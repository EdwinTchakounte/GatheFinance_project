import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../../app/theme/paysika/pa_colors.dart';
import '../../../../core/formatters/xaf_formatter.dart';
import '../../../../core/widgets/paysika/pa_card.dart';
import '../../../../core/widgets/paysika/pa_empty_state.dart';
import '../../../../core/widgets/paysika/pa_error_state.dart';
import '../../../../core/widgets/paysika/pa_pattern_background.dart';
import '../../domain/entities/feed_item.dart';
import '../state/feed_notifier.dart';

/// Page in-app qui liste toutes les campagnes micro-crédit actives.
/// Atteinte depuis le "Voir plus" du carousel Home. Lazy-load au scroll
/// vertical : charge la page suivante à 200 px du bas. Tap sur une carte
/// → renvoie l'id de la campagne via `Navigator.pop` pour que le caller
/// déclenche le sheet de demande de crédit pré-rempli (voie campagne).
class CampaignsListPage extends StatelessWidget {
  const CampaignsListPage({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: PaColors.canvas,
      appBar: AppBar(
        backgroundColor: PaColors.canvas,
        surfaceTintColor: PaColors.canvas,
        elevation: 0,
        scrolledUnderElevation: 0,
        centerTitle: true,
        iconTheme: const IconThemeData(color: PaColors.inkPrimary),
        title: const Text(
          'Campagnes en cours',
          style: TextStyle(
            color: PaColors.inkPrimary,
            fontSize: 17,
            fontWeight: FontWeight.w700,
          ),
        ),
      ),
      body: const PaPatternBackground(child: CampaignsListBody()),
    );
  }
}

/// Corps réutilisable de la liste des campagnes (sans Scaffold/AppBar).
class CampaignsListBody extends ConsumerStatefulWidget {
  const CampaignsListBody({super.key});

  @override
  ConsumerState<CampaignsListBody> createState() => _CampaignsListBodyState();
}

class _CampaignsListBodyState extends ConsumerState<CampaignsListBody> {
  final _scroll = ScrollController();

  @override
  void initState() {
    super.initState();
    _scroll.addListener(_onScroll);
  }

  @override
  void dispose() {
    _scroll.removeListener(_onScroll);
    _scroll.dispose();
    super.dispose();
  }

  void _onScroll() {
    if (_scroll.position.pixels > _scroll.position.maxScrollExtent - 200) {
      ref.read(homeFeedProvider.notifier).loadMoreCampaigns();
    }
  }

  @override
  Widget build(BuildContext context) {
    final feed = ref.watch(homeFeedProvider).valueOrNull;
    final campaigns = feed?.campaigns ?? const <CampaignFlyer>[];
    final loading = feed?.campaignsLoading ?? false;
    final hasError = feed?.campaignsError ?? false;

    return RefreshIndicator.adaptive(
      color: PaColors.teal,
      onRefresh: () => ref.read(homeFeedProvider.notifier).refresh(),
      child: campaigns.isEmpty && !loading
          ? (hasError
              ? PaErrorState(
                  message: 'Impossible de charger les campagnes.',
                  onRetry: () => ref.read(homeFeedProvider.notifier).refresh(),
                )
              : const _EmptyState())
          : ListView.separated(
              controller: _scroll,
              physics: const AlwaysScrollableScrollPhysics(),
              padding: const EdgeInsets.fromLTRB(16, 12, 16, 24),
              itemCount: campaigns.length + (loading ? 1 : 0),
              separatorBuilder: (_, __) => const SizedBox(height: 12),
              itemBuilder: (_, i) {
                if (i >= campaigns.length) {
                  return const Padding(
                    padding: EdgeInsets.symmetric(vertical: 24),
                    child: Center(
                      child: SizedBox(
                        width: 22,
                        height: 22,
                        child: CircularProgressIndicator(
                          strokeWidth: 2.4,
                          color: PaColors.teal,
                        ),
                      ),
                    ),
                  );
                }
                return _CampaignRow(
                  c: campaigns[i],
                  onOpen: () => context.pushNamed(
                    'campaign-detail',
                    pathParameters: {'id': '${campaigns[i].id}'},
                    extra: campaigns[i],
                  ),
                );
              },
            ),
    );
  }
}

class _CampaignRow extends StatelessWidget {
  const _CampaignRow({required this.c, required this.onOpen});
  final CampaignFlyer c;
  final VoidCallback onOpen;

