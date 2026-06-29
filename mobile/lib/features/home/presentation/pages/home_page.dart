import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../../app/theme/app_radii.dart';
import '../../../../app/theme/paysika/pa_colors.dart';
import '../../../../app/theme/paysika/pa_typography.dart';
import '../../../../core/formatters/date_formatter.dart';
import '../../../../core/widgets/live_poller.dart';
import '../../../../core/widgets/paysika/pa_action_pill.dart';
import '../../../../core/widgets/paysika/pa_avatar.dart';
import '../../../../core/widgets/paysika/pa_card.dart';
import '../../../../core/widgets/paysika/pa_dual_hero_balance.dart';
import '../../../../core/widgets/paysika/pa_logo.dart';
import '../../../../core/widgets/paysika/pa_pattern_background.dart';
import '../../../../core/widgets/paysika/pa_info_carousel.dart';
import '../../../../core/widgets/paysika/pa_shimmer.dart';
import '../../../../core/widgets/paysika/pa_transaction_tile.dart';
import '../../../security/presentation/widgets/pin_prompt_sheet.dart';
import '../../../../l10n/gen/app_localizations.dart';
import '../../../auth/domain/entities/member.dart';
import '../../../auth/presentation/state/auth_notifier.dart';
import '../../../booklet/presentation/widgets/order_booklet_sheet.dart';
import '../../data/renewal_status_provider.dart';
import '../../../home_feed/presentation/state/feed_notifier.dart';
import '../../../home_feed/presentation/widgets/feed_sections.dart';
import '../../../notifications/presentation/state/notifications_notifier.dart';
import '../../../savings/domain/entities/savings_account.dart';
import '../../../savings/domain/entities/savings_transaction.dart';
import '../../../savings/presentation/state/classic_savings_notifier.dart';
import '../../../savings/presentation/state/savings_notifier.dart';
import '../widgets/deposit_sheet.dart';

/// Accueil . **prototype Paysika** (style validé sur captures `capture_paysika/`).
///
/// Composition :
///   1. Header sobre . avatar greeting + cloche notifications
///   2. Hero balance . card gradient aurore teal→navy avec CTA Verser
///   3. Quick actions . 4 cercles outlined (Verser, Crédit, Carnet, Historique)
///   4. Services . grille 2 colonnes (Demander crédit, Carnet, États, Aide)
///   5. Recent transactions . header + 4 dernières tiles avatar
class HomePage extends ConsumerWidget {
  const HomePage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final member = ref.watch(authProvider).valueOrNull;
    // Hero présente les 2 soldes (épargne classique + cotisation journalière)
    // via un toggle segmenté ergonomique. La card hero est **pinned** hors
    // du scroll : elle reste toujours visible quand on défile la Home.
    final epargne = ref.watch(classicSavingsProvider);
    final cotisation = ref.watch(savingsProvider);
    final l = AppL10n.of(context);
    final firstName = member?.prenom ?? l.profile_member_badge;

