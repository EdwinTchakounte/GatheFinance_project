import 'package:flutter/material.dart';

/// Anime l'apparition d'un widget en **fade + slight slide bottom→top**, avec
/// un délai paramétrable. Sert à orchestrer une entrée en cascade des blocs
/// d'un écran (carte hero d'abord, sections ensuite, list items après).
///
/// Pour staggerer N enfants, donner `delay: Duration(milliseconds: i * 60)`.
class StaggeredFadeIn extends StatefulWidget {
  const StaggeredFadeIn({
    super.key,
    required this.child,
    this.delay = Duration.zero,
    this.duration = const Duration(milliseconds: 420),
    this.offsetY = 16,
  });

  final Widget child;
  final Duration delay;
  final Duration duration;
  final double offsetY;

  @override
  State<StaggeredFadeIn> createState() => _StaggeredFadeInState();
}

class _StaggeredFadeInState extends State<StaggeredFadeIn>
    with SingleTickerProviderStateMixin {
  late final AnimationController _ctrl;

  @override
  void initState() {
    super.initState();
    _ctrl = AnimationController(vsync: this, duration: widget.duration);
    if (widget.delay == Duration.zero) {
      _ctrl.forward();
    } else {
      Future<void>.delayed(widget.delay, () {
        if (mounted) _ctrl.forward();
      });
    }
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final eased = CurvedAnimation(parent: _ctrl, curve: Curves.easeOutCubic);
    return AnimatedBuilder(
      animation: eased,
      builder: (context, child) {
        return Opacity(
          opacity: eased.value,
          child: Transform.translate(
            offset: Offset(0, widget.offsetY * (1 - eased.value)),
            child: child,
          ),
        );
      },
      child: widget.child,
    );
  }
}
