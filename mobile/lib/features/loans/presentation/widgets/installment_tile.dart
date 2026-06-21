import 'package:flutter/material.dart';

import '../../../../app/theme/paysika/pa_colors.dart';
import '../../../../app/theme/app_radii.dart';
import '../../../../app/theme/app_typography.dart';
import '../../../../core/formatters/date_formatter.dart';
import '../../../../core/formatters/xaf_formatter.dart';
import '../../../../core/widgets/app_pill.dart';
import '../../../../l10n/gen/app_localizations.dart';
import '../../domain/entities/loan_installment.dart';

/// Ligne d'échéance — numéro + date + montant + pill statut.
class InstallmentTile extends StatelessWidget {
  const InstallmentTile({super.key, required this.installment});

  final LoanInstallment installment;

  ({String label, PillTone tone, IconData icon}) _statusFor(AppL10n l) {
    switch (installment.statut) {
      case InstallmentStatus.payee:
        return (
          label: l.inst_status_paid,
          tone: PillTone.success,
          icon: Icons.check_circle_rounded,
        );
      case InstallmentStatus.aVenir:
        return (
          label: l.inst_status_upcoming,
          tone: PillTone.neutral,
          icon: Icons.schedule_rounded,
        );
      case InstallmentStatus.enRetard:
        return (
          label: l.inst_status_late,
          tone: PillTone.danger,
          icon: Icons.error_rounded,
        );
      case InstallmentStatus.partielle:
        return (
          label: l.inst_status_partial,
          tone: PillTone.warning,
          icon: Icons.timelapse_rounded,
        );
    }
  }

  @override
  Widget build(BuildContext context) {
    final l = AppL10n.of(context);
    final scheme = Theme.of(context).colorScheme;
    final s = _statusFor(l);
    final accent = switch (s.tone) {
      PillTone.success => PaColors.success,
      PillTone.danger => PaColors.danger,
      PillTone.warning => PaColors.warning,
      _ => scheme.primary,
    };
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 12, horizontal: 16),
      child: Row(
        children: [
          Container(
            width: 40,
            height: 40,
            decoration: BoxDecoration(
              color: accent.withValues(alpha: 0.12),
              borderRadius: const BorderRadius.all(AppRadii.r12),
            ),
            alignment: Alignment.center,
            child: Text(
              '${installment.numero}',
              style: AppTypography.labelLarge.copyWith(color: accent),
            ),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  l.inst_due_on(
                      AppDateFormatter.short(installment.dateEcheance),),
                  style: AppTypography.labelLarge
                      .copyWith(color: scheme.onSurface),
                ),
                const SizedBox(height: 2),
                Text(
                  l.inst_capital_interest(
                    XAFFormatter.formatNumber(installment.montantCapital),
                    XAFFormatter.formatNumber(installment.montantInterets),
                  ),
                  style: AppTypography.bodySmall.copyWith(
                    color: scheme.onSurface.withValues(alpha: 0.55),
                  ),
                ),
              ],
            ),
          ),
          Column(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Text(
                XAFFormatter.formatNumber(installment.montantTotal),
                style: AppTypography.labelLarge.copyWith(
                  color: scheme.onSurface,
                  fontFeatures: const [FontFeature.tabularFigures()],
                ),
              ),
              const SizedBox(height: 4),
              AppPill(label: s.label, tone: s.tone, icon: s.icon),
            ],
          ),
        ],
      ),
    );
  }
}
