
import 'package:flutter/material.dart';

import 'app_colors.dart';

/// Typo en miroir du web :
///   - **Inter** pour UI (corps, boutons, labels)
///   - **Lora** (serif) pour les chiffres XAF et les titres éditoriaux
///   - **JetBrains Mono** pour numéros membre / références
///
/// ⚠️ Polices **bundlées en assets** (pubspec `fonts:`), PAS via réseau :
/// l'appli tourne hors-ligne. Ce sont des *variable fonts* → le poids passe
/// par [FontVariation] pour s'appliquer réellement.
///
/// **Règle dark-aware** : les getters ne fixent PAS la couleur du texte
/// (sauf accents brand comme `eyebrow`). La couleur vient du `Theme.textTheme`
/// ou explicitement via `.copyWith(color: ...)` au site d'usage.
class AppTypography {
  AppTypography._();

  static TextStyle _v(
    String family,
    double size,
    FontWeight weight, {
    double letterSpacing = -0.1,
    double height = 1.3,
    Color? color,
  }) =>
      TextStyle(
        fontFamily: family,
        fontSize: size,
        fontWeight: weight,
        fontVariations: [FontVariation('wght', weight.value.toDouble())],
        letterSpacing: letterSpacing,
        height: height,
        color: color,
      );

  // Display — réservé aux grands montants XAF / hero numbers (Lora serif)
  static TextStyle get displayXAF =>
      _v('Lora', 48, FontWeight.w500, letterSpacing: -0.4, height: 1.15);

  static TextStyle get displayLarge =>
      _v('Lora', 34, FontWeight.w500, letterSpacing: -0.4, height: 1.15);

  // Headings — pas de color, laissée au textTheme
  static TextStyle get headingLarge => _v('Inter', 24, FontWeight.w700);
  static TextStyle get headingMedium => _v('Inter', 20, FontWeight.w600);
  static TextStyle get headingSmall => _v('Inter', 17, FontWeight.w600);

  // Body — pas de color, laissée au textTheme
  static TextStyle get bodyLarge => _v('Inter', 16, FontWeight.w500);
  static TextStyle get bodyMedium => _v('Inter', 14.5, FontWeight.w500);
  static TextStyle get bodySmall => _v('Inter', 13, FontWeight.w500);

  // Eyebrow — accent brand (terraDark) — OK sur clair ET sombre.
  static TextStyle get eyebrow => _v('Inter', 11, FontWeight.w700,
      letterSpacing: 1.6, color: AppColors.terraDark,);

  // Label / boutons — pas de color
  static TextStyle get labelLarge => _v('Inter', 15, FontWeight.w600);
  static TextStyle get labelMedium => _v('Inter', 13.5, FontWeight.w600);

  // Mono — pour numéros membre, références (pas de color)
  static TextStyle get monoSmall => _v('JetBrains Mono', 12.5, FontWeight.w500);
}
