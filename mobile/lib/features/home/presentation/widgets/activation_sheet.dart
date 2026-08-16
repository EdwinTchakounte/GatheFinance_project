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

/// Écran d'activation unifié — règle les TROIS frais d'adhésion au même endroit
/// (parité avec le portail web). Total, progression « N sur 3 réglés », numéro
/// saisi une seule fois, paiement dans n'importe quel ordre (Mobile Money ou
/// depuis le compte si solvable), passage automatique en « actif ».
class ActivationSheet extends ConsumerStatefulWidget {
  const ActivationSheet({super.key});

  static Future<void> show(BuildContext context) => showModalBottomSheet<void>(
        context: context,
        isScrollControlled: true,
        backgroundColor: PaColors.canvas,
        shape: const RoundedRectangleBorder(
          borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
        ),
        builder: (_) => const ActivationSheet(),
      );

  @override
  ConsumerState<ActivationSheet> createState() => _ActivationSheetState();
}

class _ActivationSheetState extends ConsumerState<ActivationSheet>
    with WidgetsBindingObserver {
  final _phoneCtrl = TextEditingController();
  String? _busyCode; // code du frais en cours de règlement

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
    // Retour du navigateur Mobile Money → réactualise frais + statut.
    if (state == AppLifecycleState.resumed) _refreshAll();
  }

  Future<void> _refreshAll() async {
    await ref.read(membershipFeesProvider.notifier).refresh();
    ref.invalidate(authProvider); // met à jour la bannière de statut (Home)
  }

  String? _phoneOrNull() {
    final phone = _phoneCtrl.text.replaceAll(RegExp(r'\D'), '');
    return phone.length >= 8 ? phone : null;
  }

  Future<void> _payMobileMoney(MembershipFee fee) async {
    final phone = _phoneOrNull();
    if (phone == null) {
      _toast('Saisis un numéro Mobile Money valide.');
      return;
    }
    setState(() => _busyCode = fee.code);
    try {
      final data = await ref
          .read(membershipFeesProvider.notifier)
          .initMobileMoney(code: fee.code, phone: phone, montant: fee.amount);
      if (!mounted) return;
      // On ne ferme pas la feuille : le membre valide sur son téléphone puis
      // revient — didChangeAppLifecycleState réactualise le statut au retour.
      await TaraCheckoutLauncher.launchFromInitResponse(data);
    } catch (e) {
      if (mounted) _toast(friendlyError(e));
    } finally {
      if (mounted) setState(() => _busyCode = null);
    }
  }

  Future<void> _payFromAccount(MembershipFee fee) async {
    setState(() => _busyCode = fee.code);
    try {
      await ref.read(membershipFeesProvider.notifier).payFromAccount(fee.code);
      unawaited(HapticFeedback.mediumImpact());
      ref.invalidate(authProvider);
      if (mounted) _toast('${fee.label} réglé.');
    } catch (e) {
      if (mounted) _toast(friendlyError(e));
    } finally {
      if (mounted) setState(() => _busyCode = null);
    }
  }

  void _toast(String msg) =>
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(msg)));

  @override
  Widget build(BuildContext context) {
    final feesAsync = ref.watch(membershipFeesProvider);
    final fees = feesAsync.valueOrNull;

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
              if (fees == null)
                const Padding(
                  padding: EdgeInsets.symmetric(vertical: 40),
                  child: Center(
                    child: CircularProgressIndicator(color: PaColors.teal),
                  ),
                )
              else if (fees.isActive && fees.allPaid)
                _SuccessBlock(onClose: () => Navigator.of(context).pop())
              else
                ..._buildActivation(fees),
            ],
          ),
        ),
      ),
    );
  }

  List<Widget> _buildActivation(MembershipFeesState fees) {
    final due = fees.due;
    return [
      const Text(
        'Active ton compte',
        style: TextStyle(
          color: PaColors.inkPrimary,
          fontSize: 20,
          fontWeight: FontWeight.w800,
        ),
      ),
      const SizedBox(height: 4),
      const Text(
        "Règle tes trois frais d'adhésion pour accéder à toutes les "
        'fonctionnalités.',
        style:
            TextStyle(color: PaColors.inkSecondary, fontSize: 13, height: 1.35),
      ),
      const SizedBox(height: 16),

      // Progression + total
      _ProgressCard(
        paid: fees.paidCount,
        required: fees.requiredCount,
        total: fees.total,
      ),
      const SizedBox(height: 16),

      // Numéro Mobile Money (saisi une seule fois)
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

      // Les trois frais
      for (final fee in due) ...[
        _FeeRow(
          fee: fee,
          busy: _busyCode == fee.code,
          anyBusy: _busyCode != null,
          onMobileMoney: () => _payMobileMoney(fee),
          onFromAccount: fee.solvable ? () => _payFromAccount(fee) : null,
        ),
        const SizedBox(height: 10),
      ],

      const SizedBox(height: 4),
      // Rappel : après paiement Mobile Money, le membre revient dans l'app.
      const Row(
        children: [
          Icon(Icons.refresh_rounded, size: 16, color: PaColors.inkMuted),
          SizedBox(width: 6),
          Expanded(
            child: Text(
              'Après paiement, reviens ici — ton statut se met à jour '
              'automatiquement.',
              style: TextStyle(
                color: PaColors.inkMuted,
                fontSize: 11.5,
                height: 1.3,
              ),
            ),
          ),
        ],
      ),
      const SizedBox(height: 12),
      PaButton(
        label: 'Actualiser mon statut',
        variant: PaButtonVariant.outline,
        onPressed: _busyCode != null ? null : _refreshAll,
      ),
    ];
  }
}

