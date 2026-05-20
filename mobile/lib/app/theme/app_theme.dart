import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'app_colors.dart';
import 'app_colors_dark.dart';
import 'app_page_transitions.dart';
import 'app_radii.dart';
import 'app_typography.dart';

/// Thème Material 3 customisé : ColorScheme dérivée du cobalt, surfaces cream,
/// tous les composants par défaut alignés sur le design system Gathe.
///
/// Deux variantes :
///  - [light] (mode clair) — surfaces cream/paper, ink sombre
///  - [dark]  (mode sombre) — surfaces cobalt-très-foncées, ink clair
///
/// Le `themeMode` (system/light/dark) est piloté par
/// `theme_mode_notifier.dart` et persisté en SharedPreferences.
class AppTheme {
  AppTheme._();

  static SystemUiOverlayStyle get _systemOverlayLight =>
      const SystemUiOverlayStyle(
        statusBarColor: Colors.transparent,
        statusBarIconBrightness: Brightness.dark,
        systemNavigationBarColor: AppColors.cream,
        systemNavigationBarIconBrightness: Brightness.dark,
      );

  static SystemUiOverlayStyle get _systemOverlayDark =>
      const SystemUiOverlayStyle(
        statusBarColor: Colors.transparent,
        statusBarIconBrightness: Brightness.light,
        systemNavigationBarColor: AppDarkColors.cream,
        systemNavigationBarIconBrightness: Brightness.light,
      );

  static ThemeData get light => _build(brightness: Brightness.light);

  static ThemeData get dark => _build(brightness: Brightness.dark);

  static ThemeData _build({required Brightness brightness}) {
    final isDark = brightness == Brightness.dark;

    // Sélection de la palette adaptée
    final cobalt = isDark ? AppDarkColors.cobalt : AppColors.cobalt;
    final emerald = isDark ? AppDarkColors.emerald : AppColors.emerald;
    final terra = isDark ? AppDarkColors.terra : AppColors.terra;
    final cobaltSurface =
        isDark ? AppDarkColors.cobaltSurface : AppColors.cobaltSurface;
    final paper = isDark ? AppDarkColors.paper : AppColors.paper;
    final cream = isDark ? AppDarkColors.cream : AppColors.cream;
    final inkDark = isDark ? AppDarkColors.inkDark : AppColors.inkDark;
    final ink = isDark ? AppDarkColors.ink : AppColors.ink;
    final inkSoft = isDark ? AppDarkColors.inkSoft : AppColors.inkSoft;
    final inkMuted = isDark ? AppDarkColors.inkMuted : AppColors.inkMuted;
    final line = isDark ? AppDarkColors.line : AppColors.line;
    final danger = isDark ? AppDarkColors.danger : AppColors.danger;

    final colorScheme = ColorScheme.fromSeed(
      seedColor: cobalt,
      brightness: brightness,
      primary: cobalt,
      onPrimary: Colors.white,
      secondary: emerald,
      onSecondary: Colors.white,
      tertiary: terra,
      onTertiary: Colors.white,
      surface: paper,
      onSurface: inkDark,
      surfaceContainerHighest: cobaltSurface,
      error: danger,
      onError: Colors.white,
      outline: line,
      outlineVariant: line,
    );

    final textTheme = TextTheme(
      displayLarge: AppTypography.displayLarge.copyWith(color: inkDark),
      displayMedium: AppTypography.displayLarge.copyWith(color: inkDark),
      headlineLarge: AppTypography.headingLarge.copyWith(color: inkDark),
      headlineMedium: AppTypography.headingMedium.copyWith(color: inkDark),
      headlineSmall: AppTypography.headingSmall.copyWith(color: inkDark),
      titleLarge: AppTypography.headingMedium.copyWith(color: inkDark),
      titleMedium: AppTypography.headingSmall.copyWith(color: inkDark),
      titleSmall: AppTypography.labelLarge.copyWith(color: inkDark),
      bodyLarge: AppTypography.bodyLarge.copyWith(color: ink),
      bodyMedium: AppTypography.bodyMedium.copyWith(color: ink),
      bodySmall: AppTypography.bodySmall.copyWith(color: inkSoft),
      labelLarge: AppTypography.labelLarge.copyWith(color: inkDark),
      labelMedium: AppTypography.labelMedium.copyWith(color: inkDark),
      labelSmall: AppTypography.bodySmall.copyWith(color: inkSoft),
    );

    return ThemeData(
      useMaterial3: true,
      brightness: brightness,
      colorScheme: colorScheme,
      scaffoldBackgroundColor: cream,
      canvasColor: cream,
      splashFactory: InkRipple.splashFactory,
      pageTransitionsTheme: AppPageTransitions.theme,
      textTheme: textTheme,
      iconTheme: IconThemeData(color: ink, size: 20),
      dividerTheme: DividerThemeData(
        color: line,
        thickness: 1,
        space: 1,
      ),

      // AppBar — fond cream qui se fond, pas d'élévation
      appBarTheme: AppBarTheme(
        backgroundColor: cream,
        elevation: 0,
        scrolledUnderElevation: 0,
        surfaceTintColor: Colors.transparent,
        centerTitle: false,
        titleSpacing: 20,
        titleTextStyle: AppTypography.headingMedium.copyWith(color: inkDark),
        iconTheme: IconThemeData(color: inkDark, size: 22),
        systemOverlayStyle: isDark ? _systemOverlayDark : _systemOverlayLight,
      ),

      // Cards (API Flutter 3.27+ : CardThemeData)
      cardTheme: CardThemeData(
        color: paper,
        elevation: 0,
        margin: EdgeInsets.zero,
        shape: const RoundedRectangleBorder(borderRadius: AppRadii.card),
        surfaceTintColor: Colors.transparent,
        clipBehavior: Clip.antiAlias,
      ),

      // Boutons primaires — pill cobalt
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          backgroundColor: cobalt,
          foregroundColor: Colors.white,
          textStyle: AppTypography.labelLarge,
          minimumSize: const Size(0, 52),
          shape: const RoundedRectangleBorder(borderRadius: AppRadii.button),
          padding: const EdgeInsets.symmetric(horizontal: 24),
        ),
      ),

