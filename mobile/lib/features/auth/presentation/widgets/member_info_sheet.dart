import 'package:flutter/material.dart';

import '../../../../app/theme/paysika/pa_colors.dart';
import '../../../../app/theme/paysika/pa_typography.dart';
import '../../../../app/theme/app_radii.dart';
import '../../../../app/theme/app_spacing.dart';
import '../../../../core/widgets/paysika/pa_brand_hero.dart';
import '../../../../l10n/gen/app_localizations.dart';

/// Modale "Devenir membre" . refonte soft 2026-06-18.
///
/// Même DNA que la Login refondue : mini hero bleu gradient avec coins
/// arrondis en bas + cercle blanc + icône, zone crème dessous avec
/// bénéfices et étapes, CTA bleu gradient pleine largeur.
class MemberInfoSheet extends StatelessWidget {
  const MemberInfoSheet({super.key, this.onJoin});

  final VoidCallback? onJoin;

  static Future<void> show(BuildContext context, {VoidCallback? onJoin}) {
    return showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      backgroundColor: PaColors.canvas,
      barrierColor: Colors.black.withValues(alpha: 0.45),
      shape: const RoundedRectangleBorder(borderRadius: AppRadii.sheet),
      builder: (_) => MemberInfoSheet(onJoin: onJoin),
    );
  }

  @override
  Widget build(BuildContext context) {
    final l = AppL10n.of(context);
    return DraggableScrollableSheet(
      initialChildSize: 0.88,
      maxChildSize: 0.95,
      minChildSize: 0.55,
      expand: false,
      builder: (_, controller) => Column(
        children: [
          // Grabber discret tout en haut
          const SizedBox(height: 8),
          Container(
            width: 38,
            height: 4,
            decoration: BoxDecoration(
              color: PaColors.inkFaint,
              borderRadius: BorderRadius.circular(2),
            ),
          ),
          const SizedBox(height: 8),
          Expanded(
            child: ListView(
              controller: controller,
              padding: EdgeInsets.zero,
              children: [
                // ── Mini hero aurore + logo pont (transition vers cream) ──
                Stack(
                  clipBehavior: Clip.none,
                  alignment: Alignment.bottomCenter,
                  children: [
                    PaBrandHero(
                      bottomRadius: 26,
                      contentPadding:
                          const EdgeInsets.fromLTRB(20, 14, 20, 50),
                      child: Center(
                        child: Text(
                          l.mi_eyebrow.toUpperCase(),
                          style: const TextStyle(
                            color: Colors.white,
                            fontSize: 11,
                            fontWeight: FontWeight.w700,
                            letterSpacing: 1.6,
                          ),
                        ),
                      ),
                    ),
                    const Positioned(
                      bottom: -34,
                      child: PaBrandHeroBridgeLogo(size: 68),
                    ),
                  ],
                ),
                const SizedBox(height: 48),

                // ── Titre + intro centrés ──
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 24),
                  child: Column(
                    children: [
                      Text(
                        "Qu'est-ce qu'un membre ?",
                        textAlign: TextAlign.center,
                        style: PaText.display(
                          size: 22,
                          weight: FontWeight.w700,
                          color: PaColors.inkPrimary,
                          letterSpacing: -0.3,
                        ),
                      ),
                      const SizedBox(height: 8),
                      Text(
                        l.mi_intro,
                        textAlign: TextAlign.center,
                        style: PaText.body(
                          size: 13.5,
                          color: PaColors.inkSecondary,
                          height: 1.55,
                        ),
                      ),
                    ],
                  ),
                ),

                const SizedBox(height: 24),

                // ── 3 bénéfices soft ──
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 20),
                  child: Column(
                    children: [
                      _Benefit(
                        icon: Icons.savings_outlined,
                        tone: PaColors.success,
                        toneSurface: PaColors.successSurface,
                        title: l.mi_card1_title,
                        body: l.mi_card1_body,
                      ),
                      const SizedBox(height: 12),
                      _Benefit(
                        icon: Icons.account_balance_outlined,
                        tone: PaColors.blue,
                        toneSurface: const Color(0xFFE7EEFB),
                        title: l.mi_card2_title,
                        body: l.mi_card2_body,
                      ),
                      const SizedBox(height: 12),
                      _Benefit(
                        icon: Icons.how_to_vote_outlined,
                        tone: PaColors.warning,
                        toneSurface: PaColors.warningSurface,
                        title: l.mi_card3_title,
                        body: l.mi_card3_body,
                      ),
                    ],
                  ),
                ),

                const SizedBox(height: 22),

                // ── Card étapes ──
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 20),
                  child: Container(
                    padding: const EdgeInsets.fromLTRB(16, 16, 16, 14),
                    decoration: BoxDecoration(
                      color: PaColors.paper,
                      borderRadius: BorderRadius.circular(14),
                      border: Border.all(color: PaColors.line, width: 1),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          l.mi_steps_title,
                          style: PaText.label(
                            size: 13,
                            weight: FontWeight.w700,
                            color: PaColors.inkPrimary,
                          ),
                        ),
                        const SizedBox(height: 10),
                        _Step('1', l.mi_step1),
                        _Step('2', l.mi_step2),
                        _Step('3', l.mi_step3),
                      ],
                    ),
                  ),
                ),

                const SizedBox(height: 24),

                // ── CTA bleu gradient + lien plus tard ──
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 20),
                  child: _BlueCta(
                    label: l.mi_submit,
                    onPressed: () {
                      Navigator.of(context).pop();
                      if (onJoin != null) onJoin!();
                    },
                  ),
                ),
                const SizedBox(height: 6),
                Center(
                  child: TextButton(
                    onPressed: () => Navigator.of(context).pop(),
                    style: TextButton.styleFrom(
                      foregroundColor: PaColors.inkSecondary,
                    ),
                    child: Text(
                      l.mi_later,
                      style: PaText.label(
                        size: 13,
                        weight: FontWeight.w600,
                        color: PaColors.inkSecondary,
                      ),
                    ),
                  ),
                ),
                SizedBox(
                  height: MediaQuery.viewPaddingOf(context).bottom +
                      AppSpacing.l,
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}


