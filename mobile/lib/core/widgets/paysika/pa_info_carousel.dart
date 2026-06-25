import 'package:flutter/material.dart';

import '../../../app/theme/paysika/pa_colors.dart';
import '../../../app/theme/paysika/pa_typography.dart';

/// Donnée d'une card d'info du carousel.
class PaInfoSlide {
  const PaInfoSlide({
    required this.icon,
    required this.title,
    required this.subtitle,
    this.ctaLabel,
    this.onTap,
    this.gradient,
    this.accent = PaColors.teal,
  });

  final IconData icon;
  final String title;
  final String subtitle;
  final String? ctaLabel;
  final VoidCallback? onTap;

  /// Gradient de fond optionnel (sinon card claire teal-surface).
  final Gradient? gradient;
  final Color accent;
}

/// Carousel horizontal de cards d'info qui défile . avec dots de progression.
///
/// Reproduit le bloc "Upgrade to Premium" + dots de la réf `ok_home_page.jpeg`,
/// mais avec plusieurs slides d'information (cotisation, crédit, épargne…).
/// Auto-scroll doux + swipe manuel.
class PaInfoCarousel extends StatefulWidget {
  const PaInfoCarousel({
    super.key,
    required this.slides,
    this.height = 118,
    this.autoPlay = true,
  });

  final List<PaInfoSlide> slides;
  final double height;
  final bool autoPlay;

  @override
  State<PaInfoCarousel> createState() => _PaInfoCarouselState();
}

class _PaInfoCarouselState extends State<PaInfoCarousel> {
  final _ctrl = PageController(viewportFraction: 0.965);
  int _index = 0;

  @override
  void initState() {
    super.initState();
    if (widget.autoPlay && widget.slides.length > 1) _scheduleAutoPlay();
  }

  void _scheduleAutoPlay() {
    Future.delayed(const Duration(seconds: 5), () {
      if (!mounted || !_ctrl.hasClients) return;
      final next = (_index + 1) % widget.slides.length;
      _ctrl.animateToPage(
        next,
        duration: const Duration(milliseconds: 450),
        curve: Curves.easeOutCubic,
      );
      _scheduleAutoPlay();
    });
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        SizedBox(
          height: widget.height,
          child: PageView.builder(
            controller: _ctrl,
            onPageChanged: (i) => setState(() => _index = i),
            itemCount: widget.slides.length,
            itemBuilder: (context, i) => Padding(
              padding: const EdgeInsets.symmetric(horizontal: 3),
              child: _SlideCard(slide: widget.slides[i]),
            ),
          ),
        ),
        const SizedBox(height: 12),
        // Dots de progression . actif = barre allongée teal.
        Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            for (var i = 0; i < widget.slides.length; i++)
              AnimatedContainer(
                duration: const Duration(milliseconds: 250),
                margin: const EdgeInsets.symmetric(horizontal: 3),
                width: i == _index ? 22 : 7,
                height: 7,
                decoration: BoxDecoration(
                  color: i == _index ? PaColors.teal : PaColors.inkFaint,
                  borderRadius: BorderRadius.circular(4),
                ),
              ),
          ],
        ),
      ],
    );
  }
}


class _SlideCard extends StatelessWidget {
  const _SlideCard({required this.slide});

  final PaInfoSlide slide;

  @override
  Widget build(BuildContext context) {
    final hasGradient = slide.gradient != null;
    final accent = slide.accent;
    final onColor = hasGradient ? Colors.white : PaColors.inkPrimary;
    final subColor = hasGradient
        ? Colors.white.withValues(alpha: 0.88)
        : PaColors.inkMuted;
    // Fond : gradient (slide vedette) OU surface translucide (doodle visible).
    final bgColor =
        hasGradient ? null : PaColors.paper.withValues(alpha: 0.82);

    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: slide.onTap,
        borderRadius: BorderRadius.circular(10),
        child: Container(
          decoration: BoxDecoration(
            gradient: slide.gradient,
            color: bgColor,
            borderRadius: BorderRadius.circular(10),
            boxShadow: [
              BoxShadow(
                color: hasGradient
                    ? accent.withValues(alpha: 0.26)
                    : PaColors.navy.withValues(alpha: 0.06),
                blurRadius: hasGradient ? 26 : 18,
                offset: const Offset(0, 8),
                spreadRadius: -6,
              ),
            ],
          ),
          clipBehavior: Clip.antiAlias,
          child: Stack(
            children: [
              // Watermark . grande icône fantôme bas-droite pour la profondeur.
              Positioned(
                right: -16,
                bottom: -20,
                child: Icon(
                  slide.icon,
                  size: 110,
                  color: (hasGradient ? Colors.white : accent)
                      .withValues(alpha: hasGradient ? 0.07 : 0.045),
                ),
              ),
              // Halo lumineux top-right sur les slides gradient.
              if (hasGradient)
                Positioned(
                  top: -30,
                  right: -20,
                  child: Container(
                    width: 120,
                    height: 120,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      gradient: RadialGradient(
                        colors: [
                          Colors.white.withValues(alpha: 0.18),
                          Colors.white.withValues(alpha: 0),
                        ],
                      ),
                    ),
                  ),
                ),

              Padding(
                padding: const EdgeInsets.fromLTRB(16, 13, 16, 13),
                child: Row(
                  children: [
                    Container(
                      width: 40,
                      height: 40,
                      decoration: BoxDecoration(
                        color: hasGradient
                            ? Colors.white.withValues(alpha: 0.20)
                            : accent.withValues(alpha: 0.14),
                        borderRadius: BorderRadius.circular(12),
                      ),
                      alignment: Alignment.center,
                      child: Icon(
                        slide.icon,
                        color: hasGradient ? Colors.white : accent,
                        size: 21,
                      ),
                    ),
                    const SizedBox(width: 12),
                    // Texte (titre + sous-titre) à gauche, CTA à droite.
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Text(
                            slide.title,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: PaText.heading(size: 15.5, color: onColor),
                          ),
                          const SizedBox(height: 3),
                          Text(
                            slide.subtitle,
                            maxLines: 2,
                            overflow: TextOverflow.ellipsis,
                            style: PaText.body(
                                size: 12.5, color: subColor, height: 1.3,),
                          ),
                        ],
                      ),
                    ),
                    if (slide.ctaLabel != null) ...[
                      const SizedBox(width: 10),
                      _CtaPill(
                        label: slide.ctaLabel!,
                        onGradient: hasGradient,
                        accent: accent,
                      ),
                    ],
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}


/// Pill CTA d'une slide . plein blanc sur gradient, teinté accent sinon.
class _CtaPill extends StatelessWidget {
  const _CtaPill({
    required this.label,
    required this.onGradient,
    required this.accent,
  });

  final String label;
  final bool onGradient;
  final Color accent;

  @override
  Widget build(BuildContext context) {
    final bg = onGradient ? Colors.white : accent.withValues(alpha: 0.12);
    final fg = onGradient ? accent : accent;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 7),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(999),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(
            label,
            style: PaText.label(size: 12.5, weight: FontWeight.w700, color: fg),
          ),
          const SizedBox(width: 5),
          Icon(Icons.arrow_forward_rounded, size: 15, color: fg),
        ],
      ),
    );
  }
}
