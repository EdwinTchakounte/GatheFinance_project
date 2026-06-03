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

/// Préférences de notifications — style **Paysika**. Une carte par catégorie,
/// 3 canaux (push / email / sms) togglables.
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
                      icon: const Icon(Icons.arrow_back_rounded,
                          color: PaColors.inkPrimary),
                      tooltip: l.common_back,
                    ),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(l.notifprefs_eyebrow.toUpperCase(),
                              style: PaText.eyebrow()),
                          const SizedBox(height: 3),
                          Text(l.notifprefs_title,
                              style: PaText.heading(size: 22)),
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
                              child: _CategoryCard(
                                category: cat,
                                prefs: prefs,
                                onToggle: (chan, value) => ref
                                    .read(notificationPrefsProvider.notifier)
                                    .toggle(cat, chan, value),
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

String _chanLabel(BuildContext context, NotifChannel c) {
  final l = AppL10n.of(context);
  return switch (c) {
    NotifChannel.push => l.notifprefs_chan_push,
    NotifChannel.email => l.notifprefs_chan_email,
    NotifChannel.sms => l.notifprefs_chan_sms,
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


class _CategoryCard extends StatelessWidget {
  const _CategoryCard({
    required this.category,
    required this.prefs,
    required this.onToggle,
  });

  final NotifCategory category;
  final NotificationPrefs prefs;
  final void Function(NotifChannel chan, bool value) onToggle;

  @override
  Widget build(BuildContext context) {
    final meta = _metaFor(category);

    return PaCard(
      padding: const EdgeInsets.fromLTRB(18, 18, 18, 14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
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
                    Text(_catLabel(context, category),
                        style: PaText.label(size: 14)),
                    const SizedBox(height: 2),
                    Text(
                      _catSubtitle(context, category),
                      style: PaText.body(
                          size: 12.5, color: PaColors.inkSecondary),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 14),
          const Divider(height: 1, color: PaColors.line),
          ...NotifChannel.values.map((chan) {
            final enabled = prefs.isEnabled(category, chan);
            return _ChannelRow(
              channel: chan,
              enabled: enabled,
              onChanged: (v) => onToggle(chan, v),
            );
          }),
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


class _ChannelRow extends StatelessWidget {
  const _ChannelRow({
    required this.channel,
    required this.enabled,
    required this.onChanged,
  });

  final NotifChannel channel;
  final bool enabled;
  final ValueChanged<bool> onChanged;

  @override
  Widget build(BuildContext context) {
    final icon = switch (channel) {
      NotifChannel.push => Icons.notifications_outlined,
      NotifChannel.email => Icons.mail_outline_rounded,
      NotifChannel.sms => Icons.sms_outlined,
    };

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        children: [
          Icon(icon,
              size: 18, color: enabled ? PaColors.teal : PaColors.inkMuted),
          const SizedBox(width: 12),
          Expanded(
            child: Text(
              _chanLabel(context, channel),
              style: PaText.body(
                size: 14,
                weight: enabled ? FontWeight.w600 : FontWeight.w500,
                color: enabled ? PaColors.inkPrimary : PaColors.inkSecondary,
              ),
            ),
          ),
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
}
