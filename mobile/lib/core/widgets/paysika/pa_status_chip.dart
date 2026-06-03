import 'package:flutter/material.dart';

/// Pastille de statut unifiée (Paysika) — point coloré + label.
///
/// Extraite des copies identiques `_StatusChip` de credit_page / booklet_page.
/// La couleur porte le sens (success/warning/danger…) ; le fond est une
/// teinte douce (14 %) de cette couleur.
class PaStatusChip extends StatelessWidget {
  const PaStatusChip({super.key, required this.label, required this.color});

  final String label;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.14),
        borderRadius: BorderRadius.circular(999),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 6,
            height: 6,
            decoration: BoxDecoration(color: color, shape: BoxShape.circle),
          ),
          const SizedBox(width: 6),
          Text(
            label,
            style: TextStyle(
              color: color,
              fontSize: 11.5,
              fontWeight: FontWeight.w700,
            ),
          ),
        ],
      ),
    );
  }
}
