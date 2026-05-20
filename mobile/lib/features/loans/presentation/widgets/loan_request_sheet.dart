import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../app/theme/paysika/pa_colors.dart';
import '../../../../app/theme/app_radii.dart';
import '../../../../app/theme/app_spacing.dart';
import '../../../../app/theme/app_typography.dart';
import '../../../../core/formatters/xaf_formatter.dart';
import '../../../../core/widgets/brand_loader.dart';
import '../../../../l10n/gen/app_localizations.dart';
import '../../domain/entities/eligibility.dart';
import '../../domain/loan_terms.dart';
import '../state/loans_notifier.dart';

/// Modale demande de crédit — 2 étapes :
/// 1. Eligibility check + formulaire (montant slider + durée slider + motif)
/// 2. Success (demande créée, lien vers paiement frais à venir)
class LoanRequestSheet extends ConsumerStatefulWidget {
  const LoanRequestSheet({super.key, required this.eligibility});

  final Eligibility eligibility;

  static Future<void> show(BuildContext context, Eligibility eligibility) {
    return showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Theme.of(context).colorScheme.surface,
      barrierColor: Colors.black.withValues(alpha: 0.45),
      shape: const RoundedRectangleBorder(borderRadius: AppRadii.sheet),
      builder: (_) => LoanRequestSheet(eligibility: eligibility),
    );
  }

  @override
  ConsumerState<LoanRequestSheet> createState() => _LoanRequestSheetState();
}

enum _Step { form, loading, success }

class _LoanRequestSheetState extends ConsumerState<LoanRequestSheet>
    with TickerProviderStateMixin {
  final _motifCtrl = TextEditingController();
  double _montant = 200000;
  // Durée NON saisie manuellement : dérivée du montant (Art. 7).
  PaymentModality _modalite = PaymentModality.mensuel;
  _Step _step = _Step.form;
  late final AnimationController _checkCtrl;

  /// Décomposition règlementaire live (taux 10 %, durée par palier, échéancier).
  LoanBreakdown get _bd => computeLoanBreakdown(_montant, modalite: _modalite);

  @override
  void initState() {
    super.initState();
    final cap = widget.eligibility.plafondMax.toDouble();
    _montant = (cap >= 200000 ? 200000 : cap).toDouble();
    _checkCtrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 700),
    );
  }

  @override
  void dispose() {
    _motifCtrl.dispose();
    _checkCtrl.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (_motifCtrl.text.trim().length < 10) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(AppL10n.of(context).lreq_motive_short)),
      );
      return;
    }
    HapticFeedback.mediumImpact();
    setState(() => _step = _Step.loading);
    try {
      await ref.read(loanRequestsProvider.notifier).submit(
            montantDemande: _montant.round(),
            dureeMois: _bd.dureeMois, // dérivée du montant (Art. 7)
            motif: _motifCtrl.text.trim(),
          );
      if (!mounted) return;
      setState(() => _step = _Step.success);
      HapticFeedback.heavyImpact();
      _checkCtrl.forward();
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
    final cap = widget.eligibility.plafondMax.toDouble();
    final maxSlider = cap > kMinLoanAmount ? cap : kMinLoanAmount.toDouble();
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 8, 20, 24),
      child: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const _Grabber(),
            const SizedBox(height: AppSpacing.l),
            Text(l.lreq_title, style: AppTypography.headingMedium),
            const SizedBox(height: 4),
            Text(
              l.lreq_intro,
              style: AppTypography.bodySmall.copyWith(
                color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.5),
                height: 1.5,
              ),
            ),

            const SizedBox(height: AppSpacing.xl),

            // --- Montant ---
            Row(
              children: [
                Text(l.lreq_amount, style: AppTypography.labelMedium),
                const Spacer(),
                Text(
                  XAFFormatter.format(_montant),
                  style: AppTypography.headingSmall.copyWith(
                    color: PaColors.teal,
                    fontFeatures: const [FontFeature.tabularFigures()],
                  ),
                ),
              ],
            ),
            const SizedBox(height: 4),
            SliderTheme(
              data: SliderThemeData(
                trackHeight: 6,
                activeTrackColor: PaColors.teal,
                inactiveTrackColor: PaColors.tealSurface,
                thumbColor: PaColors.teal,
                overlayColor: PaColors.teal.withValues(alpha: 0.12),
                thumbShape: const RoundSliderThumbShape(enabledThumbRadius: 11),
                overlayShape: const RoundSliderOverlayShape(overlayRadius: 22),
              ),
              child: Slider(
                min: kMinLoanAmount.toDouble(),
                max: maxSlider,
                divisions: 40,
                value: _montant.clamp(kMinLoanAmount.toDouble(), maxSlider),
                onChanged: (v) => setState(() => _montant = (v / 1000).round() * 1000),
              ),
            ),

            const SizedBox(height: AppSpacing.l),

            // --- Modalité de remboursement (Art. 8) ---
            Text(l.lreq_modality, style: AppTypography.labelMedium),
            const SizedBox(height: AppSpacing.s),
            Row(
              children: [
                for (final m in PaymentModality.values) ...[
                  Expanded(
                    child: _ModalityChip(
                      label: m.label,
                      selected: _modalite == m,
                      onTap: () => setState(() => _modalite = m),
                    ),
                  ),
                  if (m != PaymentModality.values.last)
                    const SizedBox(width: 8),
                ],
              ],
            ),

            const SizedBox(height: AppSpacing.l),

            // --- Récapitulatif échéancier (dérivé du montant + modalité) ---
            _ScheduleRecap(bd: _bd),

            const SizedBox(height: AppSpacing.l),

            // --- Motivation ---
            Text(l.lreq_motive, style: AppTypography.labelMedium),
            const SizedBox(height: AppSpacing.s),
            TextFormField(
              controller: _motifCtrl,
              maxLines: 4,
              maxLength: 500,
              style: AppTypography.bodyLarge,
              decoration: InputDecoration(
                hintText: l.lreq_motive_hint,
                contentPadding:
                    const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
              ),
            ),

            const SizedBox(height: AppSpacing.m),

            // Estimation des frais
            Container(
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                color: PaColors.warningSurface,
                borderRadius: BorderRadius.circular(14),
              ),
              child: Row(
                children: [
                  const Icon(Icons.info_outline_rounded,
                      size: 18, color: PaColors.warning),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      l.lreq_fees_note,
                      style: const TextStyle(
                        color: PaColors.warning,
                        fontSize: 12.5,
                        height: 1.45,
                      ),
                    ),
                  ),
                ],
              ),
            ),

            const SizedBox(height: AppSpacing.xl),

            SizedBox(
              width: double.infinity,
              child: FilledButton(
                onPressed: _submit,
                child: Text(l.lreq_submit),
              ),
            ),
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
              style: AppTypography.headingSmall),
        ],
      ),
    );
  }

  Widget _successStep(BuildContext context) {
    final l = AppL10n.of(context);
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
                  color: PaColors.success, size: 38),
            ),
          ),
          const SizedBox(height: 18),
          Text(l.lreq_sent_title, style: AppTypography.headingMedium),
          const SizedBox(height: 6),
          Text(
            l.lreq_sent_body,
            textAlign: TextAlign.center,
            style: AppTypography.bodyMedium.copyWith(
              color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.7),
              height: 1.45,
            ),
          ),
          const SizedBox(height: 24),
          SizedBox(
            width: double.infinity,
            child: FilledButton(
              onPressed: () => Navigator.of(context).pop(),
              child: Text(l.common_understood),
            ),
          ),
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


