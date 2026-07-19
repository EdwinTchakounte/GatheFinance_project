import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../app/theme/paysika/pa_colors.dart';
import '../../../../app/theme/app_radii.dart';
import '../../../../app/theme/app_spacing.dart';
import '../../../../app/theme/app_typography.dart';
import '../../../../core/formatters/xaf_formatter.dart';
import '../../../../core/widgets/brand_loader.dart';
import '../../../../core/widgets/paysika/pa_button.dart';
import '../../../../l10n/gen/app_localizations.dart';
import '../../domain/entities/loan.dart';
import '../../domain/entities/loan_renewal.dart';
import '../../domain/loan_terms.dart';
import '../state/loans_notifier.dart';
import '../../../../core/error/error_message.dart';

enum _Step { form, loading, success }

/// Modale de reconduction . 2 étapes (form → success).
class RenewalSheet extends ConsumerStatefulWidget {
  const RenewalSheet({super.key, required this.loan});

  final Loan loan;

  static Future<void> show(BuildContext context, Loan loan) {
    return showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      // Plafonne le sheet pour qu'il flotte avec une marge sous la status bar
      // au lieu de grimper plein écran ; scroll interne si le contenu dépasse.
      constraints: BoxConstraints(
        maxHeight: MediaQuery.sizeOf(context).height * 0.9,
      ),
      backgroundColor: Theme.of(context).colorScheme.surface,
      barrierColor: Colors.black.withValues(alpha: 0.45),
      shape: const RoundedRectangleBorder(borderRadius: AppRadii.sheet),
      builder: (_) => RenewalSheet(loan: loan),
    );
  }

  @override
  ConsumerState<RenewalSheet> createState() => _RenewalSheetState();
}

