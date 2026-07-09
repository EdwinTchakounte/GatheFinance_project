import 'dart:math' as math;
import 'package:flutter/material.dart';

import '../../app/theme/app_colors.dart';

/// Loader signature GATHE Finance . deux arcs concentriques qui tournent en
/// sens inverse, reprenant le cobalt et l'emerald du logo. Doux, élégant,
/// reconnaissable. Trois tailles canoniques.
enum BrandLoaderSize { small, medium, large }

class BrandLoader extends StatefulWidget {
  const BrandLoader({super.key, this.size = BrandLoaderSize.medium});

  final BrandLoaderSize size;

  @override
  State<BrandLoader> createState() => _BrandLoaderState();
}

class _BrandLoaderState extends State<BrandLoader>
    with TickerProviderStateMixin {
  late final AnimationController _outer;
  late final AnimationController _inner;

  @override
  void initState() {
    super.initState();
    _outer = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1600),
    )..repeat();
    _inner = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1100),
    )..repeat();
  }

  @override
  void dispose() {
    _outer.dispose();
    _inner.dispose();
    super.dispose();
  }

  double get _diameter {
    return switch (widget.size) {
      BrandLoaderSize.small => 28,
      BrandLoaderSize.medium => 44,
      BrandLoaderSize.large => 72,
    };
  }

  double get _stroke {
    return switch (widget.size) {
      BrandLoaderSize.small => 2.6,
      BrandLoaderSize.medium => 3.2,
      BrandLoaderSize.large => 4.6,
    };
  }

  @override
  Widget build(BuildContext context) {
    final trackColor = Theme.of(context).colorScheme.outline;
    return SizedBox(
      width: _diameter,
      height: _diameter,
      child: AnimatedBuilder(
        animation: Listenable.merge([_outer, _inner]),
        builder: (context, _) {
          return CustomPaint(
            painter: _BrandLoaderPainter(
              outerProgress: _outer.value,
              innerProgress: _inner.value,
              stroke: _stroke,
              trackColor: trackColor,
            ),
          );
        },
      ),
    );
  }
}

class _BrandLoaderPainter extends CustomPainter {
  _BrandLoaderPainter({
    required this.outerProgress,
    required this.innerProgress,
    required this.stroke,
    required this.trackColor,
  });

  final double outerProgress;
  final double innerProgress;
  final double stroke;
  final Color trackColor;

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    final outerR = (size.shortestSide - stroke) / 2;
    final innerR = outerR - stroke - 4;

    final trackPaint = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = stroke
      ..color = trackColor.withValues(alpha: 0.55);
    canvas.drawCircle(center, outerR, trackPaint);
    canvas.drawCircle(center, innerR, trackPaint);

    // Arc extérieur . cobalt . tourne dans le sens horaire
    const sweep = math.pi * 0.85; // ~150°
    final outerPaint = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = stroke
      ..strokeCap = StrokeCap.round
      ..color = AppColors.cobalt;
    canvas.drawArc(
      Rect.fromCircle(center: center, radius: outerR),
      outerProgress * 2 * math.pi - math.pi / 2,
      sweep,
      false,
      outerPaint,
    );

    // Arc intérieur . emerald . tourne dans le sens inverse
    final innerPaint = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = stroke
      ..strokeCap = StrokeCap.round
      ..color = AppColors.emerald;
    canvas.drawArc(
      Rect.fromCircle(center: center, radius: innerR),
      -innerProgress * 2 * math.pi - math.pi / 2,
      sweep,
      false,
      innerPaint,
    );
  }

  @override
  bool shouldRepaint(_BrandLoaderPainter old) =>
      old.outerProgress != outerProgress ||
      old.innerProgress != innerProgress ||
      old.stroke != stroke ||
      old.trackColor != trackColor;
}


/// Trois points qui pulsent en cascade . alternative plus discrète pour les
/// chargements inline (ex. à l'intérieur d'un bouton ou d'une ligne).
class BrandPulseDots extends StatefulWidget {
  const BrandPulseDots({super.key, this.size = 6, this.color});

  final double size;
  final Color? color;

  @override
  State<BrandPulseDots> createState() => _BrandPulseDotsState();
}

class _BrandPulseDotsState extends State<BrandPulseDots>
    with SingleTickerProviderStateMixin {
  late final AnimationController _ctrl;

  @override
  void initState() {
    super.initState();
    _ctrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1200),
    )..repeat();
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  double _dotScale(double t, double phase) {
    // bell-shaped pulse centered on phase
    final local = ((t - phase + 1) % 1);
    return 0.7 + 0.6 * math.sin(local * math.pi).clamp(0, 1);
  }

  @override
  Widget build(BuildContext context) {
    final c = widget.color ?? AppColors.cobalt;
    return AnimatedBuilder(
      animation: _ctrl,
      builder: (_, __) {
        return Row(
          mainAxisSize: MainAxisSize.min,
          children: List.generate(3, (i) {
            final s = _dotScale(_ctrl.value, i * 0.18);
            return Padding(
              padding: EdgeInsets.symmetric(horizontal: widget.size * 0.3),
              child: Transform.scale(
                scale: s,
                child: Container(
                  width: widget.size,
                  height: widget.size,
                  decoration: BoxDecoration(
                    color: c.withValues(alpha: 0.4 + 0.6 * (s - 0.7) / 0.6),
                    shape: BoxShape.circle,
                  ),
                ),
              ),
            );
          }),
        );
      },
    );
  }
}
