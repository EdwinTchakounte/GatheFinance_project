import 'package:flutter/material.dart';

/// Transition de page **fade + léger slide vertical**, plus douce que la
/// transition Material par défaut. Réutilisée partout via
/// `ThemeData.pageTransitionsTheme`.
class _FadeThroughTransitionsBuilder extends PageTransitionsBuilder {
  const _FadeThroughTransitionsBuilder();

  @override
  Widget buildTransitions<T>(
    PageRoute<T> route,
    BuildContext context,
    Animation<double> animation,
    Animation<double> secondaryAnimation,
    Widget child,
  ) {
    final eased = CurvedAnimation(
      parent: animation,
      curve: Curves.easeOutCubic,
      reverseCurve: Curves.easeInCubic,
    );

    final slide = Tween<Offset>(
      begin: const Offset(0, 0.012),
      end: Offset.zero,
    ).animate(eased);

    return FadeTransition(
      opacity: eased,
      child: SlideTransition(position: slide, child: child),
    );
  }
}


class AppPageTransitions {
  AppPageTransitions._();

  static const PageTransitionsTheme theme = PageTransitionsTheme(
    builders: {
      TargetPlatform.android: _FadeThroughTransitionsBuilder(),
      TargetPlatform.iOS: _FadeThroughTransitionsBuilder(),
      TargetPlatform.linux: _FadeThroughTransitionsBuilder(),
      TargetPlatform.macOS: _FadeThroughTransitionsBuilder(),
      TargetPlatform.windows: _FadeThroughTransitionsBuilder(),
    },
  );
}
