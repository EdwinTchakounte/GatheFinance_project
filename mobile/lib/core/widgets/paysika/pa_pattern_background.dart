import 'package:flutter/material.dart';

import '../../../app/theme/paysika/pa_colors.dart';

/// Fond texturé Paysika — canvas crème + motif doodle finance subtil + halos.
///
/// Reproduit l'ambiance du fond de référence (`capture_paysika/fond.jpeg`,
/// motif WhatsApp-like de pictogrammes commerce/finance en line-art) tout en
/// restant assez discret pour ne pas concurrencer le contenu :
///
///   1. Base crème [PaColors.canvas] (matche la couleur du doodle → coutures
///      du tiling invisibles).
///   2. Doodle `assets/images/doodle_pattern.jpg` répété, atténué par
///      [patternOpacity].
///   3. Deux halos radiaux très diffus (teal haut-droite, navy bas-gauche)
///      pour la lumière premium.
///
/// Les cards posées par-dessus restent blanches (PaColors.paper) avec leur
/// ombre signature → elles « flottent » nettement sur la texture.
class PaPatternBackground extends StatelessWidget {
  const PaPatternBackground({
    super.key,
    required this.child,
    this.patternOpacity = 0.55,
    this.showHalos = true,
  });

  final Widget child;

  /// Atténuation du motif doodle (0 = invisible, 1 = pleine intensité).
  final double patternOpacity;

  /// Affiche les deux halos lumineux d'angle.
  final bool showHalos;

  @override
  Widget build(BuildContext context) {
    return Stack(
      children: [
        // 1. Base crème + motif doodle tilé.
        Positioned.fill(
          child: DecoratedBox(
            decoration: BoxDecoration(
              color: PaColors.canvas,
              image: DecorationImage(
                image: const AssetImage('assets/images/doodle_pattern.jpg'),
                repeat: ImageRepeat.repeat,
                opacity: patternOpacity,
              ),
            ),
          ),
        ),

        // 2. Halos diffus — lumière douce premium.
        if (showHalos) ...[
          Positioned(
            top: -150,
            right: -110,
            child: IgnorePointer(
              child: _Halo(
                color: PaColors.teal.withValues(alpha: 0.10),
                size: 340,
              ),
            ),
          ),
          Positioned(
            bottom: -170,
            left: -130,
            child: IgnorePointer(
              child: _Halo(
                color: PaColors.navy.withValues(alpha: 0.07),
                size: 320,
              ),
            ),
          ),
        ],

        // 3. Contenu.
        Positioned.fill(child: child),
      ],
    );
  }
}


class _Halo extends StatelessWidget {
  const _Halo({required this.color, required this.size});

  final Color color;
  final double size;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        gradient: RadialGradient(
          colors: [color, color.withValues(alpha: 0)],
        ),
      ),
    );
  }
}
