import 'package:flutter/material.dart';

import '../../app/theme/app_colors.dart';
import '../../app/theme/app_radii.dart';

/// Variantes visuelles d'[AppCard].
///
/// - `flat`     : surface paper, ombre douce, rayon 20pt . pour les listes
///                et les blocs secondaires
/// - `glass`    : surface paper avec halo blanc + filet inner-light en haut,
///                rayon 24pt . pour les blocs informatifs immersifs
/// - `hero`     : rayon 28pt, ombre cobalt amplifiée multi-couches, halo
///                blanc top-edge . pour les blocs majeurs (solde, état…)
/// - `gradient` : surface dégradée custom (utilise [AppCard.gradient]),
///                ombre forte, rayon 28pt . pour les héros impactants
///                façon Spotify/Canal+ (cobalt → cobaltDark, etc.)
enum AppCardVariant { flat, glass, hero, gradient }


/// Carte moderne . inspirée Spotify / Canal+ : ombres multi-couches teintées
/// cobalt, halo d'arête supérieure pour la profondeur, possibilité de
/// surface en gradient. Remplace l'ancienne carte plate uniforme.
///
/// Compat : `hero: true` est équivalent à `variant: AppCardVariant.hero`.
/// Si `variant` est fourni, il prime sur `hero`.
class AppCard extends StatefulWidget {
  const AppCard({
    super.key,
    required this.child,
    this.padding = const EdgeInsets.all(20),
    this.onTap,
    this.hero = false,
    this.variant,
    this.color,
    this.border,
    this.gradient,
    this.accentColor,
    this.dense = false,
  });

  final Widget child;
  final EdgeInsetsGeometry padding;
  final VoidCallback? onTap;

  /// Compat ancien code (= variant hero).
  final bool hero;

  /// Variante explicite . prend le pas sur `hero` si fournie.
  final AppCardVariant? variant;

  final Color? color;
  final BoxBorder? border;

  /// Gradient custom . implique automatiquement `variant: gradient`.
  final Gradient? gradient;

  /// Filet de couleur 3px à gauche pour catégoriser. `null` = pas de filet.
  final Color? accentColor;

  /// Réduit le rayon (16pt) pour les cards très denses (listes serrées).
  final bool dense;

  @override
  State<AppCard> createState() => _AppCardState();
}

class _AppCardState extends State<AppCard> {
  bool _pressed = false;

  AppCardVariant get _variant {
    if (widget.gradient != null) return AppCardVariant.gradient;
    if (widget.variant != null) return widget.variant!;
    if (widget.hero) return AppCardVariant.hero;
    return AppCardVariant.flat;
  }

  BorderRadius get _radius {
    if (widget.dense) return const BorderRadius.all(AppRadii.r16);
    switch (_variant) {
      case AppCardVariant.flat:
        return AppRadii.card;
      case AppCardVariant.glass:
        return const BorderRadius.all(AppRadii.r16);
      case AppCardVariant.hero:
      case AppCardVariant.gradient:
        return AppRadii.cardHero;
    }
  }

  List<BoxShadow> get _shadows {
    switch (_variant) {
      case AppCardVariant.flat:
        return [
          BoxShadow(
            color: AppColors.cobalt.withValues(alpha: 0.045),
            blurRadius: 12,
            offset: const Offset(0, 4),
          ),
          BoxShadow(
            color: AppColors.cobalt.withValues(alpha: 0.02),
            blurRadius: 2,
            offset: const Offset(0, 1),
          ),
        ];
      case AppCardVariant.glass:
        return [
          BoxShadow(
            color: AppColors.cobalt.withValues(alpha: 0.07),
            blurRadius: 22,
            offset: const Offset(0, 10),
          ),
          BoxShadow(
            color: AppColors.cobalt.withValues(alpha: 0.025),
            blurRadius: 3,
            offset: const Offset(0, 1),
          ),
        ];
      case AppCardVariant.hero:
        return [
          BoxShadow(
            color: AppColors.cobalt.withValues(alpha: 0.10),
            blurRadius: 32,
            offset: const Offset(0, 14),
          ),
          BoxShadow(
            color: AppColors.cobalt.withValues(alpha: 0.04),
            blurRadius: 4,
            offset: const Offset(0, 2),
          ),
        ];
      case AppCardVariant.gradient:
        return [
          BoxShadow(
            color: AppColors.cobalt.withValues(alpha: 0.18),
            blurRadius: 38,
            offset: const Offset(0, 18),
          ),
          BoxShadow(
            color: AppColors.cobalt.withValues(alpha: 0.06),
            blurRadius: 6,
            offset: const Offset(0, 2),
          ),
        ];
    }
  }

