import 'package:flutter/material.dart';

import 'pattern_background.dart';

/// Fond signature standard pour TOUS les écrans de l'app.
///
/// Délègue à [PatternBackground] : grille hexagonale de micro-points
/// cobalt (~3 % d'opacité — façon fond conversation WhatsApp), deux
/// halos diffus aux angles, deux filets éditoriaux terra très discrets.
///
/// Cette indirection permet de tout faire évoluer en un seul endroit.
class BrandBackground extends StatelessWidget {
  const BrandBackground({
    super.key,
    required this.child,
    this.intensity = 1,
  });

  final Widget child;

  /// 0 = fond uni cream, 1 = nominal, 1.5 = plus marqué.
  final double intensity;

  @override
  Widget build(BuildContext context) {
    return PatternBackground(
      intensity: intensity,
      child: child,
    );
  }
}
