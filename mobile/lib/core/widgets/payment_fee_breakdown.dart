import 'package:flutter/material.dart';

import '../../app/theme/paysika/pa_colors.dart';
import '../formatters/xaf_formatter.dart';

/// Décomposition « Montant / Frais (X %) / Total à payer » d'un versement.
///
/// Ne s'affiche QUE si un frais de transaction est configuré (`rate > 0`) et
/// le montant est saisi (`montant > 0`). Sinon → rien (SizedBox.shrink).
class PaymentFeeBreakdown extends StatelessWidget {
  const PaymentFeeBreakdown({
    super.key,
    required this.montant,
    required this.rate,
  });

  final num montant;
  final double rate;

  @override
  Widget build(BuildContext context) {
    if (rate <= 0 || montant <= 0) return const SizedBox.shrink();
    final frais = (montant * rate).round();
    final total = montant + frais;
    final pct = rate * 100;
    final pctLabel = pct == pct.roundToDouble()
        ? pct.toStringAsFixed(0)
        : pct.toStringAsFixed(1).replaceAll('.', ',');

    return Container(
      margin: const EdgeInsets.only(top: 12),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: PaColors.warning.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: PaColors.warning.withValues(alpha: 0.22)),
      ),
      child: Column(
        children: [
          _row(context, 'Montant', XAFFormatter.format(montant)),
          const SizedBox(height: 4),
          _row(context, 'Frais ($pctLabel %)', '+ ${XAFFormatter.format(frais)}'),
          const SizedBox(height: 10),
          _row(context, 'Total à payer', XAFFormatter.format(total), bold: true),
        ],
      ),
    );
  }

  Widget _row(BuildContext context, String label, String value,
      {bool bold = false,}) {
    final style = TextStyle(
      fontSize: bold ? 14.5 : 12.5,
      fontWeight: bold ? FontWeight.w800 : FontWeight.w500,
      color: bold ? PaColors.inkPrimary : PaColors.inkMuted,
    );
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [Text(label, style: style), Text(value, style: style)],
    );
  }
}
