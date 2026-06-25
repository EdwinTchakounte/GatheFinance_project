import 'package:flutter/material.dart';

import '../../../app/theme/paysika/pa_colors.dart';
import 'pa_logo.dart';

/// Hero brand utilisé en haut de Login, MemberInfoSheet et
/// MembershipFormSheet.
///
/// - **Gradient aurore** vert→bleu→navy (immersion couleurs logo).
/// - **Halos radiaux** blancs : un en haut-droite, un plus bas-gauche, pour
///   "embellir" la surface bleue (pas une plate).
/// - **Coins bas arrondis** (vague) pour la transition vers le crème.
/// - Le logo n'est pas inclus ici . utiliser `PaBrandHeroBridgeLogo` posé
///   en bas (chevauchement) dans un `Stack(clipBehavior: Clip.none)`.
class PaBrandHero extends StatelessWidget {
  const PaBrandHero({
    super.key,
    required this.child,
    this.bottomRadius = 32,
    this.contentPadding = const EdgeInsets.fromLTRB(20, 16, 20, 38),
  });

  /// Contenu posé au-dessus du gradient (titre, baseline…). Le caller doit
  /// prévoir un padding bottom suffisant pour que le logo "pont" ne recouvre
  /// pas son contenu.
  final Widget child;

  final double bottomRadius;
  final EdgeInsetsGeometry contentPadding;

  @override
  Widget build(BuildContext context) {
    return ClipRRect(
      borderRadius: BorderRadius.only(
        bottomLeft: Radius.circular(bottomRadius),
        bottomRight: Radius.circular(bottomRadius),
      ),
      child: Stack(
        children: [
          // ── Fond gradient aurore vert → bleu → navy ──
          Positioned.fill(
            child: DecoratedBox(
              decoration: BoxDecoration(
                gradient: const LinearGradient(
                  begin: Alignment(-1, -0.6),
                  end: Alignment(1, 0.8),
                  colors: [
                    PaColors.teal,       // vert logo
                    PaColors.blue,       // bleu royal logo
                    PaColors.navy,       // bleu nuit logo
                  ],
                  stops: [0.0, 0.55, 1.0],
                ),
              ),
            ),
          ),
          // ── Halo top-right (lumière premium) ──
          Positioned(
            top: -60,
            right: -50,
            child: IgnorePointer(
              child: Container(
                width: 240,
                height: 240,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  gradient: RadialGradient(
                    colors: [
                      Colors.white.withValues(alpha: 0.22),
                      Colors.white.withValues(alpha: 0),
                    ],
                  ),
                ),
              ),
            ),
          ),
          // ── Halo top-left (highlight subtil) ──
          Positioned(
            top: -20,
            left: -30,
            child: IgnorePointer(
              child: Container(
                width: 160,
                height: 160,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  gradient: RadialGradient(
                    colors: [
                      Colors.white.withValues(alpha: 0.14),
                      Colors.white.withValues(alpha: 0),
                    ],
                  ),
                ),
              ),
            ),
          ),
          // ── Filet horizontal subtil avant la courbe ──
          Positioned(
            left: 0,
            right: 0,
            bottom: 28,
            child: IgnorePointer(
              child: Container(
                height: 1,
                decoration: BoxDecoration(
                  gradient: LinearGradient(
                    colors: [
                      Colors.white.withValues(alpha: 0),
                      Colors.white.withValues(alpha: 0.18),
                      Colors.white.withValues(alpha: 0),
                    ],
                  ),
                ),
              ),
            ),
          ),
          // ── Contenu (titre, baseline) ──
          SafeArea(
            bottom: false,
            child: Padding(padding: contentPadding, child: child),
          ),
        ],
      ),
    );
  }
}


/// Logo "pont" qui chevauche la frontière hero/cream. Cercle blanc avec
/// logo Gathe à l'intérieur, ombre douce. Placer dans un
/// `Stack(clipBehavior: Clip.none, alignment: Alignment.bottomCenter)` avec
/// `Positioned(bottom: -size/2, child: PaBrandHeroBridgeLogo(size: size))`.
class PaBrandHeroBridgeLogo extends StatelessWidget {
  const PaBrandHeroBridgeLogo({super.key, this.size = 84});

  final double size;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        color: Colors.white,
        shape: BoxShape.circle,
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.14),
            blurRadius: 22,
            offset: const Offset(0, 8),
          ),
        ],
      ),
      alignment: Alignment.center,
      child: Padding(
        padding: EdgeInsets.all(size * 0.18),
        child: PaLogo(height: size * 0.55),
      ),
    );
  }
}
