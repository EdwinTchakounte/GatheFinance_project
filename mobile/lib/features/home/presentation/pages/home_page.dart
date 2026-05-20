import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../../app/theme/app_radii.dart';
import '../../../../app/theme/paysika/pa_colors.dart';
import '../../../../app/theme/paysika/pa_typography.dart';
import '../../../../core/formatters/date_formatter.dart';
import '../../../../core/widgets/paysika/pa_action_pill.dart';
import '../../../../core/widgets/paysika/pa_avatar.dart';
import '../../../../core/widgets/paysika/pa_card.dart';
import '../../../../core/widgets/paysika/pa_hero_balance.dart';
import '../../../../core/widgets/paysika/pa_pattern_background.dart';
import '../../../../core/widgets/paysika/pa_info_carousel.dart';
import '../../../../core/widgets/paysika/pa_shimmer.dart';
import '../../../../core/widgets/paysika/pa_transaction_tile.dart';
import '../../../security/presentation/widgets/pin_prompt_sheet.dart';
import '../../../../l10n/gen/app_localizations.dart';
import '../../../auth/presentation/state/auth_notifier.dart';
import '../../../notifications/presentation/state/notifications_notifier.dart';
import '../../../savings/domain/entities/savings_account.dart';
import '../../../savings/domain/entities/savings_transaction.dart';
import '../../../savings/presentation/state/savings_notifier.dart';
import '../widgets/deposit_sheet.dart';

/// Accueil — **prototype Paysika** (style validé sur captures `capture_paysika/`).
///
/// Composition :
///   1. Header sobre — avatar greeting + cloche notifications
///   2. Hero balance — card gradient aurore teal→navy avec CTA Verser
///   3. Quick actions — 4 cercles outlined (Verser, Crédit, Carnet, Historique)
///   4. Services — grille 2 colonnes (Demander crédit, Carnet, États, Aide)
///   5. Recent transactions — header + 4 dernières tiles avatar
class HomePage extends ConsumerWidget {
  const HomePage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final member = ref.watch(authProvider).valueOrNull;
    final savings = ref.watch(savingsProvider);
    final l = AppL10n.of(context);
    final firstName = member?.prenom ?? l.profile_member_badge;

