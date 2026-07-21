import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../../app/theme/paysika/pa_colors.dart';
import '../../../../core/formatters/date_formatter.dart';
import '../../../../core/widgets/live_poller.dart';
import '../../../../core/widgets/paysika/pa_card.dart';
import '../../../../core/widgets/paysika/pa_pattern_background.dart';
import '../../../../core/widgets/skeleton.dart';
import '../../../../l10n/gen/app_localizations.dart';
import '../../domain/entities/app_notification.dart';
import '../state/notifications_notifier.dart';
import '../../../../core/error/error_message.dart';
import 'announcements_page.dart';

/// Page Notifications . style **Paysika**.
///
/// AppBar minimaliste + liste de notif tiles (avatar coloré + titre + body
/// + temps relatif). Notifs non-lues mises en avant par un dot + fond
/// blanc + bord teal soft ; lues = fond gris pâle.
class NotificationsPage extends ConsumerStatefulWidget {
  const NotificationsPage({super.key});

  @override
  ConsumerState<NotificationsPage> createState() => _NotificationsPageState();
}

class _NotificationsPageState extends ConsumerState<NotificationsPage> {
  /// Catégorie sélectionnée (`null` = Tout). Les onglets affichés sont
  /// **dynamiques** : seules les catégories réellement présentes dans les
  /// notifications reçues apparaissent (cf. build).
  NotifKind? _filter;

