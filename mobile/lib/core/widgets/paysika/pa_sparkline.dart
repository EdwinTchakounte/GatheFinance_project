import 'package:flutter/material.dart';

/// Mini-courbe de tendance (area sparkline) — dessinée à la main, sans
/// dépendance externe (offline-safe). Donne de la « vie » et de la richesse
/// data au hero balance, façon Revolut/N26.
///
/// [values] = série chronologique (ancien → récent). Trace une ligne lissée
/// + un dégradé de remplissage dessous. Anime le tracé à l'apparition.
class PaSparkline extends StatefulWidget {
  const PaSparkline({
    super.key,
    required this.values,
    this.color = Colors.white,
    this.fillOpacity = 0.18,
    this.strokeWidth = 2.2,
  });

  final List<num> values;
  final Color color;
  final double fillOpacity;
  final double strokeWidth;

  @override
  State<PaSparkline> createState() => _PaSparklineState();
}

class _PaSparklineState extends State<PaSparkline>
    with SingleTickerProviderStateMixin {
  late final AnimationController _ctrl = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 900),
  )..forward();

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _ctrl,
      builder: (context, _) => CustomPaint(
        painter: _SparkPainter(
          values: widget.values,
          color: widget.color,
          fillOpacity: widget.fillOpacity,
          strokeWidth: widget.strokeWidth,
          progress: Curves.easeOutCubic.transform(_ctrl.value),
        ),
        size: Size.infinite,
      ),
    );
  }
}

class _SparkPainter extends CustomPainter {
  _SparkPainter({
    required this.values,
    required this.color,
    required this.fillOpacity,
    required this.strokeWidth,
    required this.progress,
  });

  final List<num> values;
  final Color color;
  final double fillOpacity;
  final double strokeWidth;
  final double progress;

  @override
  void paint(Canvas canvas, Size size) {
    if (values.length < 2) return;
    final minV = values.reduce((a, b) => a < b ? a : b).toDouble();
    final maxV = values.reduce((a, b) => a > b ? a : b).toDouble();
    final span = (maxV - minV).abs() < 1e-9 ? 1.0 : (maxV - minV);
    final dx = size.width / (values.length - 1);

    Offset pointAt(int i) {
      final x = dx * i;
      final norm = (values[i].toDouble() - minV) / span;
      // marge verticale 14% haut/bas pour ne pas coller aux bords
      final y = size.height * (0.86 - norm * 0.72);
      return Offset(x, y);
    }

    final pts = [for (var i = 0; i < values.length; i++) pointAt(i)];

    // Construit un chemin lissé (Catmull-Rom → Bézier).
    final line = Path()..moveTo(pts.first.dx, pts.first.dy);
    for (var i = 0; i < pts.length - 1; i++) {
      final p0 = i == 0 ? pts[i] : pts[i - 1];
      final p1 = pts[i];
      final p2 = pts[i + 1];
      final p3 = i + 2 < pts.length ? pts[i + 2] : p2;
      final c1 = Offset(p1.dx + (p2.dx - p0.dx) / 6, p1.dy + (p2.dy - p0.dy) / 6);
      final c2 = Offset(p2.dx - (p3.dx - p1.dx) / 6, p2.dy - (p3.dy - p1.dy) / 6);
      line.cubicTo(c1.dx, c1.dy, c2.dx, c2.dy, p2.dx, p2.dy);
    }

    // Animation du tracé : on clippe horizontalement selon [progress].
    canvas.save();
    canvas.clipRect(Rect.fromLTWH(0, 0, size.width * progress, size.height));

    // Remplissage dégradé sous la courbe.
    final fill = Path.from(line)
      ..lineTo(pts.last.dx, size.height)
      ..lineTo(pts.first.dx, size.height)
      ..close();
    canvas.drawPath(
      fill,
      Paint()
        ..shader = LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [
            color.withValues(alpha: fillOpacity),
            color.withValues(alpha: 0),
          ],
        ).createShader(Rect.fromLTWH(0, 0, size.width, size.height)),
    );

    // Ligne.
    canvas.drawPath(
      line,
      Paint()
        ..color = color.withValues(alpha: 0.9)
        ..style = PaintingStyle.stroke
        ..strokeWidth = strokeWidth
        ..strokeCap = StrokeCap.round
        ..strokeJoin = StrokeJoin.round,
    );
    canvas.restore();

    // Point terminal (apparaît en fin d'animation).
    if (progress > 0.92) {
      final last = pts.last;
      canvas.drawCircle(last, 3.4, Paint()..color = color);
      canvas.drawCircle(
        last,
        6,
        Paint()..color = color.withValues(alpha: 0.25),
      );
    }
  }

  @override
  bool shouldRepaint(_SparkPainter old) =>
      old.progress != progress || old.values != values;
}
