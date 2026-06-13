import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../../../app/theme/paysika/pa_colors.dart';
import '../../../../core/widgets/paysika/pa_card.dart';
import '../../domain/entities/feed_item.dart';
import '../state/feed_notifier.dart';

/// Section "Campagnes en cours" — carousel horizontal des flyers actifs,
/// avec lazy-load au scroll (charge la page suivante à 200px de la fin).
class CampaignsSection extends ConsumerStatefulWidget {
  const CampaignsSection({super.key, required this.onSeeMore});
  final VoidCallback onSeeMore;

  @override
  ConsumerState<CampaignsSection> createState() => _CampaignsSectionState();
}

class _CampaignsSectionState extends ConsumerState<CampaignsSection> {
  final ScrollController _ctrl = ScrollController();

  @override
  void initState() {
    super.initState();
    _ctrl.addListener(_onScroll);
  }

  @override
  void dispose() {
    _ctrl.removeListener(_onScroll);
    _ctrl.dispose();
    super.dispose();
  }

  void _onScroll() {
    if (_ctrl.position.pixels >
        _ctrl.position.maxScrollExtent - 200) {
      ref.read(homeFeedProvider.notifier).loadMoreCampaigns();
    }
  }

  @override
  Widget build(BuildContext context) {
    final feed = ref.watch(homeFeedProvider).valueOrNull;
    final campaigns = feed?.campaigns ?? const <CampaignFlyer>[];
    if (campaigns.isEmpty) return const SizedBox.shrink();
    final showSpinner = feed?.campaignsLoading ?? false;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _SectionHeader(
          title: 'Campagnes en cours',
          onSeeMore: widget.onSeeMore,
        ),
        SizedBox(
          height: 226,
          child: ListView.separated(
            controller: _ctrl,
            scrollDirection: Axis.horizontal,
            padding: const EdgeInsets.symmetric(horizontal: 16),
            physics: const BouncingScrollPhysics(),
            itemCount: campaigns.length + (showSpinner ? 1 : 0),
            separatorBuilder: (_, __) => const SizedBox(width: 14),
            itemBuilder: (_, i) {
              if (i >= campaigns.length) {
                return const Center(
                  child: Padding(
                    padding: EdgeInsets.symmetric(horizontal: 24),
                    child: SizedBox(
                      width: 24,
                      height: 24,
                      child: CircularProgressIndicator(
                        strokeWidth: 2.5,
                        color: PaColors.teal,
                      ),
                    ),
                  ),
                );
              }
              return _CampaignCard(c: campaigns[i]);
            },
          ),
        ),
        const SizedBox(height: 8),
      ],
    );
  }
}

/// Section "Actualités" — articles avec image de couverture.
class NewsSection extends ConsumerStatefulWidget {
  const NewsSection({super.key, required this.onSeeMore});
  final VoidCallback onSeeMore;

  @override
  ConsumerState<NewsSection> createState() => _NewsSectionState();
}

class _NewsSectionState extends ConsumerState<NewsSection> {
  final ScrollController _ctrl = ScrollController();

  @override
  void initState() {
    super.initState();
    _ctrl.addListener(_onScroll);
  }

  @override
  void dispose() {
    _ctrl.removeListener(_onScroll);
    _ctrl.dispose();
    super.dispose();
  }

  void _onScroll() {
    if (_ctrl.position.pixels >
        _ctrl.position.maxScrollExtent - 200) {
      ref.read(homeFeedProvider.notifier).loadMoreArticles();
    }
  }

