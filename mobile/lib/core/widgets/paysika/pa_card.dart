import 'package:flutter/material.dart';

import '../../../app/theme/paysika/pa_colors.dart';

/// Variante d'élévation d'une [PaCard].
///
/// - [elevated] : ombre signature douce . offset Y 6, blur 24, opacity 5 %.
///   Donne la profondeur premium sans tomber dans le Material lourdaud.
///   C'est le défaut.
/// - [flat] : aucune ombre, séparation par couleur de fond uniquement.
///   À utiliser sur les rows internes d'une autre PaCard (évite l'effet
///   d'ombres empilées) ou sur les surfaces sur fond gris foncé.
enum PaCardElevation { elevated, flat }


/// Card soft premium . fond paper, **radius 24**, **ombres flottantes douces**.
///
/// Brief : cards flottantes radius 24px avec
/// `0px 4px 12px rgba(0,0,0,0.04)` + `0px 2px 8px rgba(15,23,42,0.05)`.
/// L'effet « flottant » remplace le rendu flat néobank par du premium chic.
///
/// Sert de conteneur pour services, transactions groupées, info panels.
class PaCard extends StatelessWidget {
  const PaCard({
    super.key,
    required this.child,
    this.padding = const EdgeInsets.all(12),
    this.background,
    this.gradient,
    this.onTap,
    this.borderRadius,
    this.elevation = PaCardElevation.elevated,
  });

  final Widget child;
  final EdgeInsetsGeometry padding;

  /// Override de la couleur de fond (force une couleur unie, ignore le dégradé).
  final Color? background;

  /// Override du dégradé de fond. Par défaut, les cards `elevated` utilisent
  /// [PaGradients.cardSoft] (blanc → vert pâle) pour casser le tout-blanc.
  final Gradient? gradient;

  /// Active un InkWell + ripple si fourni.
  final VoidCallback? onTap;

  /// Override du radius si besoin (banner promo, etc.).
  final BorderRadius? borderRadius;

  /// Profondeur visuelle de la card.
  final PaCardElevation elevation;

  @override
  Widget build(BuildContext context) {
    final radius = borderRadius ?? BorderRadius.circular(10);
    final isElevated = elevation == PaCardElevation.elevated;

    // Fond : couleur forcée > dégradé fourni > dégradé vert par défaut (elevated)
    // > gris pâle uni (flat). Le dégradé vert subtil remplace le blanc plat.
    final Color? bgColor =
        background ?? (isElevated ? null : PaColors.cardBg);
    final Gradient? bgGradient = background != null
        ? null
        : (gradient ?? (isElevated ? PaGradients.cardSoft : null));

    final shadows = isElevated
        ? const <BoxShadow>[
            // 0px 4px 12px rgba(0,0,0,0.04)
            BoxShadow(
              color: Color(0x0A000000),
              blurRadius: 12,
              offset: Offset(0, 4),
            ),
            // 0px 2px 8px rgba(15,23,42,0.05)
            BoxShadow(
              color: Color(0x0D0F172A),
              blurRadius: 8,
              offset: Offset(0, 2),
            ),
          ]
        : <BoxShadow>[];

    final container = Container(
      decoration: BoxDecoration(
        color: bgColor,
        gradient: bgGradient,
        borderRadius: radius,
        boxShadow: shadows,
      ),
      child: Padding(padding: padding, child: child),
    );

    if (onTap == null) return container;

    return Material(
      color: Colors.transparent,
      borderRadius: radius,
      clipBehavior: Clip.antiAlias,
      child: Ink(
        decoration: BoxDecoration(
          color: bgColor,
          gradient: bgGradient,
          borderRadius: radius,
          boxShadow: shadows,
        ),
        child: InkWell(
          onTap: onTap,
          splashColor: PaColors.teal.withValues(alpha: 0.10),
          highlightColor: PaColors.teal.withValues(alpha: 0.05),
          child: Padding(padding: padding, child: child),
        ),
      ),
    );
  }
}
