import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../../../app/theme/paysika/pa_colors.dart';
import '../../../../core/widgets/paysika/pa_card.dart';
import '../../domain/entities/feed_item.dart';
import '../state/feed_notifier.dart';

/// Section "Campagnes en cours" — carousel horizontal des flyers actifs.
/// Si la liste est vide, on ne rend rien (silencieux).
class CampaignsSection extends ConsumerWidget {
  const CampaignsSection({super.key, required this.onSeeMore});

  /// Appelé au clic "Voir plus" — ouvre la vitrine /campaigns.
  final VoidCallback onSeeMore;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final campaigns = ref.watch(activeCampaignsProvider);
    if (campaigns.isEmpty) return const SizedBox.shrink();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _SectionHeader(
          title: 'Campagnes en cours',
          onSeeMore: onSeeMore,
        ),
        SizedBox(
          height: 188,
          child: ListView.separated(
            scrollDirection: Axis.horizontal,
            padding: const EdgeInsets.symmetric(horizontal: 16),
            physics: const BouncingScrollPhysics(),
            itemCount: campaigns.length,
            separatorBuilder: (_, __) => const SizedBox(width: 12),
            itemBuilder: (_, i) => _CampaignCard(c: campaigns[i]),
          ),
        ),
      ],
    );
  }
}

/// Section "Actualités" — carousel horizontal des derniers articles.
class NewsSection extends ConsumerWidget {
  const NewsSection({super.key, required this.onSeeMore});
  final VoidCallback onSeeMore;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final articles = ref.watch(latestArticlesProvider);
    if (articles.isEmpty) return const SizedBox.shrink();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _SectionHeader(title: 'Actualités', onSeeMore: onSeeMore),
        SizedBox(
          height: 175,
          child: ListView.separated(
            scrollDirection: Axis.horizontal,
            padding: const EdgeInsets.symmetric(horizontal: 16),
            physics: const BouncingScrollPhysics(),
            itemCount: articles.length,
            separatorBuilder: (_, __) => const SizedBox(width: 12),
            itemBuilder: (_, i) => _ArticleCard(a: articles[i]),
          ),
        ),
      ],
    );
  }
}

class _SectionHeader extends StatelessWidget {
  const _SectionHeader({required this.title, required this.onSeeMore});
  final String title;
  final VoidCallback onSeeMore;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 14, 16, 8),
      child: Row(
        children: [
          Expanded(
            child: Text(
              title,
              style: const TextStyle(
                color: PaColors.inkPrimary,
                fontSize: 16,
                fontWeight: FontWeight.w700,
              ),
            ),
          ),
          TextButton(
            onPressed: onSeeMore,
            style: TextButton.styleFrom(
              padding: const EdgeInsets.symmetric(horizontal: 4),
              minimumSize: const Size(0, 0),
              tapTargetSize: MaterialTapTargetSize.shrinkWrap,
            ),
            child: const Text(
              'Voir plus',
              style: TextStyle(
                color: PaColors.teal,
                fontSize: 13.5,
                fontWeight: FontWeight.w700,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _CampaignCard extends StatelessWidget {
  const _CampaignCard({required this.c});
  final CampaignFlyer c;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: 252,
      child: PaCard(
        padding: EdgeInsets.zero,
        onTap: () => _openVitrineCampaigns(),
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
                    ? _PlaceholderFlyer(label: c.profilCible)
                    : CachedNetworkImage(
                        imageUrl: c.flyerUrl!,
                        fit: BoxFit.cover,
                        fadeInDuration: const Duration(milliseconds: 200),
                        placeholder: (_, __) =>
                            _PlaceholderFlyer(label: c.profilCible),
                        errorWidget: (_, __, ___) =>
                            _PlaceholderFlyer(label: c.profilCible),
                      ),
              ),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(12, 10, 12, 12),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    c.nom,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                      color: PaColors.inkPrimary,
                      fontSize: 13.5,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    'Jusqu’à ${c.montantMax.toInt()} XAF · clôture ${_d(c.dateFin)}',
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                      color: PaColors.inkMuted,
                      fontSize: 11.5,
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  static String _d(DateTime dt) =>
      '${dt.day.toString().padLeft(2, '0')}/${dt.month.toString().padLeft(2, '0')}';

  Future<void> _openVitrineCampaigns() async {
    // Stratégie pragmatique : la liste détaillée des campagnes vit sur la
    // vitrine. On délègue à url_launcher (pas de double-écran à maintenir).
    final uri = Uri.parse('http://10.93.197.210:3200/services/micro-credit');
    await launchUrl(uri, mode: LaunchMode.externalApplication);
  }
}

class _PlaceholderFlyer extends StatelessWidget {
  const _PlaceholderFlyer({required this.label});
  final String label;

  @override
  Widget build(BuildContext context) {
    return Container(
      color: PaColors.tealSurface,
      alignment: Alignment.center,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 12),
        child: Text(
          label.toUpperCase(),
          textAlign: TextAlign.center,
          style: const TextStyle(
            color: PaColors.teal,
            fontSize: 13,
            fontWeight: FontWeight.w800,
            letterSpacing: 1.2,
          ),
        ),
      ),
    );
  }
}

class _ArticleCard extends StatelessWidget {
  const _ArticleCard({required this.a});
  final NewsArticle a;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: 240,
      child: PaCard(
        padding: const EdgeInsets.all(14),
        onTap: () => _openArticle(a.htmlUrl),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
              decoration: BoxDecoration(
                color: PaColors.warningSurface,
                borderRadius: BorderRadius.circular(999),
              ),
              child: const Text(
                'Actualité',
                style: TextStyle(
                  color: PaColors.warning,
                  fontSize: 10.5,
                  fontWeight: FontWeight.w800,
                ),
              ),
            ),
            const SizedBox(height: 8),
            Text(
              a.title,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(
                color: PaColors.inkPrimary,
                fontSize: 14,
                fontWeight: FontWeight.w700,
                height: 1.3,
              ),
            ),
            const SizedBox(height: 6),
            Expanded(
              child: Text(
                a.excerpt,
                maxLines: 3,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(
                  color: PaColors.inkSecondary,
                  fontSize: 11.5,
                  height: 1.4,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _openArticle(String url) async {
    if (url.isEmpty) return;
    final uri = Uri.tryParse(url);
    if (uri == null) return;
    await launchUrl(uri, mode: LaunchMode.externalApplication);
  }
}