    return Scaffold(
      backgroundColor: PaColors.canvas,
      body: PaPatternBackground(
        child: SafeArea(
        bottom: false,
        child: Column(
          children: [
            // ── Header FIXE (ne défile pas) ──────────────────────────────
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 12, 20, 10),
              child: _Header(
                firstName: firstName,
                unread: ref.watch(unreadNotifsCountProvider),
              ),
            ),
            Expanded(
              child: RefreshIndicator.adaptive(
          color: PaColors.teal,
          onRefresh: () => ref.read(savingsProvider.notifier).refresh(),
          child: CustomScrollView(
            physics: const AlwaysScrollableScrollPhysics(),
            slivers: [
              // ── Hero balance gradient aurore ───────────────────────────
              SliverToBoxAdapter(
                child: Padding(
                  padding: const EdgeInsets.fromLTRB(16, 14, 16, 18),
                  child: savings.when(
                    data: (data) => PaHeroBalance(
                      amount: data.solde,
                      label: l.home_balance_label,
                      ctaLabel: l.home_action_deposit,
                      onDeposit: () => _openDeposit(context),
                      pendingLabel: _pendingLabel(data),
                      onPendingTap: () => context.push('/savings/history'),
                      onRequestReveal: () =>
                          PinPromptSheet.show(context),
                    ),
                    loading: () => const _HeroSkeleton(),
                    error: (e, _) => _HeroError(message: e.toString()),
                  ),
                ),
              ),

              // ── Quick actions — 4 cercles outlined ─────────────────────
              SliverToBoxAdapter(
                child: Padding(
                  padding: const EdgeInsets.fromLTRB(16, 4, 16, 20),
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      PaActionPill(
                        icon: Icons.add_card_outlined,
                        label: l.home_action_deposit,
                        onTap: () => _openDeposit(context),
                      ),
                      PaActionPill(
                        icon: Icons.account_balance_outlined,
                        label: l.home_action_credit,
                        onTap: () => context.go('/credit'),
                      ),
                      PaActionPill(
                        icon: Icons.menu_book_outlined,
                        label: l.home_action_booklet,
                        onTap: () => context.go('/booklet'),
                      ),
                      PaActionPill(
                        icon: Icons.history_rounded,
                        label: l.home_action_history,
                        onTap: () => context.push('/savings/history'),
                      ),
                    ],
                  ),
                ),
              ),

              // ── Carousel d'infos défilant (remplace « Mes services ») ──
              SliverToBoxAdapter(
                child: Padding(
                  padding: const EdgeInsets.fromLTRB(16, 0, 16, 24),
                  child: PaInfoCarousel(
                    slides: [
                      PaInfoSlide(
                        icon: Icons.savings_outlined,
                        title: l.carousel_save_title,
                        subtitle: l.carousel_save_sub,
                        gradient: PaGradients.heroAurore,
                        accent: PaColors.teal,
                        ctaLabel: l.carousel_save_cta,
                        onTap: () => _openDeposit(context),
                      ),
                      PaInfoSlide(
                        icon: Icons.account_balance_outlined,
                        title: l.carousel_credit_title,
                        subtitle: l.carousel_credit_sub,
                        accent: PaColors.teal,
                        ctaLabel: l.carousel_credit_cta,
                        onTap: () => context.go('/credit'),
                      ),
                      PaInfoSlide(
                        icon: Icons.menu_book_outlined,
                        title: l.carousel_booklet_title,
                        subtitle: l.carousel_booklet_sub,
                        accent: PaColors.warning,
                        ctaLabel: l.carousel_booklet_cta,
                        onTap: () => context.go('/booklet'),
                      ),
                      PaInfoSlide(
                        icon: Icons.headset_mic_outlined,
                        title: l.carousel_help_title,
                        subtitle: l.carousel_help_sub,
                        accent: PaColors.catNeutral,
                        ctaLabel: l.carousel_help_cta,
                        onTap: () => context.push('/help'),
                      ),
                    ],
                  ),
                ),
              ),

              // ── Section "Récent" + Voir tout ───────────────────────────
              SliverToBoxAdapter(
                child: Padding(
                  padding: const EdgeInsets.fromLTRB(20, 4, 20, 8),
                  child: Row(
                    children: [
                      Text(
                        l.home_recent_ops,
                        style: PaText.heading(size: 16),
                      ),
                      const Spacer(),
                      TextButton(
                        onPressed: () => context.push('/savings/history'),
                        style: TextButton.styleFrom(
                          padding: EdgeInsets.zero,
                          minimumSize: const Size(0, 0),
                          tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                        ),
                        child: Text(
                          l.home_see_all,
                          style: PaText.label(
                            size: 13.5,
                            weight: FontWeight.w700,
                            color: PaColors.teal,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
              SliverToBoxAdapter(
                child: Padding(
                  padding: const EdgeInsets.fromLTRB(16, 0, 16, 60),
                  child: savings.when(
                    data: (data) => _RecentList(
                      transactions: data.transactions.take(4).toList(),
                    ),
                    loading: () => const PaCard(
                      padding: EdgeInsets.symmetric(vertical: 18, horizontal: 16),
                      child: PaShimmerList(count: 3),
                    ),
                    error: (e, _) => PaCard(
                      child: Text(
                        l.home_history_unavailable,
                        style: const TextStyle(color: PaColors.inkMuted),
                      ),
                    ),
                  ),
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
    );
  }

  static Future<void> _openDeposit(BuildContext context) {
    return showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      backgroundColor: PaColors.paper,
      barrierColor: PaColors.navyDeep.withValues(alpha: 0.55),
      enableDrag: true,
      shape: const RoundedRectangleBorder(borderRadius: AppRadii.sheet),
      builder: (_) => const DepositSheet(),
    );
  }

  /// Calcule le label "X opération(s) en attente" si pertinent, ou null.
  static String? _pendingLabel(SavingsAccount data) {
    final count = data.transactions
        .where((t) => false)  // placeholder — Tara pending flow à brancher
        .length;
    if (count <= 0) return null;
    return 'Voir $count opération${count > 1 ? 's' : ''} en attente';
  }
}


// ───────────────────────────────────────────────────────────────────────────
// Header — avatar circulaire avec initiale + greeting + cloche notif
// ───────────────────────────────────────────────────────────────────────────

class _Header extends StatelessWidget {
  const _Header({required this.firstName, required this.unread});

  final String firstName;
  final int unread;

  @override
  Widget build(BuildContext context) {
    final l = AppL10n.of(context);
    final hour = DateTime.now().hour;
    final greeting = hour < 5
        ? l.home_greeting_night
        : hour < 12
            ? l.home_greeting_morning
            : hour < 18
                ? l.home_greeting_afternoon
                : l.home_greeting_evening;
    return Row(
      children: [
        // Avatar génératif — gradient unique dérivé du nom du membre
        PaAvatar(seed: firstName, size: 44),
        const SizedBox(width: 12),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                greeting,
                style: PaText.body(
                  size: 12.5,
                  weight: FontWeight.w500,
                  color: PaColors.inkMuted,
                ),
              ),
              const SizedBox(height: 2),
              Text(
                firstName,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: PaText.heading(size: 19),
              ),
            ],
          ),
        ),
        _NotifBell(unread: unread),
      ],
    );
  }
}


class _NotifBell extends StatelessWidget {
  const _NotifBell({this.unread = 0});

  final int unread;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      customBorder: const CircleBorder(),
      onTap: () => context.push('/notifications'),
      child: Container(
        width: 44,
        height: 44,
        decoration: BoxDecoration(
          color: PaColors.paper,
          shape: BoxShape.circle,
          border: Border.all(color: PaColors.line, width: 1),
        ),
        child: Stack(
          children: [
            const Center(
              child: Icon(
                Icons.notifications_none_rounded,
                color: PaColors.navy,
                size: 22,
              ),
            ),
            if (unread > 0)
              Positioned(
                top: 6,
                right: 8,
                child: Container(
                  constraints: const BoxConstraints(minWidth: 14, minHeight: 14),
                  padding: const EdgeInsets.symmetric(horizontal: 3, vertical: 1),
                  decoration: BoxDecoration(
                    color: PaColors.danger,
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(color: PaColors.paper, width: 1.5),
                  ),
                  alignment: Alignment.center,
                  child: Text(
                    unread > 9 ? '9+' : '$unread',
                    style: const TextStyle(
                      color: Colors.white,
                      fontSize: 9.5,
                      fontWeight: FontWeight.w700,
                      height: 1.1,
                    ),
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }
}


// ───────────────────────────────────────────────────────────────────────────
// Liste des opérations récentes (4 max) — PaCard wrapping 4 PaTransactionTile
// ───────────────────────────────────────────────────────────────────────────

class _RecentList extends StatelessWidget {
  const _RecentList({required this.transactions});

  final List<SavingsTransaction> transactions;

  @override
  Widget build(BuildContext context) {
    final l = AppL10n.of(context);

    if (transactions.isEmpty) {
      return PaCard(
        padding: const EdgeInsets.symmetric(vertical: 22, horizontal: 16),
        child: Center(
          child: Text(
            l.home_no_operations,
            style: const TextStyle(color: PaColors.inkMuted),
          ),
        ),
      );
    }

    return PaCard(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 4),
      child: Column(
        children: [
          for (var i = 0; i < transactions.length; i++) ...[
            PaTransactionTile(
              kind: _mapKind(transactions[i].type),
              label: _label(l, transactions[i].type),
              time: AppDateFormatter.withTime(transactions[i].date),
              amount: transactions[i].montant,
            ),
            if (i < transactions.length - 1)
              const Divider(
                height: 1,
                thickness: 0.6,
                color: PaColors.line,
              ),
          ],
        ],
      ),
    );
  }

  PaTxKind _mapKind(SavingsType t) => switch (t) {
        SavingsType.depot => PaTxKind.depot,
        SavingsType.interet => PaTxKind.interet,
        SavingsType.retrait => PaTxKind.retrait,
      };

  String _label(AppL10n l, SavingsType t) => switch (t) {
        SavingsType.depot => l.tx_deposit,
        SavingsType.interet => l.tx_interest,
        SavingsType.retrait => l.tx_withdrawal,
      };
}


// ───────────────────────────────────────────────────────────────────────────
// Skeleton + error fallback du hero
// ───────────────────────────────────────────────────────────────────────────

class _HeroSkeleton extends StatelessWidget {
  const _HeroSkeleton();

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 140,
      decoration: BoxDecoration(
        color: PaColors.cardBg,
        borderRadius: BorderRadius.circular(24),
      ),
      padding: const EdgeInsets.all(20),
      child: const PaShimmer(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            PaShimmerBox(width: 110, height: 12),
            PaShimmerBox(width: 200, height: 32, borderRadius: 6),
            PaShimmerBox(width: 140, height: 14),
          ],
        ),
      ),
    );
  }
}


class _HeroError extends StatelessWidget {
  const _HeroError({required this.message});
  final String message;

  @override
  Widget build(BuildContext context) {
    final l = AppL10n.of(context);
    return PaCard(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Icon(Icons.error_outline, color: PaColors.danger, size: 24),
          const SizedBox(height: 8),
          Text(
            l.home_balance_unavailable,
            style: const TextStyle(
              color: PaColors.danger,
              fontSize: 16,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            message,
            style: const TextStyle(color: PaColors.inkMuted, fontSize: 12.5),
          ),
        ],
      ),
    );
  }
}
