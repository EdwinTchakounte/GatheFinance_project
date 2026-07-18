import 'package:flutter/material.dart';

import '../../../app/theme/app_typography.dart';

/// Pill d'action . cercle 56 avec icône au centre + label compact en dessous.
///
/// Style néobanque (Paysika / Wave) :
///   - cercle ~56 px, fond primary à 12 % d'alpha
///   - icône primary 22 px
///   - label tiny 11 pt sous le cercle
///   - feedback tactile InkWell + animation de scale on press
class NbActionPill extends StatelessWidget {
  const NbActionPill({
    super.key,
    required this.icon,
    required this.label,
    required this.onTap,
    this.iconColor,
    this.background,
  });

  final IconData icon;
  final String label;
  final VoidCallback? onTap;
  final Color? iconColor;
  final Color? background;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final fg = iconColor ?? scheme.primary;
    final bg = background ?? scheme.primary.withValues(alpha: 0.10);
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
              width: 56,
              height: 56,
              decoration: BoxDecoration(
                color: bg,
                shape: BoxShape.circle,
              ),
              alignment: Alignment.center,
              child: Icon(icon, color: fg, size: 24),
            ),
            const SizedBox(height: 8),
            SizedBox(
              width: 72,
              child: Text(
                label,
                textAlign: TextAlign.center,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: AppTypography.bodySmall.copyWith(
                  fontSize: 11,
                  fontWeight: FontWeight.w600,
                  height: 1.2,
                  color: scheme.onSurface.withValues(alpha: 0.85),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
