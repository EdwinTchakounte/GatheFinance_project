import 'package:flutter/material.dart';

import '../../app/theme/app_colors.dart';
import '../../app/theme/app_radii.dart';
import '../../app/theme/app_typography.dart';

enum PillTone { success, info, warning, danger, neutral, accent }

/// Petit chip de statut compact — `pill` du design system web transposé.
/// Les variantes `info` et `neutral` s'adaptent au mode clair/sombre via
/// le `ColorScheme` pour rester lisibles. Les variantes brand
/// (success/warning/danger/accent) gardent leurs surfaces signature qui
/// fonctionnent dans les deux modes.
class AppPill extends StatelessWidget {
  const AppPill({
    super.key,
    required this.label,
    this.tone = PillTone.neutral,
    this.icon,
  });

  final String label;
  final PillTone tone;
  final IconData? icon;

  ({Color bg, Color fg}) _palette(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    switch (tone) {
      case PillTone.success:
        return (bg: AppColors.emeraldSurface, fg: AppColors.emeraldDark);
      case PillTone.info:
        return (
          bg: scheme.primary.withValues(alpha: 0.14),
          fg: scheme.primary,
        );
      case PillTone.warning:
        return (bg: AppColors.warningSurface, fg: AppColors.terraDark);
      case PillTone.danger:
        return (bg: AppColors.dangerSurface, fg: AppColors.danger);
      case PillTone.neutral:
        return (
          bg: scheme.onSurface.withValues(alpha: 0.08),
          fg: scheme.onSurface.withValues(alpha: 0.7),
        );
      case PillTone.accent:
        return (bg: AppColors.terraSurface, fg: AppColors.terraDark);
    }
  }

  @override
  Widget build(BuildContext context) {
    final p = _palette(context);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: p.bg,
        borderRadius: const BorderRadius.all(AppRadii.pill),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (icon != null) ...[
            Icon(icon, size: 12, color: p.fg),
            const SizedBox(width: 4),
          ],
          Text(
            label,
            style: AppTypography.labelMedium.copyWith(
              color: p.fg,
              fontSize: 11.5,
              letterSpacing: 0.4,
            ),
          ),
        ],
      ),
    );
  }
}
