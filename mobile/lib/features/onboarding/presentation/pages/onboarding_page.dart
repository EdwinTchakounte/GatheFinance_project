import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../../app/theme/app_radii.dart';
import '../../../../app/theme/app_spacing.dart';
import '../../../../app/theme/app_typography.dart';
import '../../../../app/theme/paysika/pa_colors.dart';
import '../../../../l10n/gen/app_localizations.dart';
import '../state/onboarding_notifier.dart';

class _Slide {
  const _Slide({
    required this.image,
    required this.icon,
    required this.eyebrow,
    required this.title,
    required this.body,
    required this.accent,
  });

  final String image;
  final IconData icon;
  final String eyebrow;
  final String title;
  final String body;
  final Color accent;
}

List<_Slide> _buildSlides(AppL10n l) => <_Slide>[
      _Slide(
        image: 'assets/images/father-daughter-saving.jpg',
        icon: Icons.savings_outlined,
        eyebrow: l.onb_slide1_eyebrow,
        title: l.onb_slide1_title,
        body: l.onb_slide1_body,
        accent: PaColors.success,
      ),
      _Slide(
        image: 'assets/images/entrepreneurs.jpg',
        icon: Icons.trending_up_rounded,
        eyebrow: l.onb_slide2_eyebrow,
        title: l.onb_slide2_title,
        body: l.onb_slide2_body,
        accent: PaColors.teal,
      ),
      _Slide(
        image: 'assets/images/cooperative-investment.jpg',
        icon: Icons.diversity_3_rounded,
        eyebrow: l.onb_slide3_eyebrow,
        title: l.onb_slide3_title,
        body: l.onb_slide3_body,
        accent: PaColors.warning,
      ),
      _Slide(
        image: 'assets/images/family.jpg',
        icon: Icons.handshake_outlined,
        eyebrow: l.onb_slide4_eyebrow,
        title: l.onb_slide4_title,
        body: l.onb_slide4_body,
        accent: PaColors.teal,
      ),
    ];

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
    final scheme = Theme.of(context).colorScheme;
    final slides = _buildSlides(l);
    final isLast = _index == slides.length - 1;

    return Scaffold(
      backgroundColor: PaColors.appBg,
      body: SafeArea(
        child: Column(
          children: [
            // Header avec "Passer" + eyebrow
            Padding(
              padding: const EdgeInsets.fromLTRB(
                AppSpacing.screenH,
                AppSpacing.s,
                AppSpacing.screenH,
                0,
              ),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(
                    l.onb_eyebrow_welcome.toUpperCase(),
                    style: const TextStyle(
                      color: PaColors.inkMuted,
                      fontSize: 11,
                      fontWeight: FontWeight.w700,
                      letterSpacing: 1.6,
                    ),
                  ),
                  AnimatedSwitcher(
                    duration: const Duration(milliseconds: 220),
                    child: isLast
                        ? const SizedBox(key: ValueKey('empty'), width: 1)
                        : TextButton(
                            key: const ValueKey('skip'),
                            onPressed: _finish,
                            child: Text(
                              l.onb_skip,
                              style: const TextStyle(
                                color: PaColors.inkMuted,
                                fontSize: 13,
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                          ),
                  ),
                ],
              ),
            ),

              // Slides
              Expanded(
                child: PageView.builder(
                  controller: _ctrl,
                  itemCount: slides.length,
                  onPageChanged: (i) {
                    unawaited(HapticFeedback.selectionClick());
                    setState(() => _index = i);
                  },
                  itemBuilder: (context, i) => _SlideView(
                    slide: slides[i],
                    index: i,
                    pageController: _ctrl,
                  ),
                ),
              ),

              // Indicateur + CTA
              Padding(
                padding: const EdgeInsets.fromLTRB(
                  AppSpacing.screenH,
                  AppSpacing.l,
                  AppSpacing.screenH,
                  AppSpacing.l,
                ),
                child: Column(
                  children: [
                    _RailIndicator(count: slides.length, current: _index),
                    const SizedBox(height: AppSpacing.xl),
                    SizedBox(
                      width: double.infinity,
                      child: FilledButton(
                        onPressed: () => _next(isLast: isLast),
                        child: AnimatedSwitcher(
                          duration: const Duration(milliseconds: 220),
                          child: Text(
                            isLast ? l.onb_start : l.onb_continue,
                            key: ValueKey(isLast),
                          ),
                        ),
                      ),
                    ),
                    const SizedBox(height: AppSpacing.s),
                    AnimatedOpacity(
                      duration: const Duration(milliseconds: 220),
                      opacity: isLast ? 1 : 0,
                      child: Text(
                        l.onb_consent,
                        textAlign: TextAlign.center,
                        style: AppTypography.bodySmall.copyWith(
                          color: scheme.onSurface.withValues(alpha: 0.5),
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


class _SlideView extends StatelessWidget {
  const _SlideView({
    required this.slide,
    required this.index,
    required this.pageController,
  });

  final _Slide slide;
  final int index;
  final PageController pageController;

  /// Position relative à la page courante :
  ///   0   = slide active
  ///   -1  = slide précédente (à gauche)
  ///   +1  = slide suivante (à droite)
  double _offset() {
    if (!pageController.hasClients ||
        pageController.position.haveDimensions == false) {
      return 0;
    }
    return (pageController.page ?? pageController.initialPage.toDouble()) -
        index;
  }

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return AnimatedBuilder(
      animation: pageController,
      builder: (context, _) {
        final offset = _offset();
        // Parallax inverse : l'image « reste » légèrement pendant le swipe.
        final imageShift = offset * -32;
        // Le texte fade dès qu'on s'éloigne du centre.
        final textOpacity = (1 - offset.abs() * 1.6).clamp(0.0, 1.0);
        final textShiftY = offset.abs() * 14;
        // Légère mise à l'échelle de l'image pour donner de la profondeur.
        final imageScale = 1 - offset.abs() * 0.04;

        return Padding(
          padding: const EdgeInsets.fromLTRB(
            AppSpacing.screenH,
            AppSpacing.m,
            AppSpacing.screenH,
            AppSpacing.l,
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Hero image — vignette + filtre accent + badge pill
              AspectRatio(
                aspectRatio: 1.05,
                child: Transform.scale(
                  scale: imageScale,
                  child: ClipRRect(
                    borderRadius: AppRadii.cardHero,
                    child: Stack(
                      fit: StackFit.expand,
                      children: [
                        // Image sur-dimensionnée pour le parallax
                        Transform.translate(
                          offset: Offset(imageShift, 0),
                          child: OverflowBox(
                            maxWidth: double.infinity,
                            child: Image.asset(
                              slide.image,
                              fit: BoxFit.cover,
                            ),
                          ),
                        ),
                        // Vignette + teinte accent légère pour cohérence brand
                        Positioned.fill(
                          child: DecoratedBox(
                            decoration: BoxDecoration(
                              gradient: LinearGradient(
                                begin: Alignment.topLeft,
                                end: Alignment.bottomRight,
                                colors: [
                                  slide.accent.withValues(alpha: 0.06),
                                  Colors.transparent,
                                  slide.accent.withValues(alpha: 0.22),
                                ],
                                stops: const [0, 0.45, 1],
                              ),
                            ),
                          ),
                        ),
                        // Filet vertical institutionnel (gauche)
                        Positioned(
                          top: 22,
                          bottom: 22,
                          left: 0,
                          child: Container(
                            width: 3,
                            color: slide.accent,
                          ),
                        ),
                        // Badge pill (icône + libellé) — façon AfDB/UN
                        Positioned(
                          top: 18,
                          left: 22,
                          child: Container(
                            padding: const EdgeInsets.fromLTRB(10, 6, 14, 6),
                            decoration: BoxDecoration(
                              color: Colors.white.withValues(alpha: 0.94),
                              borderRadius: BorderRadius.circular(999),
                              boxShadow: [
                                BoxShadow(
                                  color: Colors.black.withValues(alpha: 0.10),
                                  blurRadius: 14,
                                  offset: const Offset(0, 4),
                                ),
                              ],
                            ),
                            child: Row(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                Icon(slide.icon, size: 16, color: slide.accent),
                                const SizedBox(width: 7),
                                Text(
                                  slide.eyebrow,
                                  style: AppTypography.labelMedium.copyWith(
                                    color: PaColors.navy,
                                    fontWeight: FontWeight.w600,
                                    fontSize: 12.5,
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ),

              const SizedBox(height: AppSpacing.xxl),

              // Bloc texte : fade + slide vertical synchronisés
              Opacity(
                opacity: textOpacity,
                child: Transform.translate(
                  offset: Offset(0, textShiftY),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      // Mini filet horizontal accent — note éditoriale
                      Container(
                        height: 2,
                        width: 32,
                        margin: const EdgeInsets.only(bottom: AppSpacing.m),
                        color: slide.accent,
                      ),
                      Text(
                        slide.title,
                        style: AppTypography.displayLarge
                            .copyWith(color: scheme.onSurface),
                      ),
                      const SizedBox(height: AppSpacing.m),
                      Text(
                        slide.body,
                        style: AppTypography.bodyLarge.copyWith(
                          color: scheme.onSurface.withValues(alpha: 0.7),
                          height: 1.5,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ),
        );
      },
    );
  }
}


/// Indicateur de progression posé sur un rail continu. Le segment actif
/// s'allonge en cobalt ; les autres restent en line subtil. Donne une lecture
/// instantanée de l'avancée sans le côté « pastilles » des onboarding bon
/// marché.
class _RailIndicator extends StatelessWidget {
  const _RailIndicator({required this.count, required this.current});

  final int count;
  final int current;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return SizedBox(
      height: 6,
      child: LayoutBuilder(
        builder: (context, c) {
          const gap = 6.0;
          final segWidth = (c.maxWidth - gap * (count - 1)) / count;
          return Stack(
            children: [
              Row(
                children: List.generate(count, (i) {
                  final active = i == current;
                  final done = i < current;
                  return Padding(
                    padding: EdgeInsets.only(right: i == count - 1 ? 0 : gap),
                    child: AnimatedContainer(
                      duration: const Duration(milliseconds: 320),
                      curve: Curves.easeOutCubic,
                      width: segWidth,
                      height: 6,
                      decoration: BoxDecoration(
                        color: done
                            ? scheme.primary.withValues(alpha: 0.45)
                            : active
                                ? scheme.primary
                                : scheme.outline,
                        borderRadius: BorderRadius.circular(3),
                      ),
                    ),
                  );
                }),
              ),
            ],
          );
        },
      ),
    );
  }
}
