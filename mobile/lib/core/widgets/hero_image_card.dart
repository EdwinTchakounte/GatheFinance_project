import 'package:flutter/material.dart';

import '../../app/theme/app_colors.dart';
import '../../app/theme/app_radii.dart';
import '../../app/theme/app_shadows.dart';
import '../../app/theme/app_typography.dart';

/// Carte image avec overlay éditorial . utilisée pour les blocs hero
/// (onboarding, banners, sections « pourquoi épargner », etc.).
///
/// - L'image asset est cadrée en `BoxFit.cover`
/// - Un voile sombre cobalt monte du bas vers le haut pour rendre le texte lisible
/// - L'eyebrow et le titre éditorial restent sobres
class HeroImageCard extends StatelessWidget {
  const HeroImageCard({
    super.key,
    required this.imageAsset,
    required this.eyebrow,
    required this.title,
    this.subtitle,
    this.height = 200,
    this.onTap,
  });

  final String imageAsset;
  final String eyebrow;
  final String title;
  final String? subtitle;
  final double height;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final card = ClipRRect(
      borderRadius: AppRadii.cardHero,
      child: Stack(
        fit: StackFit.expand,
        children: [
          // Image de fond
          Image.asset(
            imageAsset,
            fit: BoxFit.cover,
            filterQuality: FilterQuality.medium,
          ),

          // Voile sombre cobalt en bas pour lisibilité
          Positioned.fill(
            child: DecoratedBox(
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  begin: Alignment.topCenter,
                  end: Alignment.bottomCenter,
                  colors: [
                    AppColors.cobaltDark.withValues(alpha: 0.0),
                    AppColors.cobaltDark.withValues(alpha: 0.3),
                    AppColors.cobaltDark.withValues(alpha: 0.78),
                  ],
                  stops: const [0, 0.45, 1],
                ),
              ),
            ),
          ),

          // Trait coopératif terra/emerald . micro-élément graphique
          Positioned(
            top: 16,
            left: 18,
            child: Container(
              height: 3,
              width: 28,
              decoration: BoxDecoration(
                color: AppColors.emerald,
                borderRadius: BorderRadius.circular(2),
              ),
            ),
          ),

          // Texte
          Positioned(
            left: 20,
            right: 20,
            bottom: 18,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  eyebrow.toUpperCase(),
                  style: AppTypography.eyebrow.copyWith(
                    color: AppColors.emerald,
                    fontSize: 11,
                  ),
                ),
                const SizedBox(height: 6),
                Text(
                  title,
                  style: AppTypography.displayLarge.copyWith(
                    color: Colors.white,
                    fontSize: 26,
                    height: 1.1,
                  ),
                ),
                if (subtitle != null) ...[
                  const SizedBox(height: 6),
                  Text(
                    subtitle!,
                    style: AppTypography.bodyMedium.copyWith(
                      color: Colors.white.withValues(alpha: 0.86),
                    ),
                  ),
                ],
              ],
            ),
          ),
        ],
      ),
    );

    return Container(
      height: height,
      decoration: BoxDecoration(
        borderRadius: AppRadii.cardHero,
        boxShadow: AppShadows.medium,
      ),
      child: onTap == null
          ? card
          : Material(
              color: Colors.transparent,
              borderRadius: AppRadii.cardHero,
              child: InkWell(
                borderRadius: AppRadii.cardHero,
                onTap: onTap,
                child: card,
              ),
            ),
    );
  }
}
