import 'package:flutter/material.dart';

/// Palette officielle GATHE Finance — alignée sur le design system web.
///
/// Règle absolue : **pas de noir pur**. L'encre la plus sombre est `inkDark`
/// (#0b1320), un cobalt très désaturé. Le marron `terra` remplace le noir
/// partout où on aurait besoin d'un accent chaud.
class AppColors {
  AppColors._();

  // --- Primaires (brand) ----------------------------------------------------
  static const cobalt = Color(0xFF0E4D92); // primary
  static const cobaltDark = Color(0xFF0A3C72);
  static const cobaltLight = Color(0xFF1E68B5);
  static const cobaltSurface = Color(0xFFE7EEF8); // bg subtle

  static const emerald = Color(0xFF3AAA35); // success / positive
  static const emeraldDark = Color(0xFF2D8C29);
  static const emeraldSurface = Color(0xFFE6F4E5);

  static const terra = Color(0xFFC2742A); // warm accent (replaces black)
  static const terraDark = Color(0xFF8C531E);
  static const terraSurface = Color(0xFFF6ECDF);

  // --- Neutres -------------------------------------------------------------
  static const cream = Color(0xFFFAF6EF); // app background
  static const paper = Color(0xFFFFFFFF); // card background
  static const inkDark = Color(0xFF0B1320); // strongest text (cobalt-tinted)
  static const ink = Color(0xFF2A3142);
  static const inkSoft = Color(0xFF5A6378);
  static const inkMuted = Color(0xFF8A92A4);
  static const inkFaint = Color(0xFFB8BEC9);
  static const line = Color(0xFFE7E4DC); // borders/separators

  // --- États ---------------------------------------------------------------
  static const danger = Color(0xFFBA2121);
  static const dangerSurface = Color(0xFFFCE8E8);
  static const warning = Color(0xFFD5912E);
  static const warningSurface = Color(0xFFFBF1DF);
  static const info = cobalt;
  static const infoSurface = cobaltSurface;
}