  @override
  Widget build(BuildContext context) {
    // Urgence : jours restants avant clôture (pastille sur l'image).
    final daysLeft = c.dateFin.difference(DateTime.now()).inDays;
    final urgent = daysLeft >= 0 && daysLeft <= 7;
    final urgencyText = daysLeft < 0
        ? 'Clôturée'
        : daysLeft == 0
            ? 'Dernier jour'
            : daysLeft <= 7
                ? 'Se termine dans ${daysLeft}j'
                : 'Clôture ${_d(c.dateFin)}';

    return PaCard(
      padding: EdgeInsets.zero,
      onTap: onOpen,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // ── Visuel : image + dégradé + pastilles flottantes ────────────
          ClipRRect(
            borderRadius: const BorderRadius.vertical(top: Radius.circular(14)),
            child: AspectRatio(
              aspectRatio: 16 / 9,
              child: Stack(
                fit: StackFit.expand,
                children: [
                  c.flyerUrl == null
                      ? _Placeholder(label: c.profilCible)
                      : CachedNetworkImage(
                          imageUrl: c.flyerUrl!,
                          fit: BoxFit.cover,
                          memCacheWidth: 720,
                          placeholder: (_, __) =>
                              _Placeholder(label: c.profilCible),
                          errorWidget: (_, __, ___) =>
                              _Placeholder(label: c.profilCible),
                        ),
                  // Dégradé bas → lisibilité + profondeur.
                  const Positioned(
                    left: 0,
                    right: 0,
                    bottom: 0,
                    child: _Scrim(),
                  ),
                  // Pastille profil cible (haut-gauche).
                  Positioned(
                    top: 12,
                    left: 12,
                    child: _Pill(
                      text: c.profilCible.toUpperCase(),
                      bg: Colors.white.withValues(alpha: 0.92),
                      fg: PaColors.teal,
                    ),
                  ),
                  // Pastille urgence (haut-droite).
                  Positioned(
                    top: 12,
                    right: 12,
                    child: _Pill(
                      text: urgencyText,
                      bg: urgent
                          ? PaColors.warning
                          : Colors.black.withValues(alpha: 0.45),
                      fg: Colors.white,
                      icon: Icons.schedule_rounded,
                    ),
                  ),
                ],
              ),
            ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 14, 16, 14),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  c.nom,
                  style: const TextStyle(
                    color: PaColors.inkPrimary,
                    fontSize: 16.5,
                    fontWeight: FontWeight.w700,
                    height: 1.25,
                  ),
                ),
                const SizedBox(height: 12),
                // Bloc chiffres : montant + taux, sur fond doux.
                Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                  decoration: BoxDecoration(
                    color: PaColors.tealSurface.withValues(alpha: 0.5),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Row(
                    children: [
                      const Icon(Icons.payments_outlined,
                          size: 17, color: PaColors.teal,),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          '${XAFFormatter.formatCompact(c.montantMin)}  →  ${XAFFormatter.formatCompact(c.montantMax)}',
                          style: const TextStyle(
                            color: PaColors.inkPrimary,
                            fontSize: 13.5,
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                      ),
                      Text(
                        '${(c.tauxInteret * 100).toStringAsFixed(0)} % / crédit',
                        style: const TextStyle(
                          color: PaColors.teal,
                          fontSize: 12.5,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 12),
                // CTA pleine largeur « Postuler ».
                SizedBox(
                  width: double.infinity,
                  child: Container(
                    padding: const EdgeInsets.symmetric(vertical: 11),
                    decoration: BoxDecoration(
                      color: PaColors.teal,
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: const Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Text(
                          'Voir la campagne & postuler',
                          style: TextStyle(
                            color: Colors.white,
                            fontSize: 13.5,
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                        SizedBox(width: 4),
                        Icon(Icons.arrow_forward_rounded,
                            size: 18, color: Colors.white,),
                      ],
                    ),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  String _d(DateTime dt) =>
      '${dt.day.toString().padLeft(2, '0')}/${dt.month.toString().padLeft(2, '0')}';
}

/// Dégradé bas d'une image de carte (profondeur + lisibilité des pastilles).
class _Scrim extends StatelessWidget {
  const _Scrim();
  @override
  Widget build(BuildContext context) {
    return Container(
      height: 64,
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [Colors.transparent, Colors.black.withValues(alpha: 0.28)],
        ),
      ),
    );
  }
}

/// Pastille flottante posée sur l'image d'une carte (profil, urgence, date).
class _Pill extends StatelessWidget {
  const _Pill({required this.text, required this.bg, required this.fg, this.icon});
  final String text;
  final Color bg;
  final Color fg;
  final IconData? icon;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 4),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(999),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (icon != null) ...[
            Icon(icon, size: 12, color: fg),
            const SizedBox(width: 4),
          ],
          Text(
            text,
            style: TextStyle(
              color: fg,
              fontSize: 10.5,
              fontWeight: FontWeight.w800,
              letterSpacing: 0.5,
            ),
          ),
        ],
      ),
    );
  }
}

class _Placeholder extends StatelessWidget {
  const _Placeholder({required this.label});
  final String label;

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: const BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [PaColors.tealSurface, Color(0xFFD7EFE5)],
        ),
      ),
      alignment: Alignment.center,
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Icon(Icons.campaign_outlined, color: PaColors.teal, size: 44),
          const SizedBox(height: 8),
          Text(
            label.toUpperCase(),
            textAlign: TextAlign.center,
            style: const TextStyle(
              color: PaColors.teal,
              fontSize: 12,
              fontWeight: FontWeight.w800,
              letterSpacing: 1.2,
            ),
          ),
        ],
      ),
    );
  }
}

class _EmptyState extends StatelessWidget {
  const _EmptyState();

  @override
  Widget build(BuildContext context) {
    return ListView(
      physics: const AlwaysScrollableScrollPhysics(),
      children: const [
        SizedBox(height: 70),
        PaEmptyState(
          icon: Icons.campaign_outlined,
          title: 'Aucune campagne active',
          message: 'Reviens plus tard, ou tire vers le bas pour rafraîchir.',
        ),
      ],
    );
  }
}