class _ProgressCard extends StatelessWidget {
  const _ProgressCard({
    required this.paid,
    required this.required,
    required this.total,
  });

  final int paid;
  final int required;
  final num total;

  @override
  Widget build(BuildContext context) {
    final ratio = required == 0 ? 0.0 : paid / required;
    return PaCard(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                '$paid sur $required frais réglés',
                style: const TextStyle(
                  color: PaColors.inkPrimary,
                  fontSize: 14,
                  fontWeight: FontWeight.w700,
                ),
              ),
              Text(
                '${XAFFormatter.formatNumber(total)} XAF',
                style: const TextStyle(
                  color: PaColors.teal,
                  fontSize: 15,
                  fontWeight: FontWeight.w800,
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          ClipRRect(
            borderRadius: BorderRadius.circular(999),
            child: LinearProgressIndicator(
              value: ratio,
              minHeight: 7,
              backgroundColor: PaColors.line,
              valueColor: const AlwaysStoppedAnimation<Color>(PaColors.teal),
            ),
          ),
        ],
      ),
    );
  }
}

class _FeeRow extends StatelessWidget {
  const _FeeRow({
    required this.fee,
    required this.busy,
    required this.anyBusy,
    required this.onMobileMoney,
    required this.onFromAccount,
  });

  final MembershipFee fee;
  final bool busy;
  final bool anyBusy;
  final VoidCallback onMobileMoney;
  final VoidCallback? onFromAccount;

  @override
  Widget build(BuildContext context) {
    final paid = fee.paye;
    return PaCard(
      padding: const EdgeInsets.all(14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 34,
                height: 34,
                decoration: BoxDecoration(
                  color: paid ? PaColors.successSurface : PaColors.tealSurface,
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Icon(
                  paid ? Icons.check_rounded : Icons.receipt_long_rounded,
                  color: paid ? PaColors.success : PaColors.teal,
                  size: 19,
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      fee.label,
                      style: const TextStyle(
                        color: PaColors.inkPrimary,
                        fontSize: 14,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    const SizedBox(height: 1),
                    Text(
                      '${XAFFormatter.formatNumber(fee.amount)} XAF',
                      style: const TextStyle(
                        color: PaColors.inkSecondary,
                        fontSize: 12.5,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ],
                ),
              ),
              if (paid)
                Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 9, vertical: 4),
                  decoration: BoxDecoration(
                    color: PaColors.successSurface,
                    borderRadius: BorderRadius.circular(999),
                  ),
                  child: const Text(
                    'Réglé',
                    style: TextStyle(
                      color: PaColors.success,
                      fontSize: 11.5,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ),
            ],
          ),
          if (!paid) ...[
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: PaButton(
                    // Ligne en cours de règlement → « Paiement… ». Les AUTRES
                    // lignes (grisées le temps de ce paiement) → « En attente »,
                    // texte distinct pour lever l'ambiguïté sur celle cliquée.
                    label: busy
                        ? 'Paiement…'
                        : (anyBusy ? 'En attente' : 'Payer'),
                    icon: Icons.smartphone_rounded,
                    height: 44,
                    onPressed: anyBusy ? null : onMobileMoney,
                  ),
                ),
                if (onFromAccount != null) ...[
                  const SizedBox(width: 8),
                  Expanded(
                    child: PaButton(
                      label: busy
                          ? 'Traitement…'
                          : (anyBusy ? 'En attente' : 'Depuis le compte'),
                      variant: PaButtonVariant.outline,
                      height: 44,
                      onPressed: anyBusy ? null : onFromAccount,
                    ),
                  ),
                ],
              ],
            ),
          ],
        ],
      ),
    );
  }
}

class _SuccessBlock extends StatelessWidget {
  const _SuccessBlock({required this.onClose});

  final VoidCallback onClose;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const SizedBox(height: 8),
        Center(
          child: Container(
            width: 64,
            height: 64,
            decoration: const BoxDecoration(
              color: PaColors.successSurface,
              shape: BoxShape.circle,
            ),
            child: const Icon(
              Icons.check_rounded,
              color: PaColors.success,
              size: 34,
            ),
          ),
        ),
        const SizedBox(height: 16),
        const Text(
          'Compte activé',
          textAlign: TextAlign.center,
          style: TextStyle(
            color: PaColors.inkPrimary,
            fontSize: 19,
            fontWeight: FontWeight.w800,
          ),
        ),
        const SizedBox(height: 6),
        const Text(
          'Tes trois frais sont réglés. Tu as désormais accès à toutes les '
          'fonctionnalités.',
          textAlign: TextAlign.center,
          style: TextStyle(
            color: PaColors.inkSecondary,
            fontSize: 13,
            height: 1.4,
          ),
        ),
        const SizedBox(height: 22),
        PaButton(label: 'Accéder à mon espace', onPressed: onClose),
      ],
    );
  }
}