  Color? _surfaceColor(BuildContext context) {
    if (widget.color != null) return widget.color;
    if (_variant == AppCardVariant.gradient) return null; // gradient prend la main
    // Surface alignée sur le thème : paper en light, paper-dark en dark.
    return Theme.of(context).colorScheme.surface;
  }

  /// Refonte visuelle 2026 : la variante `glass` n'est plus un rectangle blanc
  /// plat mais un panneau doux, dégradé surface → tuile mint pâle. Adoucit
  /// l'empilement de cartes (profil) sans en changer la structure. `null` pour
  /// les autres variantes (elles gardent leur surface / gradient propre).
  Gradient? _autoGradient(BuildContext context) {
    if (widget.color != null || _variant != AppCardVariant.glass) return null;
    final base = Theme.of(context).colorScheme.surface;
    final tint = Color.alphaBlend(
      const Color(0xFF00B894).withValues(alpha: 0.055), // teal marque
      base,
    );
    return LinearGradient(
      begin: Alignment.topLeft,
      end: Alignment.bottomRight,
      colors: [base, tint],
    );
  }

  @override
  Widget build(BuildContext context) {
    final base = AnimatedContainer(
      duration: const Duration(milliseconds: 160),
      curve: Curves.easeOut,
      decoration: BoxDecoration(
        color: _surfaceColor(context),
        gradient: widget.gradient ?? _autoGradient(context),
        borderRadius: _radius,
        boxShadow: _shadows,
        border: widget.border,
      ),
      child: Stack(
        children: [
          // Highlight d'arête supérieure . donne la profondeur "Spotify"
          if (_variant != AppCardVariant.flat)
            Positioned(
              top: 0,
              left: 0,
              right: 0,
              height: 1.2,
              child: DecoratedBox(
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.only(
                    topLeft: _radius.topLeft,
                    topRight: _radius.topRight,
                  ),
                  gradient: LinearGradient(
                    begin: Alignment.centerLeft,
                    end: Alignment.centerRight,
                    colors: [
                      Colors.white.withValues(alpha: 0),
                      Colors.white.withValues(
                        alpha: _variant == AppCardVariant.gradient ? 0.35 : 0.7,
                      ),
                      Colors.white.withValues(alpha: 0),
                    ],
                  ),
                ),
              ),
            ),

          // Filet accent vertical à gauche . catégorise (membre, état…)
          if (widget.accentColor != null)
            Positioned(
              top: 14,
              bottom: 14,
              left: 0,
              child: Container(
                width: 3,
                decoration: BoxDecoration(
                  color: widget.accentColor,
                  borderRadius: const BorderRadius.only(
                    topRight: Radius.circular(2),
                    bottomRight: Radius.circular(2),
                  ),
                ),
              ),
            ),

          // Le contenu
          Padding(padding: widget.padding, child: widget.child),
        ],
      ),
    );

    final clipped = ClipRRect(borderRadius: _radius, child: base);

    if (widget.onTap == null) return clipped;

    return AnimatedScale(
      scale: _pressed ? 0.985 : 1.0,
      duration: const Duration(milliseconds: 100),
      curve: Curves.easeOutCubic,
      child: Material(
        color: Colors.transparent,
        borderRadius: _radius,
        child: InkWell(
          onTap: widget.onTap,
          onHighlightChanged: (v) {
            if (mounted) setState(() => _pressed = v);
          },
          borderRadius: _radius,
          splashColor: AppColors.cobalt.withValues(alpha: 0.05),
          highlightColor: AppColors.cobalt.withValues(alpha: 0.03),
          child: clipped,
        ),
      ),
    );
  }
}


/// Helper . gradient signature primaire (cobalt → cobaltDark) prêt à
/// l'emploi pour les héros majeurs (solde, état officiel, etc.).
class AppCardGradients {
  AppCardGradients._();

  static const cobaltDeep = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [Color(0xFF1E68B5), Color(0xFF0A3C72)],
  );

  static const emeraldFresh = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [Color(0xFF3AAA35), Color(0xFF2D8C29)],
  );

  static const terraWarm = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [Color(0xFFC2742A), Color(0xFF8C531E)],
  );

  /// Gradient subtil pour cards "informatives" sur fond cream . reste
  /// très clair, juste un soupçon de teinte.
  static const creamSoft = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [Color(0xFFFFFFFF), Color(0xFFFBF7EF)],
  );
}
