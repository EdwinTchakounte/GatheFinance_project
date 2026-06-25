import 'package:flutter/material.dart';

import '../../../app/theme/paysika/pa_colors.dart';

/// Effet shimmer Paysika . gradient teal animé qui glisse de gauche à droite.
///
/// Utilisé pour les loading states. Plus premium que des SkeletonBox plats
/// car la lueur animée signale clairement « chargement en cours » au membre,
/// sans qu'il ait à interpréter une icône ou un spinner.
///
/// Usage :
///   PaShimmer(child: Container(width: 200, height: 40, color: Colors.grey))
///
/// La couleur de base du child est ignorée . c'est l'effet qui prime.
class PaShimmer extends StatefulWidget {
  const PaShimmer({
    super.key,
    required this.child,
    this.duration = const Duration(milliseconds: 1400),
  });

  final Widget child;
  final Duration duration;

  @override
  State<PaShimmer> createState() => _PaShimmerState();
}

class _PaShimmerState extends State<PaShimmer>
    with SingleTickerProviderStateMixin {
  late final AnimationController _ctrl;

  @override
  void initState() {
    super.initState();
    _ctrl = AnimationController(vsync: this, duration: widget.duration)
      ..repeat();
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _ctrl,
      builder: (context, child) {
        return ShaderMask(
          blendMode: BlendMode.srcATop,
          shaderCallback: (rect) {
            // Position de la lueur entre -1 (off-screen left) et +1 (off-screen right).
            final t = _ctrl.value;
            final dx = -1.0 + 2.0 * t;
            return LinearGradient(
              begin: const Alignment(-1.0, 0),
              end: const Alignment(1.0, 0),
              colors: const [
                Color(0xFFE9ECF1), // base soft gray
                Color(0xFFF8FAFC), // lueur claire
                Color(0xFFE9ECF1),
              ],
              stops: [
                (dx - 0.3).clamp(0.0, 1.0),
                dx.clamp(0.0, 1.0),
                (dx + 0.3).clamp(0.0, 1.0),
              ],
            ).createShader(rect);
          },
          child: child,
        );
      },
      child: widget.child,
    );
  }
}


/// Bloc shimmer rectangulaire . utilitaire pour composer des skeletons.
class PaShimmerBox extends StatelessWidget {
  const PaShimmerBox({
    super.key,
    this.width,
    required this.height,
    this.borderRadius = 8,
  });

  final double? width;
  final double height;
  final double borderRadius;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: width,
      height: height,
      decoration: BoxDecoration(
        color: PaColors.cardBg,
        borderRadius: BorderRadius.circular(borderRadius),
      ),
    );
  }
}


/// Liste shimmer prête à l'emploi . N lignes avec avatar + 2 lignes texte.
/// Reproduit la silhouette d'une PaTransactionTile en chargement.
class PaShimmerList extends StatelessWidget {
  const PaShimmerList({
    super.key,
    this.count = 3,
    this.spacing = 14,
  });

  final int count;
  final double spacing;

  @override
  Widget build(BuildContext context) {
    return PaShimmer(
      child: Column(
        children: [
          for (var i = 0; i < count; i++) ...[
            const Row(
              children: [
                PaShimmerBox(
                  width: 40,
                  height: 40,
                  borderRadius: 20,
                ),
                SizedBox(width: 14),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      PaShimmerBox(width: 160, height: 14),
                      SizedBox(height: 6),
                      PaShimmerBox(width: 90, height: 11),
                    ],
                  ),
                ),
                PaShimmerBox(width: 64, height: 14),
              ],
            ),
            if (i < count - 1) SizedBox(height: spacing),
          ],
        ],
      ),
    );
  }
}