    return Scaffold(
      backgroundColor: PaColors.canvas,
      body: PaPatternBackground(
        child: SafeArea(
        bottom: false,
        child: Column(
          children: [
            // Polling 30s sur les 2 soldes (epargne + cotisation) pour voir
            // un cash-in admin sans pull-to-refresh. Idempotent via hash JSON.
            LivePoller(
              refresh: () => ref.read(classicSavingsProvider.notifier).refresh(),
              readSnapshot: () => ref.read(classicSavingsProvider).valueOrNull,
            ),
            LivePoller(
              refresh: () => ref.read(savingsProvider.notifier).refresh(),
              readSnapshot: () => ref.read(savingsProvider).valueOrNull,
            ),
            // ── Header FIXE (ne défile pas) . logo + greeting + cloche ──
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 10, 16, 8),
              child: _Header(
                firstName: firstName,
                unread: ref.watch(unreadNotifsCountProvider),
              ),
            ),
            // CH-2 . Bannière statut quand le membre n'est pas encore actif.
            if (member != null && member.statut != MemberStatus.actif)
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 0, 16, 6),
                child: _StatusBanner(status: member.statut),
              ),
            // D5 . Banniere renouvellement annuel.
            const _RenewalBanner(),
            // ── Hero PINNED (sortie des slivers) . toggle dual balance ──
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 6, 16, 12),
              child: _PinnedDualHero(
                epargne: epargne,
                cotisation: cotisation,
                onEpargneDeposit: () => _openClassicDeposit(context),
                onCotisationDeposit: () => _openDeposit(context),
                onReveal: () => PinPromptSheet.show(context),
                deltaLabelFmt: (s) => l.home_delta_this_month(s),
              ),
            ),
            Expanded(
              child: RefreshIndicator.adaptive(
          color: PaColors.teal,
          // Refresh global : on rafraîchit les 2 comptes pour que le hero
          // (épargne + cotisation) ET le feed se mettent à jour ensemble.
          onRefresh: () async {
            await Future.wait([
              ref.read(classicSavingsProvider.notifier).refresh(),
              ref.read(savingsProvider.notifier).refresh(),
              ref.read(homeFeedProvider.notifier).refresh(),
            ]);
          },
          child: CustomScrollView(
            physics: const AlwaysScrollableScrollPhysics(),
            slivers: [
              // ── Quick actions . 4 cercles outlined ─────────────────────
              SliverToBoxAdapter(
                child: Padding(
                  padding: const EdgeInsets.fromLTRB(16, 4, 16, 20),
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      // ── Pills dissociés épargne vs cotisation ─────────
                      // Le pill "Verser" générique brouillait la distinction
                      // backend (épargne classique vs cotisation journalière) :
                      // remplacé par 2 pills dédiés ouvrant chacun la sheet
                      // appropriée. Carnet retiré (déjà dans le bottom nav).
                      PaActionPill(
                        icon: Icons.savings_outlined,
                        label: l.home_action_savings,
                        onTap: () => _openClassicDeposit(context),
                      ),
                      PaActionPill(
                        icon: Icons.calendar_today_outlined,
                        label: l.home_action_cotisation,
                        onTap: () => _openDeposit(context),
                      ),
                      PaActionPill(
                        icon: Icons.account_balance_outlined,
                        label: l.home_action_credit,
                        onTap: () => context.go('/credit'),
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

              // NOTE : la card _CotisationCard a été retirée . la cotisation
              // est désormais accessible via la pill "Cotisation" en haut, et
              // le badge LOT 4 (commission 1%) sera réintégré ailleurs si
              // besoin. Évite la redondance UI signalée par le client.

              // ── Section "Campagnes en cours" (LOT 11 micro-crédit) ──
              // Tap sur une card → ouvre la liste des campagnes (la liste
              // gère ensuite le scroll/focus sur l'item). Pas de detail page
              // dédiée pour l'instant : la liste suffit à la démo NHR.
              SliverToBoxAdapter(
                child: CampaignsSection(
                  onSeeMore: () => context.push('/campaigns'),
                  onTapCampaign: (_) => context.push('/campaigns'),
                ),
              ),

              // ── Section "Actualités" (Wagtail blog) ────────────────────
              // Tap sur une card → ouvre la NewsDetailPage. L'article est
              // passé en `extra` pour un rendu instantané (cf. router).
              SliverToBoxAdapter(
                child: NewsSection(
                  onSeeMore: () => context.push('/news'),
                  onTapArticle: (a) =>
                      context.push('/news/${a.id}', extra: a),
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
                  child: epargne.when(
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
      constraints: BoxConstraints(
        maxHeight: MediaQuery.sizeOf(context).height * 0.9,
      ),
      backgroundColor: PaColors.paper,
      barrierColor: PaColors.navyDeep.withValues(alpha: 0.55),
      enableDrag: true,
      shape: const RoundedRectangleBorder(borderRadius: AppRadii.sheet),
      builder: (_) => const DepositSheet(),
    );
  }

  static Future<void> _openClassicDeposit(BuildContext context) {
    return showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      constraints: BoxConstraints(
        maxHeight: MediaQuery.sizeOf(context).height * 0.9,
      ),
      backgroundColor: PaColors.paper,
      barrierColor: PaColors.navyDeep.withValues(alpha: 0.55),
      enableDrag: true,
      shape: const RoundedRectangleBorder(borderRadius: AppRadii.sheet),
      builder: (_) => const DepositSheet(classic: true),
    );
  }

}


// ───────────────────────────────────────────────────────────────────────────
// Header . avatar circulaire avec initiale + greeting + cloche notif
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
    // Header compact 1 ligne : logo + (avatar + greeting/prénom à côté de la
    // cloche) . gain ~50px verticaux vs l'ancien layout sur 2 lignes.
    return Row(
      children: [
        const PaLogo(height: 22),
        const Spacer(),
        PaAvatar(seed: firstName, size: 28),
        const SizedBox(width: 8),
        Flexible(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                greeting,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: PaText.body(
                  size: 10.5,
                  weight: FontWeight.w500,
                  color: PaColors.inkMuted,
                  height: 1.1,
                ),
              ),
              Text(
                firstName,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: PaText.heading(size: 13.5),
              ),
            ],
          ),
        ),
        const SizedBox(width: 10),
        _NotifBell(unread: unread),
      ],
    );
  }
}


/// Hero pinned dual-balance . résout les 2 AsyncValue et alimente
/// `PaDualHeroBalance`. État loading/error géré localement pour ne pas
/// casser le rendu pinned.
class _PinnedDualHero extends StatelessWidget {
  const _PinnedDualHero({
    required this.epargne,
    required this.cotisation,
    required this.onEpargneDeposit,
    required this.onCotisationDeposit,
    required this.onReveal,
    required this.deltaLabelFmt,
  });

  final AsyncValue<SavingsAccount> epargne;
  final AsyncValue<SavingsAccount> cotisation;
  final VoidCallback onEpargneDeposit;
  final VoidCallback onCotisationDeposit;
  final Future<bool> Function() onReveal;
  final String Function(String) deltaLabelFmt;

  @override
  Widget build(BuildContext context) {
    // Si l'une des sources est en erreur, on dégrade gracieusement avec
    // un fallback 0 plutôt que de cacher tout le hero. Le pinned doit
    // toujours rester visible . c'est sa raison d'être.
    final ePart = epargne.valueOrNull;
    final cPart = cotisation.valueOrNull;
    if (ePart == null && cPart == null) {
      // Vraiment rien à montrer (premier chargement) → skeleton.
      return const _HeroSkeleton();
    }
    final eTrend = ePart != null ? _balanceTrend(ePart) : null;
    final eDelta = _monthDelta(eTrend);
    final cTrend = cPart != null ? _balanceTrend(cPart) : null;
    final cDelta = _monthDelta(cTrend);
    return PaDualHeroBalance(
      savings: PaHeroSlot(
        amount: ePart?.solde ?? 0,
        label: 'Mon épargne',
        ctaLabel: 'Verser sur épargne',
        onDeposit: onEpargneDeposit,
        trend: eTrend,
        deltaLabel: eDelta == null ? null : deltaLabelFmt(eDelta.$1),
        deltaPositive: eDelta?.$2 ?? true,
      ),
      cotisation: PaHeroSlot(
        amount: cPart?.solde ?? 0,
        label: 'Ma collecte',
        ctaLabel: 'Payer ma collecte',
        onDeposit: onCotisationDeposit,
        trend: cTrend,
        deltaLabel: cDelta == null ? null : deltaLabelFmt(cDelta.$1),
        deltaPositive: cDelta?.$2 ?? true,
      ),
      onRequestReveal: onReveal,
    );
  }

  static List<num>? _balanceTrend(SavingsAccount data) {
    final txs = [...data.transactions]
      ..sort((a, b) => a.date.compareTo(b.date));
    if (txs.length < 2) return null;
    final series = txs.map((t) => t.soldeApres).toList();
    return series.length > 8 ? series.sublist(series.length - 8) : series;
  }

  static (String, bool)? _monthDelta(List<num>? trend) {
    if (trend == null || trend.length < 2) return null;
    final first = trend.first.toDouble();
    final last = trend.last.toDouble();
    if (first <= 0) return null;
    final pct = (last - first) / first * 100;
    final positive = pct >= 0;
    // Cap d'affichage : au-delà de ±99 %, on affiche '>99 %' pour éviter
    // que la chip ne déborde du hero et fasse varier sa hauteur.
    final abs = pct.abs();
    final formatted = abs > 99
        ? '${positive ? '+' : '-'}>99 %'
        : '${positive ? '+' : ''}${pct.toStringAsFixed(1).replaceAll('.', ',')} %';
    return (formatted, positive);
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
        width: 36,
        height: 36,
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
                size: 18,
              ),
            ),
            if (unread > 0)
              Positioned(
                top: 4,
                right: 5,
                child: Container(
                  constraints: const BoxConstraints(minWidth: 12, minHeight: 12),
                  padding: const EdgeInsets.symmetric(horizontal: 2.5, vertical: 0.5),
                  decoration: BoxDecoration(
                    color: PaColors.danger,
                    borderRadius: BorderRadius.circular(7),
                    border: Border.all(color: PaColors.paper, width: 1.2),
                  ),
                  alignment: Alignment.center,
                  child: Text(
                    unread > 9 ? '9+' : '$unread',
                    style: const TextStyle(
                      color: Colors.white,
                      fontSize: 8.5,
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
// Liste des opérations récentes (4 max) . PaCard wrapping 4 PaTransactionTile
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
    // Dimensions calquées sur PaDualHeroBalance pour éviter le "saut" de
    // hauteur quand le hero charge ses données.
    return Container(
      width: double.infinity,
      decoration: BoxDecoration(
        color: PaColors.cardBg,
        borderRadius: BorderRadius.circular(14),
      ),
      padding: const EdgeInsets.fromLTRB(14, 12, 14, 12),
      child: const PaShimmer(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            // Toggle segmenté Épargne / Cotisations
            PaShimmerBox(width: double.infinity, height: 28, borderRadius: 9),
            SizedBox(height: 10),
            // Label du slot + delta (même ligne, hauteur fixe)
            Row(
              children: [
                PaShimmerBox(width: 110, height: 11),
                Spacer(),
                PaShimmerBox(width: 56, height: 14, borderRadius: 7),
              ],
            ),
            SizedBox(height: 4),
            // Montant
            PaShimmerBox(width: 200, height: 26, borderRadius: 6),
            SizedBox(height: 10),
            // CTA
            PaShimmerBox(width: double.infinity, height: 38, borderRadius: 10),
          ],
        ),
      ),
    );
  }
}




// ───────────────────────────────────────────────────────────────────────────
// Bannière statut (CH-2) . affichée quand le membre n'est pas actif :
// - temporaire (LOT 11) : compte créé après crédit campagne, doit payer
//   ses frais d'inscription pour basculer actif et accéder à l'épargne.
// - suspendu : sanction administrative, doit régulariser sa situation.
// - radie : exclusion définitive . pour info, pas de CTA.
// ───────────────────────────────────────────────────────────────────────────

class _StatusBanner extends StatelessWidget {
  const _StatusBanner({required this.status});

  final MemberStatus status;

  @override
  Widget build(BuildContext context) {
    final (icon, title, sub, bg, fg) = switch (status) {
      MemberStatus.temporaire => (
        Icons.info_outline_rounded,
        'Compte temporaire',
        "Paie tes frais d'inscription pour activer ton compte complet.",
        PaColors.warningSurface,
        PaColors.warning,
      ),
      MemberStatus.suspendu => (
        Icons.pause_circle_outline_rounded,
        'Compte suspendu',
        'Contacte la coopérative pour régulariser ta situation.',
        PaColors.dangerSurface,
        PaColors.danger,
      ),
      MemberStatus.radie => (
        Icons.block_rounded,
        'Compte radié',
        "Tu n'as plus accès aux services de la coopérative.",
        PaColors.dangerSurface,
        PaColors.danger,
      ),
      MemberStatus.actif => (
        Icons.check_circle_outline_rounded,
        'Compte actif',
        '',
        PaColors.successSurface,
        PaColors.success,
      ),
    };
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 11),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: fg.withValues(alpha: 0.25), width: 1),
      ),
      child: Row(
        children: [
          Icon(icon, color: fg, size: 20),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  title,
                  style: TextStyle(
                    color: fg,
                    fontSize: 13.5,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                if (sub.isNotEmpty) ...[
                  const SizedBox(height: 2),
                  Text(
                    sub,
                    style: const TextStyle(
                      color: PaColors.inkSecondary,
                      fontSize: 12,
                      height: 1.3,
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
}


// D5 . Banniere renouvellement annuel d'adhesion.
// Visible quand l'utilisateur entre dans la fenetre (J-30 avant
// l'anniversaire) ou si son compte est suspendu pour non-renouvellement.
// Tap -> ouvre le OrderBookletSheet (paiement frais_carnet via Tara).
// Le hook backend _hook_carnet_fees detecte automatiquement le renouvellement.
class _RenewalBanner extends ConsumerWidget {
  const _RenewalBanner();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(renewalStatusProvider);
    return async.maybeWhen(
      data: (status) {
        if (status == null || !status.shouldShowBanner) {
          return const SizedBox.shrink();
        }
        final isSuspended = status.isSuspended;
        final daysLeft = status.daysUntilExpiry;
        final message = isSuspended
            ? 'Compte suspendu. Paie ton carnet annuel pour reactiver.'
            : (daysLeft != null && daysLeft < 0)
                ? 'Anniversaire annuel depasse de ${daysLeft.abs()} jour(s).'
                : (daysLeft != null && daysLeft == 0)
                    ? 'Anniversaire annuel . renouvelle aujourd\'hui.'
                    : 'Renouvellement annuel dans ${daysLeft ?? 0} jour(s).';
        final accent = isSuspended
            ? const Color(0xFFBA2121)
            : PaColors.warning;
        return Padding(
          padding: const EdgeInsets.fromLTRB(16, 0, 16, 6),
          child: Material(
            color: accent.withValues(alpha: 0.10),
            borderRadius: AppRadii.card,
            child: InkWell(
              borderRadius: AppRadii.card,
              onTap: () {
                showModalBottomSheet<void>(
                  context: context,
                  isScrollControlled: true,
                  backgroundColor: Colors.transparent,
                  builder: (_) => const OrderBookletSheet(),
                );
              },
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
                decoration: BoxDecoration(
                  border: Border.all(color: accent.withValues(alpha: 0.35)),
                  borderRadius: AppRadii.card,
                  color: Colors.transparent,
                ),
                child: Row(
                  children: [
                    Icon(
                      isSuspended
                          ? Icons.lock_outline_rounded
                          : Icons.event_repeat_rounded,
                      color: accent,
                      size: 20,
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            isSuspended
                                ? 'Reactivation requise'
                                : 'Renouvellement d\'adhesion',
                            style: PaText.body(size: 13).copyWith(
                              color: PaColors.inkPrimary,
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                          const SizedBox(height: 2),
                          Text(
                            message,
                            style: PaText.body(size: 12).copyWith(
                              color: PaColors.inkSecondary,
                            ),
                          ),
                        ],
                      ),
                    ),
                    Icon(
                      Icons.arrow_forward_rounded,
                      color: accent,
                      size: 18,
                    ),
                  ],
                ),
              ),
            ),
          ),
        );
      },
      orElse: () => const SizedBox.shrink(),
    );
  }
}
