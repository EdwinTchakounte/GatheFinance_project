import 'package:flutter/material.dart';

/// Palette **sombre** Gathe Finance — miroir de [AppColors], avec les
/// mêmes noms d'usage (paper, cream, ink*) mais des valeurs adaptées à
/// un fond profond cobalt-noirci.
///
/// Règle : pas de noir pur ici non plus — le fond le plus sombre est
/// `cream` (#101626), un cobalt très désaturé. Les accents brand
/// (cobalt, emerald, terra) sont légèrement éclaircis pour rester
/// lisibles sur fond sombre.
///
/// Cette classe est consommée par `AppTheme.dark` pour bâtir le
/// `ColorScheme.dark`. Les pages custom qui référencent encore
/// `AppColors.X` en dur continuent de fonctionner en light tant
/// qu'elles n'ont pas migré vers `Theme.of(context).colorScheme`.
class AppDarkColors {
  AppDarkColors._();

  // --- Primaires (légèrement éclaircis pour le contraste sombre) ----------
  static const cobalt = Color(0xFF5B8BD0); // primary on dark
  static const cobaltDark = Color(0xFF3D6FB4);
  static const cobaltLight = Color(0xFF7AA4DC);
  static const cobaltSurface = Color(0xFF1A2942); // surface tinted cobalt

  static const emerald = Color(0xFF5BC056);
  static const emeraldDark = Color(0xFF3DA13A);
  static const emeraldSurface = Color(0xFF1A2E1A);

  static const terra = Color(0xFFD58A4F);
  static const terraDark = Color(0xFFB36F36);
  static const terraSurface = Color(0xFF3A2A1A);

  // --- Neutres (inverses) -----------------------------------------------
  static const cream = Color(0xFF101626); // app background (very dark cobalt)
  static const paper = Color(0xFF161D30); // card background
  static const inkDark = Color(0xFFF2F0EA); // strongest text on dark
  static const ink = Color(0xFFD8DAE0);
  static const inkSoft = Color(0xFFAAB0C0);
  static const inkMuted = Color(0xFF7A8090);
  static const inkFaint = Color(0xFF555B6A);
  static const line = Color(0xFF2A3142); // borders/separators on dark

  // --- États -----------------------------------------------------------
  static const danger = Color(0xFFE45A5A);
  static const dangerSurface = Color(0xFF3A1A1A);
  static const warning = Color(0xFFE5A847);
  static const warningSurface = Color(0xFF3A2A14);
  static const info = cobalt;
  static const infoSurface = cobaltSurface;
}
