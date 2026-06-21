import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../../app/theme/paysika/pa_colors.dart';
import '../../../../core/formatters/xaf_formatter.dart';
import '../../../../core/widgets/paysika/pa_card.dart';
import '../../../../core/widgets/paysika/pa_pattern_background.dart';
import '../../domain/entities/feed_item.dart';
import '../state/feed_notifier.dart';

/// Page in-app qui liste toutes les campagnes micro-crédit actives.
/// Atteinte depuis le "Voir plus" du carousel Home. Lazy-load au scroll
/// vertical : charge la page suivante à 200 px du bas. Tap sur une carte
/// → renvoie l'id de la campagne via `Navigator.pop` pour que le caller
/// déclenche le sheet de demande de crédit pré-rempli (voie campagne).
class CampaignsListPage extends ConsumerStatefulWidget {
  const CampaignsListPage({super.key});

  @override
  ConsumerState<CampaignsListPage> createState() => _CampaignsListPageState();
}

class _CampaignsListPageState extends ConsumerState<CampaignsListPage> {
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
      body: PaPatternBackground(
        child: RefreshIndicator.adaptive(
          color: PaColors.teal,
          onRefresh: () => ref.read(homeFeedProvider.notifier).refresh(),
          child: campaigns.isEmpty && !loading
              ? const _EmptyState()
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
                      onTap: () => context.pop(campaigns[i].id),
                    );
                  },
                ),
        ),
      ),
    );
  }
}

class _CampaignRow extends StatelessWidget {
  const _CampaignRow({required this.c, required this.onTap});
  final CampaignFlyer c;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return PaCard(
      padding: EdgeInsets.zero,
      onTap: onTap,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          ClipRRect(
            borderRadius: const BorderRadius.vertical(
              top: Radius.circular(20),
            ),
            child: AspectRatio(
              aspectRatio: 16 / 9,
              child: c.flyerUrl == null
                  ? _Placeholder(label: c.profilCible)
                  : CachedNetworkImage(
                      imageUrl: c.flyerUrl!,
                      fit: BoxFit.cover,
                      placeholder: (_, __) =>
                          _Placeholder(label: c.profilCible),
                      errorWidget: (_, __, ___) =>
                          _Placeholder(label: c.profilCible),
                    ),
            ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 14, 16, 16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 8,
                        vertical: 3,
                      ),
                      decoration: BoxDecoration(
                        color: PaColors.tealSurface,
                        borderRadius: BorderRadius.circular(999),
                      ),
                      child: Text(
                        c.profilCible.toUpperCase(),
                        style: const TextStyle(
                          color: PaColors.teal,
                          fontSize: 10,
                          fontWeight: FontWeight.w800,
                          letterSpacing: 1.2,
                        ),
                      ),
                    ),
                    const Spacer(),
                    Text(
                      'Clôture ${_d(c.dateFin)}',
                      style: const TextStyle(
                        color: PaColors.inkMuted,
                        fontSize: 11.5,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 10),
                Text(
                  c.nom,
                  style: const TextStyle(
                    color: PaColors.inkPrimary,
                    fontSize: 16,
                    fontWeight: FontWeight.w700,
                    height: 1.25,
                  ),
                ),
                const SizedBox(height: 10),
                Row(
                  children: [
                    const Icon(Icons.payments_outlined,
                        size: 16, color: PaColors.teal),
                    const SizedBox(width: 6),
                    Expanded(
                      child: Text(
                        '${XAFFormatter.formatCompact(c.montantMin)}  →  ${XAFFormatter.formatCompact(c.montantMax)}',
                        style: const TextStyle(
                          color: PaColors.inkSecondary,
                          fontSize: 13,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ),
                    Text(
                      '${(c.tauxInteret * 100).toStringAsFixed(0)} %',
                      style: const TextStyle(
                        color: PaColors.teal,
                        fontSize: 13,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                Row(
                  mainAxisAlignment: MainAxisAlignment.end,
                  children: [
                    Text(
                      'Postuler',
                      style: const TextStyle(
                        color: PaColors.teal,
                        fontSize: 13.5,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    const SizedBox(width: 2),
                    const Icon(Icons.arrow_forward_rounded,
                        size: 18, color: PaColors.teal),
                  ],
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
      children: [
        const SizedBox(height: 80),
        const Icon(Icons.campaign_outlined,
            color: PaColors.inkMuted, size: 56),
        const SizedBox(height: 16),
        const Center(
          child: Padding(
            padding: EdgeInsets.symmetric(horizontal: 40),
            child: Text(
              'Aucune campagne active en ce moment.\n'
              'Reviens plus tard ou tire vers le bas pour rafraîchir.',
              textAlign: TextAlign.center,
              style: TextStyle(
                color: PaColors.inkMuted,
                fontSize: 13,
              ),
            ),
          ),
        ),
      ],
    );
  }
}