      // Secondaire — outlined cobalt
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: cobalt,
          side: BorderSide(color: cobalt, width: 1.5),
          textStyle: AppTypography.labelLarge,
          minimumSize: const Size(0, 52),
          shape: const RoundedRectangleBorder(borderRadius: AppRadii.button),
          padding: const EdgeInsets.symmetric(horizontal: 24),
        ),
      ),

      // Texte / ghost
      textButtonTheme: TextButtonThemeData(
        style: TextButton.styleFrom(
          foregroundColor: cobalt,
          textStyle: AppTypography.labelMedium,
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
        ),
      ),

      // Champs de formulaire
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: paper,
        contentPadding:
            const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
        hintStyle: AppTypography.bodyMedium.copyWith(color: inkMuted),
        labelStyle: AppTypography.bodyMedium.copyWith(color: inkSoft),
        floatingLabelStyle:
            AppTypography.labelMedium.copyWith(color: cobalt),
        border: OutlineInputBorder(
          borderRadius: AppRadii.field,
          borderSide: BorderSide(color: line),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: AppRadii.field,
          borderSide: BorderSide(color: line),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: AppRadii.field,
          borderSide: BorderSide(color: cobalt, width: 1.6),
        ),
        errorBorder: OutlineInputBorder(
          borderRadius: AppRadii.field,
          borderSide: BorderSide(color: danger),
        ),
        focusedErrorBorder: OutlineInputBorder(
          borderRadius: AppRadii.field,
          borderSide: BorderSide(color: danger, width: 1.6),
        ),
        errorStyle: AppTypography.bodySmall.copyWith(color: danger),
      ),

      // BottomNav
      navigationBarTheme: NavigationBarThemeData(
        backgroundColor: paper,
        elevation: 0,
        indicatorColor: cobaltSurface,
        labelTextStyle: WidgetStatePropertyAll(
          AppTypography.labelMedium.copyWith(fontSize: 11.5, color: inkDark),
        ),
        iconTheme: WidgetStateProperty.resolveWith(
          (states) {
            final selected = states.contains(WidgetState.selected);
            return IconThemeData(
              color: selected ? cobalt : inkMuted,
              size: 24,
            );
          },
        ),
        height: 72,
        labelBehavior: NavigationDestinationLabelBehavior.alwaysShow,
      ),

      // BottomSheet
      bottomSheetTheme: BottomSheetThemeData(
        backgroundColor: paper,
        surfaceTintColor: Colors.transparent,
        elevation: 0,
        shape: const RoundedRectangleBorder(borderRadius: AppRadii.sheet),
      ),

      // SnackBar
      snackBarTheme: SnackBarThemeData(
        backgroundColor: isDark ? AppDarkColors.paper : AppColors.inkDark,
        contentTextStyle:
            AppTypography.bodyMedium.copyWith(color: Colors.white),
        behavior: SnackBarBehavior.floating,
        shape: const RoundedRectangleBorder(borderRadius: AppRadii.card),
        actionTextColor: emerald,
      ),

      // Chips / pills
      chipTheme: ChipThemeData(
        backgroundColor: cobaltSurface,
        labelStyle: AppTypography.labelMedium.copyWith(color: cobalt),
        side: BorderSide.none,
        shape: const RoundedRectangleBorder(borderRadius: AppRadii.chip),
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      ),

      // Progress
      progressIndicatorTheme: ProgressIndicatorThemeData(
        color: cobalt,
        linearTrackColor: line,
      ),
    );
  }
}
