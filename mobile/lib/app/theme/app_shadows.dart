import 'package:flutter/material.dart';

import 'app_colors.dart';

/// Ombres douces — toujours teintées cobalt et basses opacités pour rester
/// sobres (jamais d'ombre noire dure). Trois niveaux suffisent.
class AppShadows {
  AppShadows._();

  static final low = [
    BoxShadow(
      color: AppColors.cobalt.withValues(alpha: 0.05),
      blurRadius: 8,
      offset: const Offset(0, 2),
    ),
  ];

  static final medium = [
    BoxShadow(
      color: AppColors.cobalt.withValues(alpha: 0.08),
      blurRadius: 18,
      offset: const Offset(0, 6),
    ),
  ];

  static final high = [
    BoxShadow(
      color: AppColors.cobalt.withValues(alpha: 0.12),
      blurRadius: 32,
      offset: const Offset(0, 12),
    ),
  ];
}
