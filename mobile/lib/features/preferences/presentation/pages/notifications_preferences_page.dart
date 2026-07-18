import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../app/theme/paysika/pa_colors.dart';
import '../../../../app/theme/paysika/pa_typography.dart';
import '../../../../core/widgets/paysika/pa_card.dart';
import '../../../../core/widgets/paysika/pa_error_state.dart';
import '../../../../core/widgets/paysika/pa_pattern_background.dart';
import '../../../../core/widgets/skeleton.dart';
import '../../../../l10n/gen/app_localizations.dart';
import '../../domain/notification_prefs.dart';
import '../state/notification_prefs_notifier.dart';

/// Préférences de notifications — style **Paysika**. Une carte par catégorie
/// avec un unique interrupteur **push** (email/sms retirés : non implémentés).
class NotificationsPreferencesPage extends ConsumerWidget {
  const NotificationsPreferencesPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(notificationPrefsProvider);
    final l = AppL10n.of(context);

    return Scaffold(
      backgroundColor: PaColors.canvas,
      body: PaPatternBackground(
        child: SafeArea(
          bottom: false,
          child: Column(
            children: [
              Padding(
                padding: const EdgeInsets.fromLTRB(8, 8, 16, 12),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    IconButton(
                      onPressed: () => Navigator.of(context).maybePop(),
                      icon: const Icon(
                        Icons.arrow_back_rounded,
                        color: PaColors.inkPrimary,
                      ),
                      tooltip: l.common_back,
                    ),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            l.notifprefs_eyebrow.toUpperCase(),
                            style: PaText.eyebrow(),
                          ),
                          const SizedBox(height: 3),
                          Text(
                            l.notifprefs_title,
                            style: PaText.heading(size: 22),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
              Expanded(
                child: ListView(
                  physics: const AlwaysScrollableScrollPhysics(),
                  padding: const EdgeInsets.fromLTRB(16, 4, 16, 90),
                  children: [
                    const _IntroCard(),
                    const SizedBox(height: 18),
                    async.when(
                      data: (prefs) => Column(
                        children: [
                          for (final cat in NotifCategory.values)
                            Padding(
                              padding: const EdgeInsets.only(bottom: 12),
                              child: _CategoryToggleCard(
                                category: cat,
                                enabled: prefs.isEnabled(cat),
                                onChanged: (value) => ref
                                    .read(notificationPrefsProvider.notifier)
                                    .toggle(cat, value),
                              ),
                            ),
                        ],
                      ),
                      loading: () => const PaCard(
                        padding: EdgeInsets.all(18),
                        child: SkeletonList(lines: 5),
                      ),
                      error: (e, _) => PaErrorState(
                        onRetry: () =>
                            ref.invalidate(notificationPrefsProvider),
                      ),
                    ),
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


String _catLabel(BuildContext context, NotifCategory c) {
  final l = AppL10n.of(context);
  return switch (c) {
    NotifCategory.epargne => l.notifprefs_cat_epargne,
    NotifCategory.credit => l.notifprefs_cat_credit,
    NotifCategory.carnet => l.notifprefs_cat_carnet,
    NotifCategory.reconduction => l.notifprefs_cat_reconduction,
    NotifCategory.securite => l.notifprefs_cat_securite,
  };
}

String _catSubtitle(BuildContext context, NotifCategory c) {
  final l = AppL10n.of(context);
  return switch (c) {
    NotifCategory.epargne => l.notifprefs_cat_epargne_sub,
    NotifCategory.credit => l.notifprefs_cat_credit_sub,
    NotifCategory.carnet => l.notifprefs_cat_carnet_sub,
    NotifCategory.reconduction => l.notifprefs_cat_reconduction_sub,
    NotifCategory.securite => l.notifprefs_cat_securite_sub,
  };
}


class _IntroCard extends StatelessWidget {
  const _IntroCard();

  @override
  Widget build(BuildContext context) {
    final l = AppL10n.of(context);
    return PaCard(
      padding: const EdgeInsets.all(18),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 44,
            height: 44,
            decoration: BoxDecoration(
              color: PaColors.tealSurface,
              borderRadius: BorderRadius.circular(12),
            ),
            child: const Icon(
              Icons.notifications_active_outlined,
              color: PaColors.teal,
              size: 22,
            ),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(l.notifprefs_intro_title, style: PaText.label(size: 14)),
                const SizedBox(height: 4),
                Text(
                  l.notifprefs_intro_sub,
                  style: PaText.body(size: 13, color: PaColors.inkSecondary),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}


/// Une catégorie = une carte avec un unique interrupteur **push**.
class _CategoryToggleCard extends StatelessWidget {
  const _CategoryToggleCard({
    required this.category,
    required this.enabled,
    required this.onChanged,
  });

  final NotifCategory category;
  final bool enabled;
  final ValueChanged<bool> onChanged;

  @override
  Widget build(BuildContext context) {
    final meta = _metaFor(category);

    return PaCard(
      padding: const EdgeInsets.fromLTRB(16, 14, 12, 14),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          Container(
            width: 40,
            height: 40,
            decoration: BoxDecoration(
              color: meta.tint.withValues(alpha: 0.12),
              borderRadius: BorderRadius.circular(12),
            ),
            child: Icon(meta.icon, color: meta.tint, size: 20),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  _catLabel(context, category),
                  style: PaText.label(size: 14),
                ),
                const SizedBox(height: 2),
                Text(
                  _catSubtitle(context, category),
                  style: PaText.body(size: 12.5, color: PaColors.inkSecondary),
                ),
              ],
            ),
          ),
          const SizedBox(width: 8),
          Switch.adaptive(
            value: enabled,
            onChanged: onChanged,
            activeThumbColor: PaColors.teal,
            activeTrackColor: PaColors.tealSurface,
          ),
        ],
      ),
    );
  }

  ({IconData icon, Color tint}) _metaFor(NotifCategory c) {
    return switch (c) {
      NotifCategory.epargne => (
          icon: Icons.savings_outlined,
          tint: PaColors.teal,
        ),
      NotifCategory.credit => (
          icon: Icons.account_balance_outlined,
          tint: PaColors.blue,
        ),
      NotifCategory.carnet => (
          icon: Icons.menu_book_outlined,
          tint: PaColors.navy,
        ),
      NotifCategory.reconduction => (
          icon: Icons.refresh_rounded,
          tint: PaColors.warning,
        ),
      NotifCategory.securite => (
          icon: Icons.shield_outlined,
          tint: PaColors.danger,
        ),
    };
  }
}