  @override
  Widget build(BuildContext context) {
    final feed = ref.watch(homeFeedProvider).valueOrNull;
    final articles = feed?.articles ?? const <NewsArticle>[];
    if (articles.isEmpty) return const SizedBox.shrink();
    final showSpinner = feed?.articlesLoading ?? false;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _SectionHeader(title: 'Actualités', onSeeMore: widget.onSeeMore),
        SizedBox(
          height: 250,
          child: ListView.separated(
            controller: _ctrl,
            scrollDirection: Axis.horizontal,
            padding: const EdgeInsets.symmetric(horizontal: 16),
            physics: const BouncingScrollPhysics(),
            itemCount: articles.length + (showSpinner ? 1 : 0),
            separatorBuilder: (_, __) => const SizedBox(width: 14),
            itemBuilder: (_, i) {
              if (i >= articles.length) {
                return const Center(
                  child: Padding(
                    padding: EdgeInsets.symmetric(horizontal: 24),
                    child: SizedBox(
                      width: 24,
                      height: 24,
                      child: CircularProgressIndicator(
                        strokeWidth: 2.5,
                        color: PaColors.teal,
                      ),
                    ),
                  ),
                );
              }
              return _ArticleCard(a: articles[i]);
            },
          ),
        ),
        const SizedBox(height: 8),
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
      padding: const EdgeInsets.fromLTRB(20, 16, 16, 10),
      child: Row(
        children: [
          Expanded(
            child: Text(
              title,
              style: const TextStyle(
                color: PaColors.inkPrimary,
                fontSize: 17,
                fontWeight: FontWeight.w700,
                letterSpacing: -0.2,
              ),
            ),
          ),
          TextButton(
            onPressed: onSeeMore,
            style: TextButton.styleFrom(
              padding: const EdgeInsets.symmetric(horizontal: 6),
              minimumSize: const Size(0, 0),
              tapTargetSize: MaterialTapTargetSize.shrinkWrap,
            ),
            child: const Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  'Voir plus',
                  style: TextStyle(
                    color: PaColors.teal,
                    fontSize: 13.5,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                SizedBox(width: 2),
                Icon(Icons.chevron_right_rounded,
                    color: PaColors.teal, size: 18),
              ],
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
      width: 272,
      child: PaCard(
        padding: EdgeInsets.zero,
        onTap: () => _openVitrineCampaigns(),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Stack(
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
                            fadeInDuration:
                                const Duration(milliseconds: 200),
                            placeholder: (_, __) =>
                                _PlaceholderFlyer(label: c.profilCible),
                            errorWidget: (_, __, ___) =>
                                _PlaceholderFlyer(label: c.profilCible),
                          ),
                  ),
                ),
                Positioned(
                  top: 10,
                  left: 10,
                  child: Container(
                    padding: const EdgeInsets.symmetric(
                        horizontal: 8, vertical: 4),
                    decoration: BoxDecoration(
                      color: Colors.black.withValues(alpha: 0.55),
                      borderRadius: BorderRadius.circular(999),
                    ),
                    child: Text(
                      c.profilCible.toUpperCase(),
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 10,
                        fontWeight: FontWeight.w800,
                        letterSpacing: 1.2,
                      ),
                    ),
                  ),
                ),
              ],
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(14, 12, 14, 14),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    c.nom,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                      color: PaColors.inkPrimary,
                      fontSize: 14,
                      fontWeight: FontWeight.w700,
                      height: 1.25,
                    ),
                  ),
                  const SizedBox(height: 6),
                  Row(
                    children: [
                      const Icon(Icons.payments_outlined,
                          size: 14, color: PaColors.teal),
                      const SizedBox(width: 4),
                      Expanded(
                        child: Text(
                          'Jusqu\'à ${_money(c.montantMax)} XAF',
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: const TextStyle(
                            color: PaColors.inkSecondary,
                            fontSize: 12,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 4),
                  Row(
                    children: [
                      const Icon(Icons.event_outlined,
                          size: 13, color: PaColors.inkMuted),
                      const SizedBox(width: 4),
                      Expanded(
                        child: Text(
                          'Clôture ${_d(c.dateFin)}',
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: const TextStyle(
                            color: PaColors.inkMuted,
                            fontSize: 11.5,
                          ),
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  static String _money(num value) {
    final str = value.toInt().toString();
    final buf = StringBuffer();
    for (int i = 0; i < str.length; i++) {
      if (i > 0 && (str.length - i) % 3 == 0) buf.write(' ');
      buf.write(str[i]);
    }
    return buf.toString();
  }

  static String _d(DateTime dt) =>
      '${dt.day.toString().padLeft(2, '0')}/${dt.month.toString().padLeft(2, '0')}';

  Future<void> _openVitrineCampaigns() async {
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
      decoration: const BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [
            PaColors.tealSurface,
            Color(0xFFD7EFE5),
          ],
        ),
      ),
      alignment: Alignment.center,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.campaign_outlined,
                color: PaColors.teal, size: 36),
            const SizedBox(height: 8),
            Text(
              label.toUpperCase(),
              textAlign: TextAlign.center,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(
                color: PaColors.teal,
                fontSize: 12,
                fontWeight: FontWeight.w800,
                letterSpacing: 1.2,
              ),
            ),
          ],
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
      width: 268,
      child: PaCard(
        padding: EdgeInsets.zero,
        onTap: () => _openArticle(a.htmlUrl),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            ClipRRect(
              borderRadius: const BorderRadius.vertical(
                top: Radius.circular(20),
              ),
              child: AspectRatio(
                aspectRatio: 16 / 9,
                child: a.heroImageUrl == null
                    ? const _PlaceholderArticle()
                    : CachedNetworkImage(
                        imageUrl: a.heroImageUrl!,
                        fit: BoxFit.cover,
                        fadeInDuration: const Duration(milliseconds: 200),
                        placeholder: (_, __) => const _PlaceholderArticle(),
                        errorWidget: (_, __, ___) =>
                            const _PlaceholderArticle(),
                      ),
              ),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(14, 12, 14, 14),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Container(
                    padding: const EdgeInsets.symmetric(
                        horizontal: 8, vertical: 3),
                    decoration: BoxDecoration(
                      color: PaColors.warningSurface,
                      borderRadius: BorderRadius.circular(999),
                    ),
                    child: const Text(
                      'ACTUALITÉ',
                      style: TextStyle(
                        color: PaColors.warning,
                        fontSize: 10,
                        fontWeight: FontWeight.w800,
                        letterSpacing: 1.2,
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
                  const SizedBox(height: 4),
                  Text(
                    a.excerpt,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                      color: PaColors.inkSecondary,
                      fontSize: 11.5,
                      height: 1.4,
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

  Future<void> _openArticle(String url) async {
    if (url.isEmpty) return;
    final uri = Uri.tryParse(url);
    if (uri == null) return;
    await launchUrl(uri, mode: LaunchMode.externalApplication);
  }
}

class _PlaceholderArticle extends StatelessWidget {
  const _PlaceholderArticle();

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: const BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [
            Color(0xFFFDF2E2),
            Color(0xFFFAE6CB),
          ],
        ),
      ),
      alignment: Alignment.center,
      child: const Icon(
        Icons.article_outlined,
        color: PaColors.warning,
        size: 40,
      ),
    );
  }
}
