import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../app/theme/paysika/pa_colors.dart';
import '../../../../core/error/error_message.dart';
import '../../../../core/formatters/xaf_formatter.dart';
import '../../../../core/services/tara_checkout_launcher.dart';
import '../../../../core/widgets/paysika/pa_button.dart';
import '../../../../core/widgets/paysika/pa_card.dart';
import '../../../auth/presentation/state/auth_notifier.dart';
import '../state/membership_fees_notifier.dart';

/// Deux paiements de cycle, distincts de la première activation :
///   • [renewal]      — renouvellement annuel à l'anniversaire (carnet) ;
///   • [reactivation] — réactivation d'un compte suspendu pour non-renouvellement
///     (frais d'adhésion, décision métier 2026-07-21).
enum MembershipPaymentMode { renewal, reactivation }

/// Feuille de paiement de cycle (renouvellement / réactivation).
///
/// À la différence de l'activation initiale (3 frais), c'est UN seul frais —
/// carnet pour le renouvellement, adhésion pour la réactivation. Le solde
/// épargne et l'historique sont **conservés** (message de réassurance explicite,
/// à parité avec le portail).
class MembershipRenewalSheet extends ConsumerStatefulWidget {
  const MembershipRenewalSheet({super.key, required this.mode});

  final MembershipPaymentMode mode;

  static Future<void> show(BuildContext context, MembershipPaymentMode mode) =>
      showModalBottomSheet<void>(
        context: context,
        isScrollControlled: true,
        backgroundColor: PaColors.canvas,
        shape: const RoundedRectangleBorder(
          borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
        ),
        builder: (_) => MembershipRenewalSheet(mode: mode),
      );

  @override
  ConsumerState<MembershipRenewalSheet> createState() => _State();
}

