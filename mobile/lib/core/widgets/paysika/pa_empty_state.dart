import 'package:flutter/material.dart';

import '../../../app/theme/paysika/pa_colors.dart';

/// État vide premium unifié GATHE : icône dans un cercle teinté + titre + texte
/// (+ action optionnelle). Remplace les « Icône nue + texte » disséminés pour
/// un rendu cohérent sur toute l'app.
///
/// Usage :
///   PaEmptyState(
///     icon: Icons.campaign_outlined,
///     title: 'Aucune campagne active',
///     message: 'Reviens plus tard ou tire pour rafraîchir.',
///   )
class PaEmptyState extends StatelessWidget {
  const PaEmptyState({
    super.key,
    required this.icon,
    required this.title,
    this.message,
    this.tint = PaColors.teal,
    this.action,
  });

  final IconData icon;
  final String title;
  final String? message;

  /// Teinte du cercle + de l'icône (teal par défaut ; warning pour actualités…).
  final Color tint;

  /// Widget d'action optionnel (bouton) affiché sous le message.
  final Widget? action;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 32, vertical: 28),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 72,
              height: 72,
              decoration: BoxDecoration(
                color: tint.withValues(alpha: 0.10),
                shape: BoxShape.circle,
              ),
              child: Icon(icon, size: 32, color: tint),
            ),
            const SizedBox(height: 18),
            Text(
              title,
              textAlign: TextAlign.center,
              style: const TextStyle(
                color: PaColors.inkPrimary,
                fontSize: 16,
                fontWeight: FontWeight.w700,
              ),
            ),
            if (message != null) ...[
              const SizedBox(height: 8),
              Text(
                message!,
                textAlign: TextAlign.center,
                style: const TextStyle(
                  color: PaColors.inkSecondary,
                  fontSize: 13,
                  height: 1.45,
                ),
              ),
            ],
            if (action != null) ...[
              const SizedBox(height: 20),
              action!,
            ],
          ],
        ),
      ),
    );
  }
}
