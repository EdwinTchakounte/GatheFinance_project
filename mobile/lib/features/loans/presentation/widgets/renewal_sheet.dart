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
import '../../domain/entities/loan.dart';
import '../state/loans_notifier.dart';

enum _Step { form, loading, success }

/// Modale de reconduction — 2 étapes (form → success).
class RenewalSheet extends ConsumerStatefulWidget {
  const RenewalSheet({super.key, required this.loan});

  final Loan loan;

  static Future<void> show(BuildContext context, Loan loan) {
    return showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
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
  int _duree = 6;
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
    _checkCtrl.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    HapticFeedback.mediumImpact();
    setState(() => _step = _Step.loading);
    try {
      await ref.read(loansProvider.notifier).requestRenewal(
            loanId: widget.loan.id,
            nouvelleDureeMois: _duree,
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
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 8, 20, 24),
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
                XAFFormatter.format(widget.loan.soldeRestant)),
            style: AppTypography.bodySmall.copyWith(
              color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.5),
              height: 1.45,
            ),
          ),

          const SizedBox(height: AppSpacing.xl),

          Row(
            children: [
              Text(l.ren_new_duration, style: AppTypography.labelMedium),
              const Spacer(),
              Text(
                l.states_months(_duree),
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
              min: 3,
              max: 36,
              divisions: 33,
              value: _duree.toDouble(),
              onChanged: (v) => setState(() => _duree = v.round()),
            ),
          ),

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
                    size: 18, color: PaColors.teal),
                const SizedBox(width: 10),
                Expanded(
                  child: Text(
                    l.ren_fees_note,
                    style: const TextStyle(
                      color: PaColors.navyDeep,
                      fontSize: 12.5,
                      height: 1.5,
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
              child: Text(l.ren_submit),
            ),
          ),
        ],
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
            l.ren_sent_body('$_duree'),
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
