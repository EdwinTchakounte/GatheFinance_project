import 'dart:async';
import 'package:flutter/foundation.dart' show kDebugMode;
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../app/theme/paysika/pa_colors.dart';
import '../../../../app/theme/app_radii.dart';
import '../../../../app/theme/app_spacing.dart';
import '../../../../app/theme/app_typography.dart';
import '../../../../core/services/tara_checkout_launcher.dart';
import '../../../../core/services/transaction_fee_provider.dart';
import '../../../../core/widgets/brand_loader.dart';
import '../../../../core/widgets/payment_fee_breakdown.dart';
import '../../../../core/widgets/paysika/pa_button.dart';
import '../../../../l10n/gen/app_localizations.dart';
import '../state/booklet_notifier.dart';

enum _Step { form, loading, success }

/// Sheet "Commander mon carnet" : versement Mobile Money + accès aux
/// documents officiels de la coopérative (spécimen carnet + règlement).
class OrderBookletSheet extends ConsumerStatefulWidget {
  const OrderBookletSheet({super.key});

  static Future<void> show(BuildContext context) {
    return showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      constraints: BoxConstraints(
        maxHeight: MediaQuery.sizeOf(context).height * 0.92,
      ),
      backgroundColor: Theme.of(context).colorScheme.surface,
      barrierColor: Colors.black.withValues(alpha: 0.45),
      shape: const RoundedRectangleBorder(borderRadius: AppRadii.sheet),
      builder: (_) => const OrderBookletSheet(),
    );
  }

  @override
  ConsumerState<OrderBookletSheet> createState() => _OrderBookletSheetState();
}

