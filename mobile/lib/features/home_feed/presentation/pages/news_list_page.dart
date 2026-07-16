import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';

import '../../../../app/theme/paysika/pa_colors.dart';
import '../../../../core/widgets/paysika/pa_card.dart';
import '../../../../core/widgets/paysika/pa_empty_state.dart';
import '../../../../core/widgets/paysika/pa_error_state.dart';
import '../../../../core/widgets/paysika/pa_pattern_background.dart';
import '../../domain/entities/feed_item.dart';
import '../state/feed_notifier.dart';

/// Liste in-app de toutes les actualités. Atteinte depuis le "Voir plus"
/// du carousel Home. Tap sur une carte → page de détail in-app.
///
/// Le contenu (RefreshIndicator + liste) est extrait dans [NewsListBody] pour
/// pouvoir être réutilisé tel quel dans un onglet de la page « Annonces ».
class NewsListPage extends StatelessWidget {
  const NewsListPage({super.key});

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
          'Actualités',
          style: TextStyle(
            color: PaColors.inkPrimary,
            fontSize: 17,
            fontWeight: FontWeight.w700,
          ),
        ),
      ),
      body: const PaPatternBackground(child: NewsListBody()),
    );
  }
}

/// Corps réutilisable de la liste d'actualités (sans Scaffold/AppBar).
class NewsListBody extends ConsumerStatefulWidget {
  const NewsListBody({super.key});

  @override
  ConsumerState<NewsListBody> createState() => _NewsListBodyState();
}

class _NewsListBodyState extends ConsumerState<NewsListBody> {
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
    final hasError = feed?.articlesError ?? false;

    return RefreshIndicator.adaptive(
      color: PaColors.teal,
      onRefresh: () => ref.read(homeFeedProvider.notifier).refresh(),
      child: articles.isEmpty && !loading
          ? (hasError
              ? PaErrorState(
                  message: 'Impossible de charger les actualités.',
                  onRetry: () => ref.read(homeFeedProvider.notifier).refresh(),
                )
              : const _Empty())
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
          // ── Visuel : image + dégradé + pastille date ───────────────────
          ClipRRect(
            borderRadius: const BorderRadius.vertical(top: Radius.circular(20)),
            child: AspectRatio(
              aspectRatio: 16 / 9,
              child: Stack(
                fit: StackFit.expand,
                children: [
                  a.heroImageUrl == null
                      ? const _Placeholder()
                      : CachedNetworkImage(
                          imageUrl: a.heroImageUrl!,
                          fit: BoxFit.cover,
                          memCacheWidth: 720,
                          placeholder: (_, __) => const _Placeholder(),
                          errorWidget: (_, __, ___) => const _Placeholder(),
                        ),
                  const Positioned(
                    left: 0,
                    right: 0,
                    bottom: 0,
                    child: _Scrim(),
                  ),
                  Positioned(
                    top: 12,
                    left: 12,
                    child: _Pill(
                      text: dt.format(a.publishedAt).toUpperCase(),
                      bg: Colors.white.withValues(alpha: 0.92),
                      fg: PaColors.warning,
                      icon: Icons.event_note_rounded,
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
                  a.title,
                  style: const TextStyle(
                    color: PaColors.inkPrimary,
                    fontSize: 16.5,
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
                const SizedBox(height: 12),
                const Row(
                  children: [
                    Text(
                      'Lire l\'article',
                      style: TextStyle(
                        color: PaColors.warning,
                        fontSize: 13,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    SizedBox(width: 3),
                    Icon(Icons.arrow_forward_rounded,
                        size: 17, color: PaColors.warning,),
                  ],
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
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

/// Pastille flottante posée sur l'image d'une carte.
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
        SizedBox(height: 70),
        PaEmptyState(
          icon: Icons.article_outlined,
          tint: PaColors.warning,
          title: 'Aucune actualité pour le moment',
          message: 'Reviens plus tard, ou tire vers le bas pour rafraîchir.',
        ),
      ],
    );
  }
}
