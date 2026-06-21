import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';

import '../../../../app/theme/paysika/pa_colors.dart';
import '../../../../core/widgets/paysika/pa_card.dart';
import '../../../../core/widgets/paysika/pa_pattern_background.dart';
import '../../domain/entities/feed_item.dart';
import '../state/feed_notifier.dart';

/// Liste in-app de toutes les actualités. Atteinte depuis le "Voir plus"
/// du carousel Home. Tap sur une carte → page de détail in-app.
class NewsListPage extends ConsumerStatefulWidget {
  const NewsListPage({super.key});

  @override
  ConsumerState<NewsListPage> createState() => _NewsListPageState();
}

class _NewsListPageState extends ConsumerState<NewsListPage> {
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
      ref.read(homeFeedProvider.notifier).loadMoreArticles();
    }
  }

  @override
  Widget build(BuildContext context) {
    final feed = ref.watch(homeFeedProvider).valueOrNull;
    final articles = feed?.articles ?? const <NewsArticle>[];
    final loading = feed?.articlesLoading ?? false;

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
          'Actualités',
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
          child: articles.isEmpty && !loading
              ? const _Empty()
              : ListView.separated(
                  controller: _scroll,
                  physics: const AlwaysScrollableScrollPhysics(),
                  padding: const EdgeInsets.fromLTRB(16, 12, 16, 24),
                  itemCount: articles.length + (loading ? 1 : 0),
                  separatorBuilder: (_, __) => const SizedBox(height: 12),
                  itemBuilder: (_, i) {
                    if (i >= articles.length) {
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
                    return _ArticleRow(
                      a: articles[i],
                      onTap: () => context.push(
                        '/news/${articles[i].id}',
                        extra: articles[i],
                      ),
                    );
                  },
                ),
        ),
      ),
    );
  }
}

class _ArticleRow extends StatelessWidget {
  const _ArticleRow({required this.a, required this.onTap});
  final NewsArticle a;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final dt = DateFormat('dd MMM yyyy', 'fr_FR');
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
              child: a.heroImageUrl == null
                  ? const _Placeholder()
                  : CachedNetworkImage(
                      imageUrl: a.heroImageUrl!,
                      fit: BoxFit.cover,
                      placeholder: (_, __) => const _Placeholder(),
                      errorWidget: (_, __, ___) => const _Placeholder(),
                    ),
            ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 14, 16, 16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  dt.format(a.publishedAt).toUpperCase(),
                  style: const TextStyle(
                    color: PaColors.warning,
                    fontSize: 11,
                    fontWeight: FontWeight.w800,
                    letterSpacing: 1.2,
                  ),
                ),
                const SizedBox(height: 6),
                Text(
                  a.title,
                  style: const TextStyle(
                    color: PaColors.inkPrimary,
                    fontSize: 16,
                    fontWeight: FontWeight.w700,
                    height: 1.3,
                  ),
                ),
                if (a.excerpt.isNotEmpty) ...[
                  const SizedBox(height: 8),
                  Text(
                    a.excerpt,
                    maxLines: 3,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                      color: PaColors.inkSecondary,
                      fontSize: 13,
                      height: 1.45,
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

class _Placeholder extends StatelessWidget {
  const _Placeholder();

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: const BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [Color(0xFFFDF2E2), Color(0xFFFAE6CB)],
        ),
      ),
      alignment: Alignment.center,
      child: const Icon(
        Icons.article_outlined,
        color: PaColors.warning,
        size: 44,
      ),
    );
  }
}

class _Empty extends StatelessWidget {
  const _Empty();

  @override
  Widget build(BuildContext context) {
    return ListView(
      physics: const AlwaysScrollableScrollPhysics(),
      children: const [
        SizedBox(height: 80),
        Icon(Icons.article_outlined, color: PaColors.inkMuted, size: 56),
        SizedBox(height: 16),
        Center(
          child: Padding(
            padding: EdgeInsets.symmetric(horizontal: 40),
            child: Text(
              'Aucune actualité pour le moment.',
              textAlign: TextAlign.center,
              style: TextStyle(color: PaColors.inkMuted, fontSize: 13),
            ),
          ),
        ),
      ],
    );
  }
}
