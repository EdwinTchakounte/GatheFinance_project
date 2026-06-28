import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../app/theme/paysika/pa_colors.dart';
import '../../../../core/formatters/date_formatter.dart';
import '../../../../core/widgets/paysika/pa_card.dart';
import '../../../../core/widgets/paysika/pa_pattern_background.dart';
import '../../../../core/widgets/skeleton.dart';
import '../../../../l10n/gen/app_localizations.dart';
import '../../domain/entities/app_notification.dart';
import '../state/notifications_notifier.dart';

/// Page Notifications . style **Paysika**.
///
/// AppBar minimaliste + liste de notif tiles (avatar coloré + titre + body
/// + temps relatif). Notifs non-lues mises en avant par un dot + fond
/// blanc + bord teal soft ; lues = fond gris pâle.
class NotificationsPage extends ConsumerWidget {
  const NotificationsPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final notifsAsync = ref.watch(notificationsProvider);
    final unread = ref.watch(unreadNotifsCountProvider);
    final l = AppL10n.of(context);

    return Scaffold(
      backgroundColor: PaColors.canvas,
      appBar: AppBar(
        backgroundColor: PaColors.canvas,
        surfaceTintColor: PaColors.canvas,
        elevation: 0,
        scrolledUnderElevation: 0,
        leading: IconButton(
          onPressed: () => Navigator.maybePop(context),
          icon:
              const Icon(Icons.arrow_back_rounded, color: PaColors.inkPrimary),
        ),
        title: Text(
          l.notifs_title,
          style: const TextStyle(
            color: PaColors.inkPrimary,
            fontSize: 17,
            fontWeight: FontWeight.w700,
          ),
        ),
        actions: [
          if (unread > 0)
            TextButton(
              onPressed: () =>
                  ref.read(notificationsProvider.notifier).markAllRead(),
              child: Text(
                l.notifs_mark_all_read,
                style: const TextStyle(
                  color: PaColors.teal,
                  fontSize: 13,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ),
          const SizedBox(width: 4),
        ],
      ),
      body: PaPatternBackground(
        child: RefreshIndicator.adaptive(
          color: PaColors.teal,
          onRefresh: () => ref.read(notificationsProvider.notifier).refresh(),
          child: notifsAsync.when(
            data: (items) {
              if (items.isEmpty) return const _EmptyState();
              return ListView.separated(
                physics: const AlwaysScrollableScrollPhysics(),
                padding: const EdgeInsets.fromLTRB(16, 10, 16, 60),
                itemCount: items.length,
                separatorBuilder: (_, __) => const SizedBox(height: 8),
                itemBuilder: (_, i) => _NotifCard(
                  notif: items[i],
                  onTap: () => ref
                      .read(notificationsProvider.notifier)
                      .markRead(items[i].id),
                ),
              );
            },
            loading: () => ListView(
              padding: const EdgeInsets.all(16),
              children: List.generate(
                4,
                (_) => const Padding(
                  padding: EdgeInsets.only(bottom: 10),
                  child: PaCard(
                    padding: EdgeInsets.all(14),
                    child: SkeletonList(lines: 2),
                  ),
                ),
              ),
            ),
            error: (e, _) => Padding(
              padding: const EdgeInsets.all(16),
              child: PaCard(
                padding: const EdgeInsets.all(20),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Icon(Icons.error_outline,
                        color: PaColors.danger, size: 24,),
                    const SizedBox(height: 8),
                    Text(
                      l.notifs_unavailable,
                      style: const TextStyle(
                        color: PaColors.danger,
                        fontSize: 16,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      e.toString(),
                      style: const TextStyle(
                          color: PaColors.inkMuted, fontSize: 12.5,),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _NotifCard extends StatelessWidget {
  const _NotifCard({required this.notif, required this.onTap});

  final AppNotification notif;
  final VoidCallback onTap;

  ({IconData icon, Color tint}) get _icon {
    switch (notif.kind) {
      case NotifKind.savings:
        return (icon: Icons.savings_outlined, tint: PaColors.success);
      case NotifKind.loan:
        return (icon: Icons.account_balance_outlined, tint: PaColors.teal);
      case NotifKind.payment:
        return (icon: Icons.payments_outlined, tint: PaColors.navy);
      case NotifKind.lender:
        return (icon: Icons.volunteer_activism_outlined, tint: PaColors.success);
      case NotifKind.announcement:
        return (icon: Icons.campaign_rounded, tint: PaColors.blue);
      case NotifKind.system:
        return (icon: Icons.notifications_outlined, tint: PaColors.warning);
    }
  }

  @override
  Widget build(BuildContext context) {
    final v = _icon;
    final isUnread = !notif.read;

    return PaCard(
      onTap: onTap,
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
      background: isUnread ? PaColors.paper : PaColors.cardBg,
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 40,
            height: 40,
            decoration: BoxDecoration(
              color: v.tint.withValues(alpha: 0.14),
              shape: BoxShape.circle,
            ),
            alignment: Alignment.center,
            child: Icon(v.icon, color: v.tint, size: 20),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Expanded(
                      child: Text(
                        notif.title,
                        style: TextStyle(
                          color: PaColors.inkPrimary,
                          fontSize: 14.5,
                          fontWeight:
                              isUnread ? FontWeight.w700 : FontWeight.w600,
                        ),
                      ),
                    ),
                    const SizedBox(width: 8),
                    Text(
                      _relative(context, notif.createdAt),
                      style: const TextStyle(
                        color: PaColors.inkMuted,
                        fontSize: 11.5,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 4),
                Text(
                  notif.body,
                  style: const TextStyle(
                    color: PaColors.inkSecondary,
                    fontSize: 13,
                    height: 1.45,
                  ),
                ),
                if (isUnread) ...[
                  const SizedBox(height: 8),
                  Container(
                    width: 8,
                    height: 8,
                    decoration: const BoxDecoration(
                      color: PaColors.teal,
                      shape: BoxShape.circle,
                    ),
                  ),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }

  String _relative(BuildContext context, DateTime date) {
    final l = AppL10n.of(context);
    final diff = DateTime.now().difference(date);
    if (diff.inMinutes < 60) return l.notifs_rel_minutes(diff.inMinutes);
    if (diff.inHours < 24) return l.notifs_rel_hours(diff.inHours);
    if (diff.inDays < 7) return l.notifs_rel_days(diff.inDays);
    return AppDateFormatter.short(date);
  }
}

class _EmptyState extends StatelessWidget {
  const _EmptyState();

  @override
  Widget build(BuildContext context) {
    final l = AppL10n.of(context);
    return ListView(
      physics: const AlwaysScrollableScrollPhysics(),
      padding: const EdgeInsets.all(20),
      children: [
        const SizedBox(height: 60),
        Center(
          child: Container(
            width: 80,
            height: 80,
            decoration: const BoxDecoration(
              color: PaColors.tealSurface,
              shape: BoxShape.circle,
            ),
            alignment: Alignment.center,
            child: const Icon(
              Icons.notifications_off_outlined,
              color: PaColors.teal,
              size: 36,
            ),
          ),
        ),
        const SizedBox(height: 18),
        Center(
          child: Text(
            l.notifs_empty_title,
            style: const TextStyle(
              color: PaColors.inkPrimary,
              fontSize: 17,
              fontWeight: FontWeight.w700,
            ),
          ),
        ),
        const SizedBox(height: 6),
        Center(
          child: Text(
            l.notifs_empty_sub,
            textAlign: TextAlign.center,
            style: const TextStyle(color: PaColors.inkMuted, fontSize: 13.5),
          ),
        ),
      ],
    );
  }
}
