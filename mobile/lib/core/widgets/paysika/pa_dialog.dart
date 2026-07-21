import 'package:flutter/material.dart';

import '../../../app/theme/paysika/pa_colors.dart';
import 'pa_button.dart';

/// Boîtes de dialogue premium (Paysika) — remplacent les `AlertDialog`
/// système par défaut, disparates page par page. Une seule identité visuelle :
/// carte `paper` arrondie (radius 22), pastille d'icône colorée, titre Syne,
/// corps lisible, actions en boutons pill [PaButton].
///
/// Deux points d'entrée :
///   • [showPaConfirm] — question binaire (confirmer / annuler), avec teinte
///     rouge optionnelle pour une action destructive ;
///   • [showPaAlert]   — information à acquitter (un seul bouton), avec liste
///     de puces optionnelle (ex. motifs d'inéligibilité).

/// Dialogue de confirmation. Retourne `true` si l'utilisateur confirme.
Future<bool> showPaConfirm(
  BuildContext context, {
  required String title,
  required String message,
  String confirmLabel = 'Confirmer',
  String cancelLabel = 'Annuler',
  IconData icon = Icons.help_outline_rounded,
  bool danger = false,
}) async {
  final res = await showDialog<bool>(
    context: context,
    builder: (ctx) => _PaDialogShell(
      icon: icon,
      accent: danger ? PaColors.danger : PaColors.teal,
      accentSurface: danger ? PaColors.dangerSurface : PaColors.tealSurface,
      title: title,
      content: Text(
        message,
        style: const TextStyle(
          color: PaColors.inkSecondary,
          fontSize: 14,
          height: 1.4,
        ),
      ),
      actions: [
        PaButton(
          label: confirmLabel,
          variant: PaButtonVariant.primary,
          onPressed: () => Navigator.of(ctx).pop(true),
        ),
        const SizedBox(height: 8),
        PaButton(
          label: cancelLabel,
          variant: PaButtonVariant.outline,
          onPressed: () => Navigator.of(ctx).pop(false),
        ),
      ],
    ),
  );
  return res ?? false;
}

/// Dialogue d'information à acquitter. [bullets] affiche une liste de puces
/// sous le [message] (ex. motifs d'un refus).
Future<void> showPaAlert(
  BuildContext context, {
  required String title,
  String? message,
  List<String> bullets = const [],
  String actionLabel = "J'ai compris",
  IconData icon = Icons.info_outline_rounded,
  Color accent = PaColors.blue,
}) {
  return showDialog<void>(
    context: context,
    builder: (ctx) => _PaDialogShell(
      icon: icon,
      accent: accent,
      accentSurface: accent.withValues(alpha: 0.12),
      title: title,
      content: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          if (message != null)
            Text(
              message,
              style: const TextStyle(
                color: PaColors.inkSecondary,
                fontSize: 14,
                height: 1.4,
              ),
            ),
          if (bullets.isNotEmpty) ...[
            if (message != null) const SizedBox(height: 12),
            ...bullets.map(
              (b) => Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Container(
                      margin: const EdgeInsets.only(top: 6, right: 9),
                      width: 5,
                      height: 5,
                      decoration: const BoxDecoration(
                        color: PaColors.teal,
                        shape: BoxShape.circle,
                      ),
                    ),
                    Expanded(
                      child: Text(
                        b,
                        style: const TextStyle(
                          color: PaColors.inkSecondary,
                          fontSize: 13,
                          height: 1.4,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ],
        ],
      ),
      actions: [
        PaButton(
          label: actionLabel,
          variant: PaButtonVariant.primary,
          onPressed: () => Navigator.of(ctx).pop(),
        ),
      ],
    ),
  );
}

/// Coque commune — pastille d'icône + titre + contenu + actions empilées.
class _PaDialogShell extends StatelessWidget {
  const _PaDialogShell({
    required this.icon,
    required this.accent,
    required this.accentSurface,
    required this.title,
    required this.content,
    required this.actions,
  });

  final IconData icon;
  final Color accent;
  final Color accentSurface;
  final String title;
  final Widget content;
  final List<Widget> actions;

  @override
  Widget build(BuildContext context) {
    return Dialog(
      backgroundColor: PaColors.paper,
      insetPadding: const EdgeInsets.symmetric(horizontal: 28, vertical: 24),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(22)),
      child: Padding(
        padding: const EdgeInsets.fromLTRB(22, 24, 22, 18),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Container(
              width: 46,
              height: 46,
              decoration: BoxDecoration(
                color: accentSurface,
                borderRadius: BorderRadius.circular(14),
              ),
              child: Icon(icon, color: accent, size: 24),
            ),
            const SizedBox(height: 14),
            Text(
              title,
              style: const TextStyle(
                color: PaColors.inkPrimary,
                fontSize: 17,
                fontWeight: FontWeight.w800,
                height: 1.2,
              ),
            ),
            const SizedBox(height: 8),
            content,
            const SizedBox(height: 20),
            ...actions,
          ],
        ),
      ),
    );
  }
}