class _State extends ConsumerState<MembershipRenewalSheet>
    with WidgetsBindingObserver {
  final _phoneCtrl = TextEditingController();
  bool _busy = false;
  bool _launched = false; // un paiement Mobile Money a été lancé

  bool get _isReactivation => widget.mode == MembershipPaymentMode.reactivation;

  // Renouvellement → carnet ; réactivation → adhésion (pénalité 10 000).
  String get _feeCode => _isReactivation ? 'ADHESION' : 'CARNET';

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _phoneCtrl.dispose();
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) _refreshAll();
  }

  Future<void> _refreshAll() async {
    await ref.read(membershipFeesProvider.notifier).refresh();
    ref.invalidate(authProvider);
  }

  MembershipFee? _fee(MembershipFeesState? s) {
    if (s == null) return null;
    for (final f in s.fees) {
      if (f.code == _feeCode) return f;
    }
    return null;
  }

  Future<void> _payMobileMoney() async {
    final phone = _phoneCtrl.text.replaceAll(RegExp(r'\D'), '');
    if (phone.length < 8) {
      _toast('Saisis un numéro Mobile Money valide.');
      return;
    }
    setState(() => _busy = true);
    try {
      final data = await ref
          .read(membershipFeesProvider.notifier)
          .initMobileMoney(code: _feeCode, phone: phone);
      if (!mounted) return;
      setState(() => _launched = true);
      await TaraCheckoutLauncher.launchFromInitResponse(data);
    } catch (e) {
      if (mounted) _toast(friendlyError(e));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _payFromAccount() async {
    setState(() => _busy = true);
    try {
      await ref.read(membershipFeesProvider.notifier).payFromAccount(_feeCode);
      unawaited(HapticFeedback.mediumImpact());
      ref.invalidate(authProvider);
      if (!mounted) return;
      Navigator.of(context).pop();
      _toast(
        _isReactivation ? 'Compte réactivé.' : 'Renouvellement enregistré.',
      );
    } catch (e) {
      if (mounted) _toast(friendlyError(e));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  void _toast(String msg) =>
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(msg)));

  @override
  Widget build(BuildContext context) {
    final feesAsync = ref.watch(membershipFeesProvider);
    final fee = _fee(feesAsync.valueOrNull);
    final amount = fee?.amount ?? (_isReactivation ? 10000 : 1000);
    final solvable = fee?.solvable ?? false;

    final title =
        _isReactivation ? 'Réactive ton compte' : 'Renouvelle ton adhésion';
    final intro = _isReactivation
        ? 'Ton compte est suspendu (anniversaire annuel dépassé). Règle tes '
            "frais d'adhésion pour le réactiver."
        : "C'est l'heure de ton renouvellement annuel. Règle ton carnet pour "
            'reconduire ton adhésion sur le cycle suivant.';

    return Padding(
      padding: EdgeInsets.only(bottom: MediaQuery.viewInsetsOf(context).bottom),
      child: SafeArea(
        top: false,
        child: SingleChildScrollView(
          padding: const EdgeInsets.fromLTRB(20, 12, 20, 24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Center(
                child: Container(
                  width: 40,
                  height: 4,
                  decoration: BoxDecoration(
                    color: PaColors.line,
                    borderRadius: BorderRadius.circular(2),
                  ),
                ),
              ),
              const SizedBox(height: 18),
              Text(
                title,
                style: const TextStyle(
                  color: PaColors.inkPrimary,
                  fontSize: 20,
                  fontWeight: FontWeight.w800,
                ),
              ),
              const SizedBox(height: 4),
              Text(
                intro,
                style: const TextStyle(
                  color: PaColors.inkSecondary,
                  fontSize: 13,
                  height: 1.35,
                ),
              ),
              const SizedBox(height: 16),

              // Montant
              PaCard(
                padding: const EdgeInsets.all(16),
                child: Row(
                  children: [
                    Expanded(
                      child: Text(
                        _isReactivation
                            ? "Frais d'adhésion"
                            : 'Frais de carnet annuel',
                        style: const TextStyle(
                          color: PaColors.inkPrimary,
                          fontSize: 14,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                    ),
                    Text(
                      '${XAFFormatter.formatNumber(amount)} XAF',
                      style: const TextStyle(
                        color: PaColors.teal,
                        fontSize: 18,
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 10),

              // Réassurance : le solde et l'historique sont conservés.
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: PaColors.tealSurface,
                  borderRadius: BorderRadius.circular(12),
                ),
                child: const Row(
                  children: [
                    Icon(
                      Icons.verified_outlined,
                      color: PaColors.teal,
                      size: 18,
                    ),
                    SizedBox(width: 10),
                    Expanded(
                      child: Text(
                        'Ton numéro, ton solde d’épargne et tout ton historique '
                        'sont conservés sur le cycle suivant.',
                        style: TextStyle(
                          color: PaColors.tealDark,
                          fontSize: 12,
                          height: 1.35,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 18),

              if (_launched) ...[
                Container(
                  padding: const EdgeInsets.all(14),
                  decoration: BoxDecoration(
                    color: PaColors.warningSurface,
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: const Row(
                    children: [
                      Icon(
                        Icons.hourglass_bottom_rounded,
                        color: PaColors.warning,
                        size: 18,
                      ),
                      SizedBox(width: 10),
                      Expanded(
                        child: Text(
                          'Valide le paiement sur ton téléphone, puis reviens : '
                          'ton statut se met à jour automatiquement.',
                          style: TextStyle(
                            color: PaColors.inkSecondary,
                            fontSize: 12,
                            height: 1.35,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 12),
                PaButton(
                  label: 'Actualiser mon statut',
                  variant: PaButtonVariant.outline,
                  onPressed: _busy ? null : _refreshAll,
                ),
              ] else ...[
                const Text(
                  'NUMÉRO MOBILE MONEY',
                  style: TextStyle(
                    color: PaColors.inkSecondary,
                    fontSize: 11,
                    fontWeight: FontWeight.w700,
                    letterSpacing: 1.1,
                  ),
                ),
                const SizedBox(height: 8),
                TextField(
                  controller: _phoneCtrl,
                  keyboardType: TextInputType.phone,
                  cursorColor: PaColors.teal,
                  decoration: InputDecoration(
                    prefixText: '+237 ',
                    hintText: '6 XX XX XX XX',
                    filled: true,
                    fillColor: PaColors.cardBg,
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(12),
                      borderSide: BorderSide.none,
                    ),
                  ),
                ),
                const SizedBox(height: 16),
                PaButton(
                  label: _busy ? '…' : 'Payer par Mobile Money',
                  icon: Icons.smartphone_rounded,
                  onPressed: _busy ? null : _payMobileMoney,
                ),
                if (solvable) ...[
                  const SizedBox(height: 8),
                  PaButton(
                    label: 'Payer depuis mon compte',
                    variant: PaButtonVariant.outline,
                    onPressed: _busy ? null : _payFromAccount,
                  ),
                ],
              ],
            ],
          ),
        ),
      ),
    );
  }
}
