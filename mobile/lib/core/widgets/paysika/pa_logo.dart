import 'package:flutter/material.dart';

/// Marque Gathe . `logo_clean.png` posé en haut-gauche de chaque page
/// principale (Home, Crédit, Carnet, Profil). Hauteur ~ 28 par défaut.
class PaLogo extends StatelessWidget {
  const PaLogo({super.key, this.height = 28, this.semanticLabel = 'Gathe Finance'});

  final double height;
  final String semanticLabel;

  @override
  Widget build(BuildContext context) {
    return Image.asset(
      'assets/images/logo_clean.png',
      height: height,
      fit: BoxFit.contain,
      semanticLabel: semanticLabel,
      filterQuality: FilterQuality.high,
    );
  }
}