/// Bénéfice = container fond surface très clair tone + icône cercle pleine
/// tone + titre w700 + body slate.
class _Benefit extends StatelessWidget {
  const _Benefit({
    required this.icon,
    required this.tone,
    required this.toneSurface,
    required this.title,
    required this.body,
  });

  final IconData icon;
  final Color tone;
  final Color toneSurface;
  final String title;
  final String body;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.fromLTRB(14, 14, 14, 14),
      decoration: BoxDecoration(
        color: toneSurface,
        borderRadius: BorderRadius.circular(14),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 40,
            height: 40,
            decoration: BoxDecoration(
              color: tone,
              shape: BoxShape.circle,
            ),
            alignment: Alignment.center,
            child: Icon(icon, color: Colors.white, size: 20),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: PaText.heading(
                    size: 14.5,
                    weight: FontWeight.w700,
                    color: PaColors.inkPrimary,
                  ),
                ),
                const SizedBox(height: 3),
                Text(
                  body,
                  style: PaText.body(
                    size: 12.5,
                    color: PaColors.inkSecondary,
                    height: 1.45,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}


class _Step extends StatelessWidget {
  const _Step(this.num, this.label);
  final String num;
  final String label;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 5),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 22,
            height: 22,
            decoration: BoxDecoration(
              color: PaColors.blue.withValues(alpha: 0.10),
              shape: BoxShape.circle,
            ),
            alignment: Alignment.center,
            child: Text(
              num,
              style: const TextStyle(
                color: PaColors.blue,
                fontSize: 11,
                fontWeight: FontWeight.w800,
              ),
            ),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              label,
              style: PaText.body(
                size: 13,
                color: PaColors.inkSecondary,
                height: 1.5,
              ),
            ),
          ),
        ],
      ),
    );
  }
}


/// CTA bleu gradient pleine largeur (réutilisé du look Login).
class _BlueCta extends StatelessWidget {
  const _BlueCta({required this.label, required this.onPressed});

  final String label;
  final VoidCallback? onPressed;

  @override
  Widget build(BuildContext context) {
    final disabled = onPressed == null;
    return SizedBox(
      width: double.infinity,
      height: 50,
      child: Material(
        color: Colors.transparent,
        borderRadius: BorderRadius.circular(12),
        child: InkWell(
          onTap: onPressed,
          borderRadius: BorderRadius.circular(12),
          child: Ink(
            decoration: BoxDecoration(
              gradient: LinearGradient(
                begin: Alignment.centerLeft,
                end: Alignment.centerRight,
                colors: disabled
                    ? [PaColors.line, PaColors.line]
                    : const [PaColors.blue, PaColors.navy],
              ),
              borderRadius: BorderRadius.circular(12),
            ),
            child: Center(
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Icon(
                    Icons.east_rounded,
                    color: Colors.white,
                    size: 18,
                  ),
                  const SizedBox(width: 8),
                  Text(
                    label,
                    style: const TextStyle(
                      color: Colors.white,
                      fontSize: 14,
                      fontWeight: FontWeight.w700,
                      letterSpacing: 0.2,
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
