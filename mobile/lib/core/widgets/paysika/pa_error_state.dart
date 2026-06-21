import 'package:flutter/material.dart';

import '../../../app/theme/paysika/pa_colors.dart';
import '../../../app/theme/paysika/pa_typography.dart';
import '../../../l10n/gen/app_localizations.dart';
import 'pa_button.dart';
import 'pa_card.dart';

/// État d'erreur unifié (Paysika) avec bouton « Réessayer ».
///
/// Remplace les multiples `_ErrorBox` / `_ErrorState` qui affichaient un
/// `e.toString()` brut sans action. On NE montre jamais le détail technique
/// à l'utilisateur : un titre clair + un sous-texte rassurant + un retry.
class PaErrorState extends StatelessWidget {
  const PaErrorState({
    super.key,
    this.title,
    this.message,
    this.onRetry,
  });

  /// Titre court. Par défaut « Une erreur est survenue » (i18n).
  final String? title;

  /// Sous-texte explicatif (jamais le détail technique). Optionnel.
  final String? message;

  /// Si fourni, affiche un bouton « Réessayer ».
  final VoidCallback? onRetry;

  @override
  Widget build(BuildContext context) {
    final l = AppL10n.of(context);
    return PaCard(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 44,
            height: 44,
            decoration: const BoxDecoration(
              color: PaColors.dangerSurface,
              shape: BoxShape.circle,
            ),
            alignment: Alignment.center,
            child: const Icon(Icons.cloud_off_rounded,
                color: PaColors.danger, size: 22,),
          ),
          const SizedBox(height: 14),
          Text(
            title ?? l.error_generic_title,
            style: PaText.heading(size: 16),
          ),
          const SizedBox(height: 6),
          Text(
            message ?? l.error_generic_body,
            style: PaText.body(size: 13.5, height: 1.5),
          ),
          if (onRetry != null) ...[
            const SizedBox(height: 16),
            PaButton(
              label: l.common_retry,
              icon: Icons.refresh_rounded,
              variant: PaButtonVariant.outline,
              fullWidth: false,
              onPressed: onRetry,
              height: 44,
            ),
          ],
        ],
      ),
    );
  }
}
