import 'package:flutter/material.dart';

import '../../../app/theme/paysika/pa_colors.dart';
import '../../../app/theme/paysika/pa_typography.dart';
import 'pa_logo.dart';

/// Header compact pleine largeur . logo + titre sur la même ligne, posé
/// sur un **gradient soft** vert→bleu (8% opacity) et clos par un filet
/// hairline.
///
/// Pattern utilisé en haut de Crédit / Carnet / Profil (2026-06-18).
class PaGradientHeaderBand extends StatelessWidget {
  const PaGradientHeaderBand({
    super.key,
    required this.title,
    this.action,
  });

  final String title;

  /// Action optionnelle à droite (cloche, menu…). Si null, juste logo + titre.
  final Widget? action;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.centerLeft,
          end: Alignment.centerRight,
          colors: [
            PaColors.teal.withValues(alpha: 0.10),
            PaColors.blue.withValues(alpha: 0.10),
          ],
        ),
        border: const Border(
          bottom: BorderSide(color: PaColors.line, width: 0.8),
        ),
      ),
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 12),
      child: Row(
        children: [
          const PaLogo(height: 22),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              title,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: PaText.heading(size: 18),
            ),
          ),
          if (action != null) ...[
            const SizedBox(width: 10),
            action!,
          ],
        ],
      ),
    );
  }
}