  @override
  void initState() {
    super.initState();
    // Ouvrir la page de notifications = le membre les a « vues » → on marque
    // tout comme lu automatiquement (post-frame pour ne pas muter un provider
    // pendant le 1er build). Le badge de la cloche retombe ainsi à 0.
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      if (ref.read(unreadNotifsCountProvider) > 0) {
        ref.read(notificationsProvider.notifier).markAllRead();
      }
    });
  }

  /// Tap sur une notification → marque lue puis navigue vers la ressource
  /// correspondant à sa catégorie (kind).
  void _openNotif(BuildContext context, AppNotification n) {
    ref.read(notificationsProvider.notifier).markRead(n.id);
    if (n.kind == NotifKind.announcement) {
      Navigator.of(context).push(
        MaterialPageRoute<void>(builder: (_) => const AnnouncementsPage()),
      );
      return;
    }
    final route = switch (n.kind) {
      NotifKind.loan => '/credit',
      NotifKind.avaliste => '/avaliste/mandats',
      NotifKind.savings => '/savings/history',
      NotifKind.payment => '/states',
      NotifKind.lender => '/me/lender-payouts',
      NotifKind.support => '/support',
      NotifKind.announcement => null,
      NotifKind.system => null,
    };
    if (route == null) return;
    // /credit est une branche du shell (bascule d'onglet), le reste se pousse.
    if (route == '/credit') {
      context.go(route);
    } else {
      context.push(route);
    }
  }

  @override
  Widget build(BuildContext context) {
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
            fontSize: 16,
            fontWeight: FontWeight.w700,
          ),
        ),
        actions: [
          IconButton(
            tooltip: 'Annonces',
            onPressed: () => Navigator.of(context).push(
              MaterialPageRoute<void>(
                builder: (_) => const AnnouncementsPage(),
              ),
            ),
            icon: const Icon(Icons.campaign_rounded, color: PaColors.teal),
          ),
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
      body: Stack(
        children: [
          // Polling 30s : voit les nouvelles notifs admin sans pull-to-refresh.
          // Idempotence : pas de rebuild si le hash JSON est inchange.
          LivePoller(
            refresh: () => ref.read(notificationsProvider.notifier).refresh(),
            readSnapshot: () => ref.read(notificationsProvider).valueOrNull,
          ),
          PaPatternBackground(
        child: RefreshIndicator.adaptive(
          color: PaColors.teal,
          onRefresh: () => ref.read(notificationsProvider.notifier).refresh(),
          child: notifsAsync.when(
            data: (items) {
              if (items.isEmpty) return const _EmptyState();

              // Onglets DYNAMIQUES : seulement les catégories réellement
              // présentes (ordre stable via l'enum). « Tout » toujours en tête.
              final present = <NotifKind>[
                for (final k in NotifKind.values)
                  if (items.any((n) => n.kind == k)) k,
              ];
              // Le filtre courant a disparu (plus aucune notif de ce type) →
              // on retombe sur « Tout ».
              final active =
                  (_filter != null && present.contains(_filter)) ? _filter : null;
              final visible = active == null
                  ? items
                  : items.where((n) => n.kind == active).toList();

              return Column(
                children: [
                  // Une seule catégorie → pas de barre (rien à filtrer).
                  if (present.length > 1)
                    _FilterBar(
                      present: present,
                      active: active,
                      onSelect: (k) => setState(() => _filter = k),
                    ),
                  Expanded(
                    child: ListView.separated(
                      physics: const AlwaysScrollableScrollPhysics(),
                      padding: const EdgeInsets.fromLTRB(16, 10, 16, 60),
                      itemCount: visible.length,
                      separatorBuilder: (_, __) => const SizedBox(height: 8),
                      itemBuilder: (_, i) => _NotifCard(
                        notif: visible[i],
                        onTap: () => _openNotif(context, visible[i]),
                      ),
                    ),
                  ),
                ],
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
                      friendlyError(e),
                      style: const TextStyle(
                          color: PaColors.inkMuted, fontSize: 12,),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
        ],
      ),
    );
  }
}

/// Libellé localisé d'une catégorie de notification.
String _kindLabel(AppL10n l, NotifKind k) => switch (k) {
      NotifKind.savings => l.notif_kind_savings,
      NotifKind.loan => l.notif_kind_loan,
      NotifKind.avaliste => 'Avaliste',
      NotifKind.payment => l.notif_kind_payment,
      NotifKind.lender => l.notif_kind_lender,
      NotifKind.announcement => l.notif_kind_announcement,
      NotifKind.support => l.notif_kind_support,
      NotifKind.system => l.notif_kind_system,
    };

/// Barre de filtres horizontale (pilules) — « Tout » + catégories présentes.
class _FilterBar extends StatelessWidget {
  const _FilterBar({
    required this.present,
    required this.active,
    required this.onSelect,
  });

  final List<NotifKind> present;
  final NotifKind? active;
  final ValueChanged<NotifKind?> onSelect;

  @override
  Widget build(BuildContext context) {
    final l = AppL10n.of(context);
    final entries = <(NotifKind?, String)>[
      (null, l.notifs_filter_all),
      for (final k in present) (k, _kindLabel(l, k)),
    ];
    return SizedBox(
      height: 44,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.fromLTRB(16, 8, 16, 4),
        itemCount: entries.length,
        separatorBuilder: (_, __) => const SizedBox(width: 8),
        itemBuilder: (_, i) {
          final (kind, label) = entries[i];
          final selected = kind == active;
          return GestureDetector(
            onTap: () => onSelect(kind),
            child: AnimatedContainer(
              duration: const Duration(milliseconds: 160),
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
              decoration: BoxDecoration(
                color: selected ? PaColors.teal : PaColors.paper,
                borderRadius: BorderRadius.circular(999),
                border: Border.all(
                  color: selected ? PaColors.teal : PaColors.line,
                  width: 0.9,
                ),
              ),
              alignment: Alignment.center,
              child: Text(
                label,
                style: TextStyle(
                  color: selected ? Colors.white : PaColors.inkSecondary,
                  fontSize: 12,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ),
          );
        },
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
      case NotifKind.avaliste:
        return (icon: Icons.handshake_rounded, tint: PaColors.blue);
      case NotifKind.payment:
        return (icon: Icons.payments_outlined, tint: PaColors.navy);
      case NotifKind.lender:
        return (icon: Icons.volunteer_activism_outlined, tint: PaColors.success);
      case NotifKind.announcement:
        return (icon: Icons.campaign_rounded, tint: PaColors.blue);
      case NotifKind.support:
        return (icon: Icons.support_agent_rounded, tint: PaColors.teal);
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
                          fontSize: 14,
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
                        fontSize: 11,
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
              fontSize: 16,
              fontWeight: FontWeight.w700,
            ),
          ),
        ),
        const SizedBox(height: 6),
        Center(
          child: Text(
            l.notifs_empty_sub,
            textAlign: TextAlign.center,
            style: const TextStyle(color: PaColors.inkMuted, fontSize: 13),
          ),
        ),
      ],
    );
  }
}
