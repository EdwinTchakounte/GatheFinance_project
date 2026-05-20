import 'package:flutter/material.dart';

import '../../app/theme/app_typography.dart';
import '../formatters/xaf_formatter.dart';

/// Affichage standard d'un montant XAF avec grosse typographie éditoriale.
/// `size` règle la hiérarchie : hero pour les soldes, large pour les KPIs,
/// medium pour les lignes de liste, small pour le secondaire.
enum AmountSize { hero, large, medium, small }

class AmountText extends StatelessWidget {
  const AmountText(
    this.amount, {
    super.key,
    this.size = AmountSize.medium,
    this.color,
    this.unitColor,
    this.showUnit = true,
    this.crossOut = false,
  });

  final num amount;
  final AmountSize size;
  final Color? color;
  final Color? unitColor;
  final bool showUnit;
  final bool crossOut;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final muted = scheme.onSurface.withValues(alpha: 0.5);
    final number = XAFFormatter.formatNumber(amount);
    final numberStyle = switch (size) {
      AmountSize.hero => AppTypography.displayXAF,
      AmountSize.large => AppTypography.displayLarge,
      AmountSize.medium => AppTypography.headingMedium.copyWith(
          fontFeatures: const [FontFeature.tabularFigures()]),
      AmountSize.small => AppTypography.bodyLarge.copyWith(
          fontFeatures: const [FontFeature.tabularFigures()]),
    };
    final unitStyle = AppTypography.labelMedium.copyWith(
      color: unitColor ?? muted,
      letterSpacing: 1.2,
    );

    final fg = color ?? scheme.onSurface;
    return RichText(
      text: TextSpan(
        children: [
          TextSpan(
            text: number,
            style: numberStyle.copyWith(
              color: fg,
              decoration: crossOut ? TextDecoration.lineThrough : null,
              decorationColor: muted,
              decorationThickness: 1.2,
            ),
          ),
          if (showUnit) ...[
            const TextSpan(text: ' '),
            TextSpan(text: 'XAF', style: unitStyle),
          ],
        ],
      ),
    );
  }
}