class _OrderBookletSheetState extends ConsumerState<OrderBookletSheet>
    with TickerProviderStateMixin {
  final _formKey = GlobalKey<FormState>();
  final _phoneCtrl = TextEditingController();
  // Frais de carnet (Article 4 du Reglement) = 1 000 XAF officiel.
  // En kDebugMode (dev local) on baisse a 100 pour faciliter les tests STK
  // sandbox Tara qui plafonnent les micro-paiements ; en release le champ
  // est figé sur 1 000 et caché de l'UI.
  final _amountCtrl = TextEditingController(text: kDebugMode ? '100' : '1000');
  _Step _step = _Step.form;
  late final AnimationController _checkCtrl;

  @override
  void initState() {
    super.initState();
    _checkCtrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 700),
    );
  }

  @override
  void dispose() {
    _phoneCtrl.dispose();
    _amountCtrl.dispose();
    _checkCtrl.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    unawaited(HapticFeedback.mediumImpact());
    setState(() => _step = _Step.loading);
    try {
      final amount = int.tryParse(_amountCtrl.text.trim()) ?? 1000;
      await ref.read(bookletProvider.notifier).order(
            phone: _phoneCtrl.text,
            network: '',
            montant: amount,
          );
      if (!mounted) return;
      setState(() => _step = _Step.success);
      unawaited(HapticFeedback.heavyImpact());
      unawaited(_checkCtrl.forward());
    } catch (err) {
      if (!mounted) return;
      setState(() => _step = _Step.form);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(err.toString())),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedSize(
      duration: const Duration(milliseconds: 280),
      curve: Curves.easeOutCubic,
      alignment: Alignment.topCenter,
      child: Padding(
        padding: EdgeInsets.only(
          bottom: MediaQuery.viewInsetsOf(context).bottom,
        ),
        child: SafeArea(
          top: false,
          child: switch (_step) {
            _Step.form => _form(),
            _Step.loading => _loading(),
            _Step.success => _success(context),
          },
        ),
      ),
    );
  }

  Widget _form() {
    final l = AppL10n.of(context);
    return SingleChildScrollView(
      padding: const EdgeInsets.fromLTRB(20, 8, 20, 28),
      child: Form(
        key: _formKey,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const _Grabber(),
            const SizedBox(height: AppSpacing.l),

            // Hero : illustration ronde + titre + sous-titre.
            const _Hero(),
            const SizedBox(height: AppSpacing.l),

            // Note : les documents officiels (reglement + specimen carnet)
            // ont ete deplaces dans la page Mon Carnet . on garde ici uniquement
            // le formulaire de commande pour resserrer le focus utilisateur.

            // Section formulaire versement.
            Text(
              'Versement',
              style: AppTypography.labelMedium.copyWith(
                color: PaColors.inkSecondary,
                letterSpacing: 0.6,
              ),
            ),
            const SizedBox(height: 8),

            Text(l.common_number, style: AppTypography.labelMedium),
            const SizedBox(height: AppSpacing.s),
            TextFormField(
              controller: _phoneCtrl,
              keyboardType: TextInputType.phone,
              style: AppTypography.bodyLarge,
              decoration: InputDecoration(
                hintText: '6XX XX XX XX',
                prefixIcon: Padding(
                  padding: const EdgeInsets.only(left: 14, right: 8),
                  child: Text('+237  ', style: TextStyle(
                    color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.7),
                    fontWeight: FontWeight.w600,
                  ),),
                ),
                prefixIconConstraints:
                    const BoxConstraints(minWidth: 0, minHeight: 0),
              ),
              validator: (v) {
                final digits = (v ?? '').replaceAll(RegExp(r'\D'), '');
                if (digits.length < 8) return l.err_number_incomplete;
                return null;
              },
            ),

            // Champ montant : edition possible uniquement en debug (sandbox
            // Tara). En release on cache le champ — montant fige a 1 000 XAF
            // par le default du controller. Cf. _amountCtrl plus haut.
            if (kDebugMode) ...[
              const SizedBox(height: AppSpacing.l),
              Text('Montant (XAF) - mode dev', style: AppTypography.labelMedium),
              const SizedBox(height: AppSpacing.s),
              TextFormField(
                controller: _amountCtrl,
                keyboardType: TextInputType.number,
                style: AppTypography.bodyLarge,
                decoration: const InputDecoration(
                  hintText: '100',
                  suffixText: 'XAF',
                ),
                validator: (v) {
                  final n = int.tryParse((v ?? '').trim());
                  if (n == null || n < 100) return 'Montant min. 100 XAF.';
                  return null;
                },
              ),
            ],

            const SizedBox(height: AppSpacing.l),

            Container(
              padding: const EdgeInsets.all(13),
              decoration: BoxDecoration(
                color: PaColors.warningSurface,
                borderRadius: BorderRadius.circular(12),
              ),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Icon(Icons.menu_book_rounded,
                      size: 17, color: PaColors.warning,),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      l.bko_after_note,
                      style: const TextStyle(
                        color: PaColors.warning,
                        fontSize: 12,
                        height: 1.45,
                      ),
                    ),
                  ),
                ],
              ),
            ),

            ValueListenableBuilder<TextEditingValue>(
              valueListenable: _amountCtrl,
              builder: (_, value, __) {
                final rate =
                    ref.watch(transactionFeeRateProvider).valueOrNull ?? 0.0;
                final m = int.tryParse(value.text.trim()) ?? 0;
                return PaymentFeeBreakdown(montant: m, rate: rate);
              },
            ),

            const SizedBox(height: AppSpacing.xl),

            PaButton(label: l.bko_pay, onPressed: _submit),
          ],
        ),
      ),
    );
  }

  Widget _loading() {
    final l = AppL10n.of(context);
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 8, 20, 36),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const _Grabber(),
          const SizedBox(height: 32),
          const BrandLoader(size: BrandLoaderSize.large),
          const SizedBox(height: 22),
          Text(
            l.bko_waiting_body('Mobile Money'),
            style: AppTypography.headingSmall,
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 6),
          Text(
            'Tara confirme la transaction.',
            style: AppTypography.bodyMedium.copyWith(
              color: Theme.of(context).colorScheme.onSurface
                  .withValues(alpha: 0.7),
            ),
          ),
        ],
      ),
    );
  }

  Widget _success(BuildContext context) {
    final l = AppL10n.of(context);
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 8, 20, 28),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const _Grabber(),
          const SizedBox(height: 26),
          ScaleTransition(
            scale: CurvedAnimation(
              parent: _checkCtrl,
              curve: Curves.elasticOut,
            ),
            child: Container(
              width: 68,
              height: 68,
              decoration: BoxDecoration(
                color: PaColors.success.withValues(alpha: 0.14),
                shape: BoxShape.circle,
              ),
              alignment: Alignment.center,
              child: const Icon(
                Icons.menu_book_rounded,
                color: PaColors.success,
                size: 32,
              ),
            ),
          ),
          const SizedBox(height: 16),
          Text(l.bko_done_title, style: AppTypography.headingMedium),
          const SizedBox(height: 6),
          Text(
            "L'agence va imprimer ton carnet sous 48 h.\nTu recevras une notification au retrait.",
            textAlign: TextAlign.center,
            style: AppTypography.bodyMedium.copyWith(
              color: Theme.of(context).colorScheme.onSurface
                  .withValues(alpha: 0.7),
              height: 1.45,
            ),
          ),
          if (LastTaraResponse.vendor != null
              || LastTaraResponse.status != null) ...[
            const SizedBox(height: 14),
            _TaraConfirmedBadge(),
          ],
          const SizedBox(height: 22),
          PaButton(
            label: l.common_understood,
            onPressed: () => Navigator.of(context).pop(),
          ),
        ],
      ),
    );
  }
}


