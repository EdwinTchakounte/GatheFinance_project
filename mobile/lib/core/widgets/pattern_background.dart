import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../../app/theme/app_colors.dart';
import '../../app/theme/app_colors_dark.dart';

/// Fond ambiant immersif pour TOUTES les pages de l'app.
///
/// Couches (de l'arrière vers l'avant) :
///   1. Surface plate `cream` (ou couleur custom)
///   2. Grille hexagonale de micro-points cobalt à ~3 % d'opacité
///      (l'équivalent du fond conversation WhatsApp . discret, pas
///      perceptible directement mais ajoute de la profondeur)
///   3. Deux halos radiaux très diffus (cobalt en haut-droite,
///      emerald en bas-gauche) . donnent une lumière douce
///   4. Deux filets diagonaux fins en accent terra (1px, 4 %)
///      pour la touche éditoriale type AfDB/UN
///   5. Le contenu de l'écran par-dessus
///
/// Optimisé : tout le motif est dessiné une seule fois via
/// [CustomPainter] avec un `shouldRepaint` qui renvoie toujours
/// `false`. Aucun rebuild inutile au scroll.
class PatternBackground extends StatelessWidget {
  const PatternBackground({
    super.key,
    required this.child,
    this.surface,
    this.intensity = 1.0,
    this.showHalos = true,
    this.showFilets = true,
  });

  final Widget child;

  /// Couleur de fond. `null` → `AppColors.cream`.
  final Color? surface;

  /// 0 = motif invisible, 1 = nominal, 1.5 = plus marqué.
  final double intensity;

  /// Affiche les deux halos radiaux (cobalt / emerald).
  final bool showHalos;

  /// Affiche les deux filets diagonaux terra.
  final bool showFilets;

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final bg = surface ??
        (isDark ? AppDarkColors.cream : AppColors.cream);
    // En dark, les points sont éclaircis (cobaltLight clair) avec une
    // opacité légèrement supérieure pour rester perceptibles sur fond
    // sombre. En light, on garde le cobalt brand sur cream.
    final dotColor = isDark ? AppDarkColors.cobaltLight : AppColors.cobalt;
    final dotOpacity = (isDark ? 0.055 : 0.038) * intensity;
    final filetColor = isDark ? AppDarkColors.terra : AppColors.terra;
    final filetOpacity = (isDark ? 0.08 : 0.06) * intensity;
    final haloCobalt = isDark ? AppDarkColors.cobalt : AppColors.cobalt;
    final haloEmerald = isDark ? AppDarkColors.emerald : AppColors.emerald;
    final haloOpacityCobalt = (isDark ? 0.14 : 0.10) * intensity;
    final haloOpacityEmerald = (isDark ? 0.10 : 0.08) * intensity;

    return Stack(
      children: [
        Positioned.fill(child: ColoredBox(color: bg)),

        // Motif hex de points . couche principale
        Positioned.fill(
          child: IgnorePointer(
            child: CustomPaint(
              painter: _HexDotsPainter(
                dotColor: dotColor,
                opacity: dotOpacity,
              ),
            ),
          ),
        ),

        // Filets éditoriaux diagonaux
        if (showFilets)
          Positioned.fill(
            child: IgnorePointer(
              child: CustomPaint(
                painter: _FiletsPainter(
                  color: filetColor,
                  opacity: filetOpacity,
                ),
              ),
            ),
          ),

        // Halos diffus aux angles
        if (showHalos) ...[
          Positioned(
            top: -140,
            right: -100,
            child: IgnorePointer(
              child: _Halo(
                color: haloCobalt.withValues(alpha: haloOpacityCobalt),
                size: 360,
              ),
            ),
          ),
          Positioned(
            bottom: -160,
            left: -120,
            child: IgnorePointer(
              child: _Halo(
                color: haloEmerald.withValues(alpha: haloOpacityEmerald),
                size: 320,
              ),
            ),
          ),
        ],

        Positioned.fill(child: child),
      ],
    );
  }
}


/// Peintre du motif hexagonal de micro-points.
/// Le résultat ressemble à un papier filigrané . pas un quadrillage,
/// mais un grain doux qui structure le fond.
class _HexDotsPainter extends CustomPainter {
  _HexDotsPainter({required this.dotColor, required this.opacity});

  final Color dotColor;
  final double opacity;

  static const _spacing = 28.0;
  static const _dotRadius = 1.1;

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = dotColor.withValues(alpha: opacity)
      ..style = PaintingStyle.fill;

    // Sin(60°) pour le pas vertical entre lignes hexagonales
    final rowStep = _spacing * math.sin(math.pi / 3);
    const colStep = _spacing;
    const halfCol = colStep / 2;

    int row = 0;
    for (double y = -rowStep; y < size.height + rowStep; y += rowStep) {
      final offsetX = (row % 2 == 0) ? 0.0 : halfCol;
      for (double x = -colStep; x < size.width + colStep; x += colStep) {
        canvas.drawCircle(Offset(x + offsetX, y), _dotRadius, paint);
      }
      row++;
    }
  }

  @override
  bool shouldRepaint(_HexDotsPainter old) =>
      old.dotColor != dotColor || old.opacity != opacity;
}


/// Deux filets fins diagonaux qui traversent l'écran . touche éditoriale
/// très discrète qui ajoute du rythme sans peser visuellement.
class _FiletsPainter extends CustomPainter {
  _FiletsPainter({required this.color, required this.opacity});

  final Color color;
  final double opacity;

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = color.withValues(alpha: opacity)
      ..strokeWidth = 1.0
      ..style = PaintingStyle.stroke;

    // Filet 1 . haut, pente douce
    canvas.drawLine(
      Offset(-20, size.height * 0.18),
      Offset(size.width + 20, size.height * 0.05),
      paint,
    );

    // Filet 2 . milieu/bas, sens inverse
    canvas.drawLine(
      Offset(-20, size.height * 0.62),
      Offset(size.width + 20, size.height * 0.78),
      paint,
    );
  }

  @override
  bool shouldRepaint(_FiletsPainter old) =>
      old.color != color || old.opacity != opacity;
}


/// Disque flou rayonnant . utilisé pour les deux halos d'angle.
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
          stops: const [0, 1],
        ),
      ),
    );
  }
}
