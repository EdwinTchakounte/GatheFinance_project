import 'package:flutter/material.dart';

import '../../../app/theme/app_spacing.dart';
import '../../../app/theme/app_typography.dart';
import '../../formatters/xaf_formatter.dart';
import '../animated_amount.dart';
import '../amount_text.dart';

/// Hero solde — version néobanque épurée (style Paysika / Wave / Revolut).
///
/// Stack vertical, gauche-aligné :
///   - eyebrow `MON ÉPARGNE` en tiny gris letter-spaced
///   - solde 56 pt bold avec count-up animé
///   - delta semaine vert/rouge selon signe, ou texte neutre si null
///
/// Volontairement minimaliste — pas de carte, pas d'ombre, pas de gradient.
/// L'air et la typo font tout le travail.
class NbHeroBalance extends StatelessWidget {
  const NbHeroBalance({
    super.key,
    required this.amount,
    this.eyebrow = 'MON ÉPARGNE',
    this.deltaAmount,
    this.deltaLabel = 'cette semaine',
    this.emptyDeltaLabel = 'Pas de mouvement cette semaine',
  });

  /// Solde actuel à afficher (count-up animé).
  final num amount;

  /// Petit label au-dessus du solde — par défaut « MON ÉPARGNE ».
  final String eyebrow;

  /// Variation positive ou négative. Si `null`, affiche `emptyDeltaLabel`.
  final num? deltaAmount;

  /// Suffixe de la ligne delta — par défaut « cette semaine ».
  final String deltaLabel;

  /// Texte affiché quand `deltaAmount` est null ou 0.
  final String emptyDeltaLabel;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final muted = scheme.onSurface.withValues(alpha: 0.45);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        Text(
          eyebrow,
          style: AppTypography.bodySmall.copyWith(
            color: muted,
            fontSize: 11,
            fontWeight: FontWeight.w700,
            letterSpacing: 1.6,
          ),
        ),
        const SizedBox(height: AppSpacing.m),
        AnimatedAmount(
          amount,
          size: AmountSize.hero,
          color: scheme.onSurface,
          unitColor: muted,
        ),
        const SizedBox(height: AppSpacing.s),
        _DeltaLine(
          delta: deltaAmount,
          suffix: deltaLabel,
          empty: emptyDeltaLabel,
        ),
      ],
    );
  }
}


class _DeltaLine extends StatelessWidget {
  const _DeltaLine({
    required this.delta,
    required this.suffix,
    required this.empty,
  });

  final num? delta;
  final String suffix;
  final String empty;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final muted = scheme.onSurface.withValues(alpha: 0.55);

    if (delta == null || delta == 0) {
      return Text(
        empty,
        style: AppTypography.bodySmall.copyWith(color: muted, fontSize: 13),
      );
    }
    final positive = delta! > 0;
    final color = positive ? const Color(0xFF1B9B6E) : const Color(0xFFC6463A);
    final arrow = positive ? '↑' : '↓';
    final label = XAFFormatter.format(delta!.abs());

    return Row(
      children: [
        Text(
          '$arrow $label',
          style: AppTypography.bodySmall.copyWith(
            color: color,
            fontSize: 13,
            fontWeight: FontWeight.w700,
          ),
        ),
        const SizedBox(width: 6),
        Text(
          suffix,
          style: AppTypography.bodySmall.copyWith(color: muted, fontSize: 13),
        ),
      ],
    );
  }
}
