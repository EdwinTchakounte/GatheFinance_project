import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_svg/flutter_svg.dart';
import 'package:go_router/go_router.dart';

import '../../../../app/theme/app_spacing.dart';
import '../../../../app/theme/paysika/pa_colors.dart';
import '../../../../app/theme/paysika/pa_typography.dart';
import '../../../../core/widgets/paysika/pa_button.dart';
import '../../../../core/widgets/paysika/pa_pattern_background.dart';
import '../../../../l10n/gen/app_localizations.dart';
import '../state/onboarding_notifier.dart';

class _Slide {
  const _Slide({
    required this.illustration,
    required this.title,
    required this.body,
  });

  /// Chemin de l'asset SVG (illustration vectorielle aux couleurs Gathe).
  final String illustration;
  final String title;
  final String body;
}

List<_Slide> _buildSlides(AppL10n l) => <_Slide>[
      _Slide(
        illustration: 'assets/illustrations/onboarding_savings.svg',
        title: l.onb_slide1_title,
        body: l.onb_slide1_body,
      ),
      _Slide(
        illustration: 'assets/illustrations/onboarding_banking.svg',
        title: l.onb_slide2_title,
        body: l.onb_slide2_body,
      ),
      _Slide(
        illustration: 'assets/illustrations/onboarding_community.svg',
        title: l.onb_slide3_title,
        body: l.onb_slide3_body,
      ),
    ];

/// Onboarding refonte 2026-06-24 . illustrations SVG bundlees (offline).
///
/// - Hero gradient bleu pleine largeur, coins bas arrondis (vague).
/// - Illustration SVG centree (~160x160) aux couleurs Gathe (bleu + vert).
/// - Titre Sora blanc XL.
/// - Zone creme doodle dessous : 1 phrase body + dots + CTA.
class OnboardingPage extends ConsumerStatefulWidget {
  const OnboardingPage({super.key});

  @override
  ConsumerState<OnboardingPage> createState() => _OnboardingPageState();
}

class _OnboardingPageState extends ConsumerState<OnboardingPage> {
  final _ctrl = PageController();
  int _index = 0;

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  Future<void> _finish() async {
    unawaited(HapticFeedback.lightImpact());
    await ref.read(onboardingProvider.notifier).markSeen();
    if (!mounted) return;
    context.go('/login');
  }

  void _next({required bool isLast}) {
    unawaited(HapticFeedback.selectionClick());
    if (isLast) {
      unawaited(_finish());
    } else {
      _ctrl.nextPage(
        duration: const Duration(milliseconds: 380),
        curve: Curves.easeOutCubic,
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final l = AppL10n.of(context);
    final slides = _buildSlides(l);
    final isLast = _index == slides.length - 1;

    return Scaffold(
      backgroundColor: PaColors.canvas,
      body: PaPatternBackground(
        patternOpacity: 0.32,
        child: Column(
          children: [
            // ── Hero bleu pleine largeur, coins bas arrondis ──
            _BlueHero(
              slide: slides[_index],
              total: slides.length,
              current: _index,
              onSkip: isLast ? null : _finish,
            ),
            // ── Body + CTA dans la zone crème ──
            Expanded(
              child: PageView.builder(
                controller: _ctrl,
                itemCount: slides.length,
                onPageChanged: (i) {
                  unawaited(HapticFeedback.selectionClick());
                  setState(() => _index = i);
                },
                itemBuilder: (context, i) => Padding(
                  padding: const EdgeInsets.fromLTRB(28, 24, 28, 0),
                  child: SingleChildScrollView(
                    child: Text(
                      slides[i].body,
                      style: PaText.body(
                        size: 15,
                        color: PaColors.inkSecondary,
                        height: 1.55,
                      ),
                      textAlign: TextAlign.center,
                    ),
                  ),
                ),
              ),
            ),
            // ── Dots + CTA ──
            Padding(
              padding: const EdgeInsets.fromLTRB(28, 0, 28, 28),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  _Dots(count: slides.length, current: _index),
                  const SizedBox(height: AppSpacing.l),
                  PaButton(
                    label: isLast ? l.onb_start : l.onb_continue,
                    onPressed: () => _next(isLast: isLast),
                  ),
                  AnimatedOpacity(
                    duration: const Duration(milliseconds: 220),
                    opacity: isLast ? 1 : 0,
                    child: Padding(
                      padding: const EdgeInsets.only(top: AppSpacing.s),
                      child: Text(
                        l.onb_consent,
                        textAlign: TextAlign.center,
                        style: PaText.body(
                          size: 11.5,
                          color: PaColors.inkMuted,
                          height: 1.35,
                        ),
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}


/// Bloc hero bleu avec coins bas arrondis (vague), cercle blanc + icône
/// centré, titre Sora blanc XL.
class _BlueHero extends StatelessWidget {
  const _BlueHero({
    required this.slide,
    required this.total,
    required this.current,
    required this.onSkip,
  });

  final _Slide slide;
  final int total;
  final int current;
  final VoidCallback? onSkip;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      decoration: const BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [
            PaColors.blue, // #2563EB
            PaColors.navy, // #1E3A8A
          ],
        ),
        borderRadius: BorderRadius.only(
          bottomLeft: Radius.circular(36),
          bottomRight: Radius.circular(36),
        ),
      ),
      child: SafeArea(
        bottom: false,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(20, 8, 20, 30),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            mainAxisSize: MainAxisSize.min,
            children: [
              // Row top : index + Passer
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(
                    '${current + 1} / $total',
                    style: const TextStyle(
                      color: Colors.white70,
                      fontSize: 12.5,
                      fontWeight: FontWeight.w600,
                      letterSpacing: 1.2,
                    ),
                  ),
                  if (onSkip != null)
                    TextButton(
                      onPressed: onSkip,
                      style: TextButton.styleFrom(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 8, vertical: 4),
                        minimumSize: Size.zero,
                        tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                      ),
                      child: const Text(
                        'Passer',
                        style: TextStyle(
                          color: Colors.white,
                          fontSize: 13,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ),
                ],
              ),
              const SizedBox(height: 12),
              // Illustration SVG centree (avec halo blanc adouci derriere).
              Center(
                child: Container(
                  width: 184,
                  height: 184,
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(
                    color: Colors.white.withValues(alpha: 0.10),
                    shape: BoxShape.circle,
                  ),
                  child: SvgPicture.asset(
                    slide.illustration,
                    fit: BoxFit.contain,
                    semanticsLabel: slide.title,
                    placeholderBuilder: (_) => const SizedBox.shrink(),
                  ),
                ),
              ),
              const SizedBox(height: 18),
              // Titre slide
              Text(
                slide.title,
                textAlign: TextAlign.center,
                style: PaText.display(
                  size: 24,
                  weight: FontWeight.w700,
                  color: Colors.white,
                  letterSpacing: -0.4,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}


class _Dots extends StatelessWidget {
  const _Dots({required this.count, required this.current});

  final int count;
  final int current;

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.center,
      children: List.generate(count, (i) {
        final active = i == current;
        return AnimatedContainer(
          duration: const Duration(milliseconds: 240),
          curve: Curves.easeOutCubic,
          width: active ? 22 : 7,
          height: 7,
          margin: const EdgeInsets.symmetric(horizontal: 4),
          decoration: BoxDecoration(
            color: active ? PaColors.blue : PaColors.inkFaint,
            borderRadius: BorderRadius.circular(4),
          ),
        );
      }),
    );
  }
}
