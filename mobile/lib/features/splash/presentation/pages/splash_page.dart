import 'package:flutter/material.dart';

import '../../../../app/theme/app_spacing.dart';
import '../../../../app/theme/paysika/pa_colors.dart';
import '../../../../core/widgets/brand_loader.dart';
import '../../../../core/widgets/logo_mark.dart';
import '../../../../l10n/gen/app_localizations.dart';

/// Écran d'attente affiché tant que les providers (`onboardingProvider`,
/// `authProvider`) ne sont pas résolus. La redirection vers `/onboarding`,
/// `/login` ou `/home` est gérée par le `redirect` du router.
///
/// Animation orchestrée en 3 temps :
///   1. Eyebrow fade-in (0–400ms)
///   2. Logo scale 1.08→1.0 + fade (300–950ms, elasticOut)
///   3. Loader + sous-titre fade-in tardif (800–1100ms)
class SplashPage extends StatefulWidget {
  const SplashPage({super.key});

  @override
  State<SplashPage> createState() => _SplashPageState();
}

class _SplashPageState extends State<SplashPage>
    with SingleTickerProviderStateMixin {
  late final AnimationController _ctrl;

  late final Animation<double> _eyebrowOpacity;
  late final Animation<double> _logoOpacity;
  late final Animation<double> _logoScale;
  late final Animation<double> _loaderOpacity;

  @override
  void initState() {
    super.initState();
    _ctrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1100),
    );

    _eyebrowOpacity = CurvedAnimation(
      parent: _ctrl,
      curve: const Interval(0.0, 0.36, curve: Curves.easeOut),
    );
    _logoOpacity = CurvedAnimation(
      parent: _ctrl,
      curve: const Interval(0.18, 0.6, curve: Curves.easeOut),
    );
    // Scale large → small (elasticOut donne le subtle bounce-down)
    _logoScale = Tween<double>(begin: 1.08, end: 1.0).animate(
      CurvedAnimation(
        parent: _ctrl,
        curve: const Interval(0.18, 0.85, curve: Curves.elasticOut),
      ),
    );
    _loaderOpacity = CurvedAnimation(
      parent: _ctrl,
      curve: const Interval(0.7, 1.0, curve: Curves.easeOut),
    );

    _ctrl.forward();
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final l = AppL10n.of(context);
    return Scaffold(
      backgroundColor: PaColors.paper,
      body: Container(
        color: PaColors.paper,
        child: SafeArea(
          child: Center(
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                FadeTransition(
                  opacity: _eyebrowOpacity,
                  child: Text(
                    l.splash_eyebrow,
                    style: const TextStyle(
                      color: PaColors.inkMuted,
                      fontSize: 12,
                      fontWeight: FontWeight.w700,
                      letterSpacing: 2.4,
                    ),
                  ),
                ),
                const SizedBox(height: AppSpacing.xl),

                FadeTransition(
                  opacity: _logoOpacity,
                  child: ScaleTransition(
                    scale: _logoScale,
                    child: const LogoMark(size: LogoSize.hero),
                  ),
                ),

                const SizedBox(height: AppSpacing.huge),

                FadeTransition(
                  opacity: _loaderOpacity,
                  child: Column(
                    children: [
                      const BrandLoader(size: BrandLoaderSize.medium),
                      const SizedBox(height: AppSpacing.l),
                      Text(
                        l.splash_loading,
                        style: const TextStyle(
                          color: PaColors.inkMuted,
                          fontSize: 13,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