/// Chip de modalité de remboursement (journalier / hebdo / mensuel).
class _ModalityChip extends StatelessWidget {
  const _ModalityChip({
    required this.label,
    required this.selected,
    required this.onTap,
  });

  final String label;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: selected ? PaColors.navy : PaColors.cardBg,
      borderRadius: BorderRadius.circular(12),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(12),
        child: Container(
          height: 42,
          alignment: Alignment.center,
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(12),
            border: Border.all(
              color: selected ? PaColors.navy : PaColors.line,
              width: 1,
            ),
          ),
          child: Text(
            label,
            style: AppTypography.labelMedium.copyWith(
              color: selected ? Colors.white : PaColors.inkSecondary,
              fontWeight: FontWeight.w600,
              fontSize: 12.5,
            ),
          ),
        ),
      ),
    );
  }
}


/// Récapitulatif de l'échéancier dérivé du montant (Articles 5, 7, 8).
class _ScheduleRecap extends StatelessWidget {
  const _ScheduleRecap({required this.bd});

  final LoanBreakdown bd;

  @override
  Widget build(BuildContext context) {
    final l = AppL10n.of(context);
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: PaColors.tealSurface,
        borderRadius: BorderRadius.circular(16),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.event_note_outlined, size: 18, color: PaColors.teal),
              const SizedBox(width: 8),
              Text(
                l.lreq_schedule,
                style: AppTypography.labelMedium.copyWith(
                  color: PaColors.navy,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          _row(l.lreq_duration, l.states_months(bd.dureeMois)),
          _row(l.lreq_interest, XAFFormatter.format(bd.interetsTotaux)),
          _row(l.lreq_total, XAFFormatter.format(bd.montantTotalDu),
              strong: true),
          const Divider(height: 18, color: PaColors.line),
          _row(
            l.lreq_installments('${bd.nbEcheances}'),
            l.lreq_per_time(XAFFormatter.format(bd.montantParEcheance)),
            strong: true,
            accent: true,
          ),
        ],
      ),
    );
  }

  Widget _row(String label, String value,
      {bool strong = false, bool accent = false}) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 3),
      child: Row(
        children: [
          Text(
            label,
            style: AppTypography.bodySmall.copyWith(
              color: PaColors.inkSecondary,
              fontSize: 13,
            ),
          ),
          const Spacer(),
          Text(
            value,
            style: AppTypography.bodySmall.copyWith(
              color: accent ? PaColors.teal : PaColors.inkPrimary,
              fontSize: strong ? 14 : 13,
              fontWeight: strong ? FontWeight.w700 : FontWeight.w600,
              fontFeatures: const [FontFeature.tabularFigures()],
            ),
          ),
        ],
      ),
    );
  }
}
