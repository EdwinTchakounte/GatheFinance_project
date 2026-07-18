import 'package:flutter/material.dart';

import '../../../app/theme/paysika/pa_colors.dart';
import 'pa_card.dart';

/// Card de service à 2 lignes (titre + sub) avec icône ronde teal-soft.
///
/// Style observé dans capture_paysika/ ("Payment estimator", "Cashback",
/// "Mobile Money Transfer"…). Format :
///
///   ┌──────────────────────────────┐
///   │ ⓘ                             │
///   │  Titre bold navy 14.5         │
///   │  Sous-titre 2 lignes 12 gris  │
///   └──────────────────────────────┘
///
/// Hauteur cible ~110-120 px pour rester compact en grille 2 colonnes.
class PaQuickService extends StatelessWidget {
  const PaQuickService({
    super.key,
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.onTap,
    this.tint,
  });

  final IconData icon;
  final String title;
  final String subtitle;
  final VoidCallback onTap;
  final Color? tint;

  @override
  Widget build(BuildContext context) {
    final color = tint ?? PaColors.teal;
    return PaCard(
      onTap: onTap,
      padding: const EdgeInsets.all(14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 38,
            height: 38,
            decoration: BoxDecoration(
              color: color.withValues(alpha: 0.14),
              shape: BoxShape.circle,
            ),
            alignment: Alignment.center,
            child: Icon(icon, color: color, size: 20),
          ),
          const SizedBox(height: 12),
          Text(
            title,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(
              color: PaColors.inkPrimary,
              fontSize: 14,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 3),
          Text(
            subtitle,
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(
              color: PaColors.inkMuted,
              fontSize: 12,
              fontWeight: FontWeight.w500,
              height: 1.3,
            ),
          ),
        ],
      ),
    );
  }
}