class _RenewalSheetState extends ConsumerState<RenewalSheet>
    with TickerProviderStateMixin {
  // Article 10 : prorogation fixe de +1 mois, non négociable.
  // Article 11 : le membre choisit le mode de règlement des intérêts.
  bool _comptant = true; // true = au comptant (10 %), false = reportés (15 %)
  _Step _step = _Step.form;
  late final AnimationController _checkCtrl;

  /// Reconduction créée — porte le montant d'intérêts restant à verser.
  LoanRenewalEntity? _renewal;
  bool _paying = false;

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
    _checkCtrl.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    unawaited(HapticFeedback.mediumImpact());
    setState(() => _step = _Step.loading);
    try {
      final renewal = await ref.read(loansProvider.notifier).requestRenewal(
            loanId: widget.loan.id,
            comptant: _comptant,
          );
      if (!mounted) return;
      setState(() {
        _renewal = renewal;
        _step = _Step.success;
      });
      unawaited(HapticFeedback.heavyImpact());
      unawaited(_checkCtrl.forward());
    } catch (err) {
      if (!mounted) return;
      setState(() => _step = _Step.form);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(friendlyError(err))),
      );
    }
  }

  /// Règle les intérêts sur l'épargne classique. Non bloquant : le membre
  /// peut aussi fermer la feuille et payer plus tard (agence, mobile money)
  /// — les intérêts non versés sont reportés sur le nouvel échéancier.
  Future<void> _payFromSavings() async {
    final renewal = _renewal;
    if (renewal == null) return;
    setState(() => _paying = true);
    try {
      final updated = await ref
          .read(loansProvider.notifier)
          .payRenewalInterestFromSavings(renewal.id);
      if (!mounted) return;
      setState(() {
        _renewal = updated;
        _paying = false;
      });
      unawaited(HapticFeedback.heavyImpact());
    } catch (err) {
      if (!mounted) return;
      setState(() => _paying = false);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(friendlyError(err))),
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
            _Step.form => _formStep(),
            _Step.loading => _loadingStep(),
            _Step.success => _successStep(context),
          },
        ),
      ),
    );
  }

  Widget _formStep() {
    final l = AppL10n.of(context);
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 8, 20, 24),
      child: SingleChildScrollView(
        child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const _Grabber(),
          const SizedBox(height: AppSpacing.l),
          Text(l.ren_title, style: AppTypography.headingMedium),
          const SizedBox(height: 4),
          Text(
            l.ren_subtitle(widget.loan.numeroDossier,
                XAFFormatter.format(widget.loan.soldeRestant),),
            style: AppTypography.bodySmall.copyWith(
              color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.5),
              height: 1.45,
            ),
          ),

          const SizedBox(height: AppSpacing.xl),

          // Prorogation fixe : +1 mois (Article 10) . pas de choix de durée.
          Row(
            children: [
              const Icon(Icons.event_repeat_rounded,
                  size: 18, color: PaColors.teal,),
              const SizedBox(width: 10),
              Text(
                l.ren_extra_month,
                style: AppTypography.labelMedium.copyWith(color: PaColors.teal),
              ),
            ],
          ),

          const SizedBox(height: AppSpacing.xl),

          // Article 11 : choix du mode de règlement des intérêts.
          Text(l.ren_mode_question, style: AppTypography.labelLarge),
          const SizedBox(height: AppSpacing.m),
          _ModeOption(
            selected: _comptant,
            title: l.ren_mode_comptant,
            subtitle: l.ren_mode_comptant_sub,
            onTap: () => setState(() => _comptant = true),
          ),
          const SizedBox(height: 10),
          _ModeOption(
            selected: !_comptant,
            title: l.ren_mode_reporte,
            subtitle: l.ren_mode_reporte_sub,
            onTap: () => setState(() => _comptant = false),
          ),

          const SizedBox(height: AppSpacing.l),

          // Recap live : intérêts de reconduction (taux × capital restant) +
          // nouveau total. Pas d'intérêt sur intérêt (Article 11).
          _RecapBlock(loan: widget.loan, comptant: _comptant),

          const SizedBox(height: AppSpacing.l),

          Container(
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(
              color: PaColors.tealSurface,
              borderRadius: BorderRadius.circular(14),
            ),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Icon(Icons.info_outline_rounded,
                    size: 18, color: PaColors.teal,),
                const SizedBox(width: 10),
                Expanded(
                  child: Text(
                    l.ren_fees_note,
                    style: const TextStyle(
                      color: PaColors.navyDeep,
                      fontSize: 12,
                      height: 1.5,
                    ),
                  ),
                ),
              ],
            ),
          ),

          const SizedBox(height: AppSpacing.xl),

          PaButton(label: l.ren_submit, onPressed: _submit),
        ],
      ),
      ),
    );
  }

  Widget _loadingStep() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 8, 20, 36),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const _Grabber(),
          const SizedBox(height: 36),
          const BrandLoader(size: BrandLoaderSize.large),
          const SizedBox(height: 24),
          Text(AppL10n.of(context).lreq_sending,
              style: AppTypography.headingSmall,),
        ],
      ),
    );
  }

  Widget _successStep(BuildContext context) {
    final l = AppL10n.of(context);
    final reste = _renewal?.resteAPayer ?? 0;
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 8, 20, 28),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const _Grabber(),
          const SizedBox(height: 28),
          ScaleTransition(
            scale: CurvedAnimation(parent: _checkCtrl, curve: Curves.elasticOut),
            child: Container(
              width: 72,
              height: 72,
              decoration: BoxDecoration(
                color: PaColors.success.withValues(alpha: 0.14),
                shape: BoxShape.circle,
              ),
              alignment: Alignment.center,
              child: const Icon(Icons.check_rounded,
                  color: PaColors.success, size: 38,),
            ),
          ),
          const SizedBox(height: 18),
          Text(l.lreq_sent_title, style: AppTypography.headingMedium),
          const SizedBox(height: 6),
          Text(
            l.ren_sent_body,
            textAlign: TextAlign.center,
            style: AppTypography.bodyMedium.copyWith(
              color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.7),
              height: 1.45,
            ),
          ),
          if (reste > 0) ...[
            const SizedBox(height: 20),
            Container(
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                color: PaColors.warning.withValues(alpha: 0.10),
                borderRadius: BorderRadius.circular(14),
              ),
              child: Column(
                children: [
                  Text(
                    'Intérêts à verser : ${XAFFormatter.format(reste)}',
                    style: AppTypography.bodyMedium
                        .copyWith(fontWeight: FontWeight.w600),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    'Tu peux les régler maintenant sur ton épargne, ou plus '
                    'tard. Non versés, ils sont reportés sur ton nouvel '
                    'échéancier.',
                    textAlign: TextAlign.center,
                    style: AppTypography.bodySmall.copyWith(
                      color: Theme.of(context)
                          .colorScheme
                          .onSurface
                          .withValues(alpha: 0.7),
                      height: 1.4,
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 16),
            PaButton(
              label: _paying ? 'Prélèvement…' : 'Régler sur mon épargne',
              onPressed: _paying ? null : _payFromSavings,
            ),
            const SizedBox(height: 10),
            PaButton(
              label: 'Plus tard',
              variant: PaButtonVariant.outline,
              onPressed: () => Navigator.of(context).pop(),
            ),
          ] else ...[
            const SizedBox(height: 24),
            PaButton(
              label: l.common_understood,
              onPressed: () => Navigator.of(context).pop(),
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


/// Carte de choix de mode de reconduction (comptant / reporté) . Article 11.
class _ModeOption extends StatelessWidget {
  const _ModeOption({
    required this.selected,
    required this.title,
    required this.subtitle,
    required this.onTap,
  });

  final bool selected;
  final String title;
  final String subtitle;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      button: true,
      selected: selected,
      label: title,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(14),
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 160),
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(
            color: selected ? PaColors.tealSurface : Colors.transparent,
            borderRadius: BorderRadius.circular(14),
            border: Border.all(
              color: selected
                  ? PaColors.teal
                  : Theme.of(context).colorScheme.outline,
              width: selected ? 1.6 : 1,
            ),
          ),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(
                selected
                    ? Icons.radio_button_checked_rounded
                    : Icons.radio_button_unchecked_rounded,
                size: 20,
                color: selected ? PaColors.teal : PaColors.inkMuted,
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      title,
                      style: AppTypography.labelLarge.copyWith(
                        color: selected ? PaColors.navyDeep : PaColors.inkPrimary,
                      ),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      subtitle,
                      style: AppTypography.bodySmall.copyWith(
                        color: PaColors.inkMuted,
                        height: 1.4,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}


/// Recap chiffré : intérêts de reconduction + nouveau total (Article 11).
class _RecapBlock extends StatelessWidget {
  const _RecapBlock({required this.loan, required this.comptant});

  final Loan loan;
  final bool comptant;

  @override
  Widget build(BuildContext context) {
    final l = AppL10n.of(context);
    // Base = le solde restant (tout ce qu'il reste à remettre), pas le seul
    // capital : c'est la règle métier retenue côté serveur.
    final interets = renewalInterest(loan.soldeRestant, comptant: comptant);
    final nouveauTotal = loan.soldeRestant + interets;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surface,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: Theme.of(context).colorScheme.outline),
      ),
      child: Column(
        children: [
          _row(context, l.ren_recap_interest,
              XAFFormatter.format(interets), strong: false,),
          const SizedBox(height: 10),
          const SizedBox(height: 12),
          _row(context, l.ren_recap_total,
              XAFFormatter.format(nouveauTotal), strong: true,),
        ],
      ),
    );
  }

  Widget _row(BuildContext context, String label, String value,
      {required bool strong,}) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Text(
          label,
          style: AppTypography.bodySmall.copyWith(color: PaColors.inkMuted),
        ),
        Text(
          value,
          style: (strong
                  ? AppTypography.headingSmall
                  : AppTypography.labelLarge)
              .copyWith(
            color: strong ? PaColors.navyDeep : PaColors.inkPrimary,
          ),
        ),
      ],
    );
  }
}
