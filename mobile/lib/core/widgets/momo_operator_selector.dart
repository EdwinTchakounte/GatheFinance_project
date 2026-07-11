import 'package:flutter/material.dart';

import '../../app/theme/app_typography.dart';
import '../../app/theme/paysika/pa_colors.dart';

/// Sélecteur d'opérateur Mobile Money.
///
/// Renvoie la valeur attendue par le backend (`'MTN'` / `'ORANGE'`), qui doit
/// figurer dans `_ALLOWED_NETWORKS` du `PaymentInitSerializer`. Sans opérateur
/// choisi, l'init de paiement échoue avec « Ce champ ne peut être vide ».
class MomoOperatorSelector extends StatelessWidget {
  const MomoOperatorSelector({
    super.key,
    required this.value,
    required this.onChanged,
  });

  /// Valeur API courante : `'MTN'` ou `'ORANGE'`.
  final String value;
  final ValueChanged<String> onChanged;

  static const List<List<String>> _options = [
    ['MTN', 'MTN MoMo'],
    ['ORANGE', 'Orange Money'],
  ];

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        for (var i = 0; i < _options.length; i++) ...[
          if (i > 0) const SizedBox(width: 10),
          Expanded(child: _chip(context, _options[i][0], _options[i][1])),
        ],
      ],
    );
  }

  Widget _chip(BuildContext context, String code, String label) {
    final selected = value == code;
    return InkWell(
      onTap: () => onChanged(code),
      borderRadius: BorderRadius.circular(12),
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 12),
        alignment: Alignment.center,
        decoration: BoxDecoration(
          color: selected
              ? PaColors.teal.withValues(alpha: 0.12)
              : Colors.transparent,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(
            color: selected
                ? PaColors.teal
                : Theme.of(context).colorScheme.outline.withValues(alpha: 0.4),
            width: selected ? 1.6 : 1,
          ),
        ),
        child: Text(
          label,
          style: AppTypography.labelMedium.copyWith(
            color: selected
                ? PaColors.teal
                : Theme.of(context).colorScheme.onSurface,
            fontWeight: selected ? FontWeight.w700 : FontWeight.w500,
          ),
        ),
      ),
    );
  }
}
