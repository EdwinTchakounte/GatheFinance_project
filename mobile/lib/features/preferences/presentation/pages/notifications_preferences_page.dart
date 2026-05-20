import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_radii.dart';
import '../../../../app/theme/app_spacing.dart';
import '../../../../app/theme/app_typography.dart';
import '../../../../core/widgets/app_card.dart';
import '../../../../core/widgets/brand_background.dart';
import '../../../../core/widgets/skeleton.dart';
import '../../../../core/widgets/static_page_header.dart';
import '../../../../l10n/gen/app_localizations.dart';
import '../../domain/notification_prefs.dart';
import '../state/notification_prefs_notifier.dart';

class NotificationsPreferencesPage extends ConsumerWidget {
  const NotificationsPreferencesPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(notificationPrefsProvider);
    final l = AppL10n.of(context);

    return Scaffold(
      body: BrandBackground(
        intensity: 0.55,
        child: SafeArea(
          bottom: false,
          child: Column(
            children: [
              StaticPageHeader(
                eyebrow: l.notifprefs_eyebrow,
                title: l.notifprefs_title,
              ),
              Expanded(
                child: CustomScrollView(
                  physics: const AlwaysScrollableScrollPhysics(),
                  slivers: [
              const SliverPadding(
                padding: EdgeInsets.fromLTRB(
                  AppSpacing.screenH,
                  AppSpacing.m,
                  AppSpacing.screenH,
                  AppSpacing.xl,
                ),
                sliver: SliverToBoxAdapter(child: _IntroCard()),
              ),
              async.when(
                data: (prefs) => SliverPadding(
                  padding: const EdgeInsets.fromLTRB(
                    AppSpacing.screenH,
                    0,
                    AppSpacing.screenH,
                    AppSpacing.huge,
                  ),
                  sliver: SliverList.builder(
                    itemCount: NotifCategory.values.length,
                    itemBuilder: (context, i) {
                      final cat = NotifCategory.values[i];
                      return Padding(
                        padding: const EdgeInsets.only(bottom: AppSpacing.m),
                        child: _CategoryCard(
                          category: cat,
                          prefs: prefs,
                          onToggle: (chan, value) => ref
                              .read(notificationPrefsProvider.notifier)
                              .toggle(cat, chan, value),
                        ),
                      );
                    },
                  ),
                ),
                loading: () => const SliverToBoxAdapter(
                  child: Padding(
                    padding: EdgeInsets.symmetric(
                      horizontal: AppSpacing.screenH,
                      vertical: 20,
                    ),
                    child: SkeletonList(lines: 5),
                  ),
                ),
                error: (e, _) => SliverFillRemaining(
                  hasScrollBody: false,
                  child: _ErrorState(message: e.toString()),
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
    final scheme = Theme.of(context).colorScheme;
    return AppCard(
      variant: AppCardVariant.glass,
      padding: const EdgeInsets.all(18),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 44,
            height: 44,
            decoration: BoxDecoration(
              color: scheme.primary.withValues(alpha: 0.12),
              borderRadius: const BorderRadius.all(AppRadii.r12),
            ),
            child: Icon(
              Icons.notifications_active_outlined,
              color: scheme.primary,
              size: 22,
            ),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  l.notifprefs_intro_title,
                  style: AppTypography.labelLarge
                      .copyWith(color: scheme.onSurface),
                ),
                const SizedBox(height: 4),
                Text(
                  l.notifprefs_intro_sub,
                  style: AppTypography.bodySmall.copyWith(
                    color: scheme.onSurface.withValues(alpha: 0.7),
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
    final scheme = Theme.of(context).colorScheme;
    final meta = _metaFor(category);

    return AppCard(
      variant: AppCardVariant.glass,
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
                  gradient: meta.gradient,
                  borderRadius: const BorderRadius.all(AppRadii.r12),
                  boxShadow: [
                    BoxShadow(
                      color: meta.glow.withValues(alpha: 0.20),
                      blurRadius: 10,
                      offset: const Offset(0, 4),
                    ),
                  ],
                ),
                child: Icon(meta.icon, color: Colors.white, size: 20),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      _catLabel(context, category),
                      style: AppTypography.labelLarge
                          .copyWith(color: scheme.onSurface),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      _catSubtitle(context, category),
                      style: AppTypography.bodySmall.copyWith(
                        color: scheme.onSurface.withValues(alpha: 0.7),
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 14),
          Divider(height: 1, color: scheme.outline),
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

  ({IconData icon, LinearGradient gradient, Color glow}) _metaFor(
    NotifCategory c,
  ) {
    switch (c) {
      case NotifCategory.epargne:
        return (
          icon: Icons.savings_outlined,
          gradient: AppCardGradients.emeraldFresh,
          glow: AppColors.emerald,
        );
      case NotifCategory.credit:
        return (
          icon: Icons.account_balance_outlined,
          gradient: AppCardGradients.cobaltDeep,
          glow: AppColors.cobalt,
        );
      case NotifCategory.carnet:
        return (
          icon: Icons.menu_book_outlined,
          gradient: AppCardGradients.terraWarm,
          glow: AppColors.terra,
        );
      case NotifCategory.reconduction:
        return (
          icon: Icons.refresh_rounded,
          gradient: const LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [Color(0xFF6B7BD6), Color(0xFF3B4FB3)],
          ),
          glow: AppColors.cobalt,
        );
      case NotifCategory.securite:
        return (
          icon: Icons.shield_outlined,
          gradient: const LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [Color(0xFFD45B5B), Color(0xFFA13838)],
          ),
          glow: AppColors.danger,
        );
    }
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
    final scheme = Theme.of(context).colorScheme;
    final icon = switch (channel) {
      NotifChannel.push => Icons.notifications_outlined,
      NotifChannel.email => Icons.mail_outline_rounded,
      NotifChannel.sms => Icons.sms_outlined,
    };

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        children: [
          Icon(
            icon,
            size: 18,
            color: enabled
                ? scheme.primary
                : scheme.onSurface.withValues(alpha: 0.5),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Text(
              _chanLabel(context, channel),
              style: AppTypography.bodyMedium.copyWith(
                color: enabled
                    ? scheme.onSurface
                    : scheme.onSurface.withValues(alpha: 0.7),
                fontWeight: enabled ? FontWeight.w600 : FontWeight.w500,
              ),
            ),
          ),
          Switch.adaptive(
            value: enabled,
            onChanged: onChanged,
            activeThumbColor: AppColors.emerald,
            activeTrackColor: AppColors.emeraldSurface,
          ),
        ],
      ),
    );
  }
}


class _ErrorState extends StatelessWidget {
  const _ErrorState({required this.message});
  final String message;

  @override
  Widget build(BuildContext context) {
    final l = AppL10n.of(context);
    final scheme = Theme.of(context).colorScheme;
    return Padding(
      padding: const EdgeInsets.fromLTRB(
        AppSpacing.screenH,
        AppSpacing.huge,
        AppSpacing.screenH,
        AppSpacing.huge,
      ),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const Icon(
            Icons.cloud_off_outlined,
            color: AppColors.terraDark,
            size: 36,
          ),
          const SizedBox(height: 10),
          Text(
            l.notifprefs_unavailable,
            textAlign: TextAlign.center,
            style: AppTypography.headingSmall.copyWith(
              color: AppColors.terraDark,
            ),
          ),
          const SizedBox(height: 6),
          Text(
            message,
            textAlign: TextAlign.center,
            style: AppTypography.bodySmall.copyWith(
              color: scheme.onSurface.withValues(alpha: 0.55),
            ),
          ),
        ],
      ),
    );
  }
}
