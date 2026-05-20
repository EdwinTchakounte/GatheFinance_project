import 'dart:ui' show FontVariation;

import 'package:flutter/material.dart';

import 'pa_colors.dart';

/// Typographie premium « luxury fintech » — **Sora** (moderne, épuré).
///
/// **Sora** pour titres, hero et montants : géométrique contemporaine, chiffres
/// très nets, et — avec des poids allégés (w600 max sur les titres) — moins
/// imposante que Poppins. **Inter** pour le corps (lisibilité maximale).
///
/// ⚠️ Polices **bundlées en assets** (cf. pubspec `fonts:`), PAS via réseau :
/// l'appli tourne hors-ligne et GoogleFonts retombait sinon sur Roboto.
/// Ce sont des *variable fonts* → le poids est piloté par [FontVariation].
class PaText {
  PaText._();

  static const _sora = 'Sora';
  static const _inter = 'Inter';

  /// Construit un TextStyle avec axe de poids variable correctement appliqué.
  static TextStyle _styled({
    required String family,
    required double size,
    required FontWeight weight,
    required Color color,
    double? letterSpacing,
    double? height,
  }) =>
      TextStyle(
        fontFamily: family,
        fontSize: size,
        fontWeight: weight,
        fontVariations: [FontVariation('wght', weight.value.toDouble())],
        color: color,
        letterSpacing: letterSpacing,
        height: height,
      );

  // ── Display / titres (Sora) ─────────────────────────────────────────────
  /// Gros titres et hero balance — Sora SemiBold (poids allégé, pas lourd).
  static TextStyle display({
    double size = 32,
    FontWeight weight = FontWeight.w600,
    Color color = PaColors.inkPrimary,
    double letterSpacing = -0.6,
    double? height,
  }) =>
      _styled(
        family: _sora,
        size: size,
        weight: weight,
        color: color,
        letterSpacing: letterSpacing,
        height: height,
      );

  /// Titres de section / cards — Sora SemiBold.
  static TextStyle heading({
    double size = 19,
    FontWeight weight = FontWeight.w600,
    Color color = PaColors.inkPrimary,
    double letterSpacing = -0.3,
  }) =>
      _styled(
        family: _sora,
        size: size,
        weight: weight,
        color: color,
        letterSpacing: letterSpacing,
      );

  // ── Montants (Sora — figures nettes) ─────────────────────────────────────
  /// Chiffres monétaires — Sora, SemiBold par défaut, lettres resserrées.
  static TextStyle amount({
    double size = 24,
    FontWeight weight = FontWeight.w600,
    Color color = PaColors.inkPrimary,
    double letterSpacing = -0.5,
    double? height,
  }) =>
      _styled(
        family: _sora,
        size: size,
        weight: weight,
        color: color,
        letterSpacing: letterSpacing,
        height: height,
      );

  // ── Corps (Inter) ─────────────────────────────────────────────────────────
  static TextStyle body({
    double size = 14,
    FontWeight weight = FontWeight.w400,
    Color color = PaColors.inkSecondary,
    double height = 1.45,
  }) =>
      _styled(
        family: _inter,
        size: size,
        weight: weight,
        color: color,
        height: height,
      );

  static TextStyle label({
    double size = 13,
    FontWeight weight = FontWeight.w600,
    Color color = PaColors.inkPrimary,
    double letterSpacing = 0,
  }) =>
      _styled(
        family: _inter,
        size: size,
        weight: weight,
        color: color,
        letterSpacing: letterSpacing,
      );

  /// Eyebrow — petit label maj. espacé (sections).
  static TextStyle eyebrow({Color color = PaColors.inkMuted}) => _styled(
        family: _inter,
        size: 11,
        weight: FontWeight.w700,
        color: color,
        letterSpacing: 1.4,
      );
}