// ─────────────────────────────────────────────────────────────────────────
// Composants visuels
// ─────────────────────────────────────────────────────────────────────────


class _Hero extends StatelessWidget {
  const _Hero();

  @override
  Widget build(BuildContext context) {
    final l = AppL10n.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // Cercle dégradé teal+navy avec icône carnet.
        Container(
          width: 56,
          height: 56,
          decoration: BoxDecoration(
            gradient: LinearGradient(
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
              colors: [
                PaColors.teal.withValues(alpha: 0.22),
                PaColors.navy.withValues(alpha: 0.12),
              ],
            ),
            shape: BoxShape.circle,
            border: Border.all(
              color: PaColors.teal.withValues(alpha: 0.3),
              width: 1.2,
            ),
          ),
          alignment: Alignment.center,
          child: const Icon(
            Icons.menu_book_rounded,
            color: PaColors.navy,
            size: 26,
          ),
        ),
        const SizedBox(height: 14),
        Text(l.bko_title, style: AppTypography.headingMedium),
        const SizedBox(height: 4),
        Text(
          l.bko_sub,
          style: AppTypography.bodyMedium.copyWith(
            color: Theme.of(context).colorScheme.onSurface
                .withValues(alpha: 0.65),
            height: 1.4,
          ),
        ),
      ],
    );
  }
}

class _TaraConfirmedBadge extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(11),
      decoration: BoxDecoration(
        color: PaColors.teal.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(11),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (LastTaraResponse.prettyVendor != null)
            Row(
              children: [
                const Icon(Icons.check_circle_outline_rounded,
                    size: 15, color: PaColors.teal,),
                const SizedBox(width: 8),
                Text(
                  'Confirme. ${LastTaraResponse.prettyVendor}',
                  style: AppTypography.labelMedium.copyWith(
                    color: PaColors.teal,
                    fontSize: 12,
                  ),
                ),
              ],
            ),
          if (LastTaraResponse.message != null) ...[
            const SizedBox(height: 4),
            Text(
              'Statut Tara. ${LastTaraResponse.status} '
                  '(${LastTaraResponse.message})',
              style: AppTypography.bodySmall.copyWith(
                color: Theme.of(context).colorScheme.onSurface
                    .withValues(alpha: 0.65),
                fontSize: 11,
              ),
            ),
          ],
        ],
      ),
    );
  }
}


class _Grabber extends StatelessWidget {
  const _Grabber();

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Container(
        width: 36,
        height: 4,
        decoration: BoxDecoration(
          color: Theme.of(context).colorScheme.outline,
          borderRadius: BorderRadius.circular(2),
        ),
      ),
    );
  }
}
