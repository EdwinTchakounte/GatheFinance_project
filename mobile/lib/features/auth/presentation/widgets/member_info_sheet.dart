import 'package:flutter/material.dart';

import '../../../../app/theme/paysika/pa_colors.dart';
import '../../../../app/theme/app_radii.dart';
import '../../../../app/theme/app_spacing.dart';
import '../../../../app/theme/app_typography.dart';
import '../../../../core/widgets/eyebrow.dart';
import '../../../../l10n/gen/app_localizations.dart';

/// Modale qui explique ce qu'est un **membre** et présente la marche à
/// suivre pour devenir membre. Réutilisée :
///   - depuis le login (« Devenir membre »)
///   - depuis l'onboarding (slide « Membre » → « En savoir plus »)
class MemberInfoSheet extends StatelessWidget {
  const MemberInfoSheet({super.key, this.onJoin});

  /// Action « Soumettre ma demande » — typiquement ouvre `MembershipForm`.
  final VoidCallback? onJoin;

  static Future<void> show(BuildContext context, {VoidCallback? onJoin}) {
    return showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Theme.of(context).colorScheme.surface,
      barrierColor: Colors.black.withValues(alpha: 0.45),
      shape: const RoundedRectangleBorder(borderRadius: AppRadii.sheet),
      builder: (_) => MemberInfoSheet(onJoin: onJoin),
    );
  }

  @override
  Widget build(BuildContext context) {
    final l = AppL10n.of(context);
    return DraggableScrollableSheet(
      initialChildSize: 0.85,
      maxChildSize: 0.95,
      minChildSize: 0.5,
      expand: false,
      builder: (_, controller) => SafeArea(
        top: false,
        child: ListView(
          controller: controller,
          padding: const EdgeInsets.fromLTRB(20, 8, 20, 28),
          children: [
            // Grabber
            Center(
              child: Container(
                width: 36,
                height: 4,
                decoration: BoxDecoration(
                  color: Theme.of(context).colorScheme.outline,
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
            ),
            const SizedBox(height: AppSpacing.xl),

            // Hero pictogramme
            Center(
              child: Container(
                width: 88,
                height: 88,
                decoration: BoxDecoration(
                  gradient: LinearGradient(
                    begin: Alignment.topLeft,
                    end: Alignment.bottomRight,
                    colors: [
                      PaColors.teal.withValues(alpha: 0.14),
                      PaColors.success.withValues(alpha: 0.14),
                    ],
                  ),
                  shape: BoxShape.circle,
                ),
                alignment: Alignment.center,
                child: const Icon(
                  Icons.handshake_outlined,
                  size: 44,
                  color: PaColors.teal,
                ),
              ),
            ),

            const SizedBox(height: AppSpacing.l),

            Center(child: Eyebrow(l.mi_eyebrow)),
            const SizedBox(height: 6),

            Center(
              child: Text(
                'Qu\'est-ce qu\'un membre ?',
                textAlign: TextAlign.center,
                style: AppTypography.displayLarge.copyWith(fontSize: 26),
              ),
            ),

            const SizedBox(height: AppSpacing.m),

            Text(
              l.mi_intro,
              textAlign: TextAlign.center,
              style: AppTypography.bodyLarge.copyWith(
                color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.7),
                height: 1.55,
              ),
            ),

            const SizedBox(height: AppSpacing.xxl),

            // 3 avantages
            _Benefit(
              icon: Icons.savings_outlined,
              tint: PaColors.success,
              title: l.mi_card1_title,
              body: l.mi_card1_body,
            ),
            const SizedBox(height: AppSpacing.m),
            _Benefit(
              icon: Icons.account_balance_outlined,
              tint: PaColors.teal,
              title: l.mi_card2_title,
              body: l.mi_card2_body,
            ),
            const SizedBox(height: AppSpacing.m),
            _Benefit(
              icon: Icons.how_to_vote_outlined,
              tint: PaColors.warning,
              title: l.mi_card3_title,
              body: l.mi_card3_body,
            ),

            const SizedBox(height: AppSpacing.xxl),

            // Conditions
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: Theme.of(context).colorScheme.surface,
                borderRadius: BorderRadius.circular(16),
                border: Border.all(color: Theme.of(context).colorScheme.outline),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    l.mi_steps_title,
                    style: AppTypography.labelLarge,
                  ),
                  const SizedBox(height: AppSpacing.s),
                  _Step('1', l.mi_step1),
                  _Step('2', l.mi_step2),
                  _Step('3', l.mi_step3),
                ],
              ),
            ),

            const SizedBox(height: AppSpacing.xl),

            SizedBox(
              width: double.infinity,
              child: FilledButton(
                onPressed: () {
                  Navigator.of(context).pop();
                  if (onJoin != null) onJoin!();
                },
                child: Text(l.mi_submit),
              ),
            ),
            const SizedBox(height: AppSpacing.s),
            SizedBox(
              width: double.infinity,
              child: TextButton(
                onPressed: () => Navigator.of(context).pop(),
                child: Text(l.mi_later),
              ),
            ),
          ],
        ),
      ),
    );
  }
}


class _Benefit extends StatelessWidget {
  const _Benefit({
    required this.icon,
    required this.tint,
    required this.title,
    required this.body,
  });

  final IconData icon;
  final Color tint;
  final String title;
  final String body;

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Container(
          width: 44,
          height: 44,
          decoration: BoxDecoration(
            color: tint.withValues(alpha: 0.12),
            borderRadius: const BorderRadius.all(AppRadii.r12),
          ),
          alignment: Alignment.center,
          child: Icon(icon, color: tint, size: 22),
        ),
        const SizedBox(width: 14),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(title, style: AppTypography.headingSmall.copyWith(fontSize: 16)),
              const SizedBox(height: 2),
              Text(
                body,
                style: AppTypography.bodyMedium.copyWith(
                  color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.7),
                  height: 1.5,
                ),
              ),
            ],
          ),
        ),
      ],
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
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 22,
            height: 22,
            decoration: const BoxDecoration(
              color: PaColors.tealSurface,
              shape: BoxShape.circle,
            ),
            alignment: Alignment.center,
            child: Text(
              num,
              style: AppTypography.bodySmall.copyWith(
                color: PaColors.teal,
                fontWeight: FontWeight.w700,
              ),
            ),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              label,
              style: AppTypography.bodyMedium.copyWith(
                color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.7),
                height: 1.45,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
