import 'package:flutter/material.dart';

import '../../../app/theme/paysika/pa_colors.dart';

/// Quick action Paysika — cercle **outlined gris pâle** (pas rempli teal),
/// icône navy au centre, label sobre dessous.
///
/// Reproduction fidèle des chips quick actions observés dans capture_paysika/
/// (Simulator / Bills / Transfer / More). C'est un design de "pastille sobre"
/// — la couleur ne pop pas, c'est le pictogramme qui guide l'œil.
class PaActionPill extends StatelessWidget {
  const PaActionPill({
    super.key,
    required this.icon,
    required this.label,
    required this.onTap,
    this.size = 56,
  });

  final IconData icon;
  final String label;
  final VoidCallback? onTap;
  final double size;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      button: true,
      label: label,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(28),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: size,
              height: size,
              decoration: BoxDecoration(
                color: PaColors.paper,
                shape: BoxShape.circle,
                border: Border.all(
                  color: PaColors.line,
                  width: 1,
                ),
              ),
              alignment: Alignment.center,
              child: Icon(icon, color: PaColors.navy, size: 24),
            ),
            const SizedBox(height: 7),
            SizedBox(
              width: 78,
              child: Text(
                label,
                textAlign: TextAlign.center,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(
                  color: PaColors.inkSecondary,
                  fontSize: 11.5,
                  fontWeight: FontWeight.w600,
                  height: 1.25,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
