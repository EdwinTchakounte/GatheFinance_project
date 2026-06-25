import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../app/theme/paysika/pa_colors.dart';
import '../../../../core/widgets/paysika/pa_card.dart';
import '../../../../core/widgets/paysika/pa_shimmer.dart';
import '../../domain/entities/feed_item.dart';
import '../state/feed_notifier.dart';

/// Section "Campagnes en cours" . carousel horizontal des flyers actifs.
///
/// Sur la Home on n'affiche que les 2 plus récentes (date_fin ASC côté
/// backend). Le bouton "Voir plus" route vers la page in-app `/campaigns`
/// qui montre la liste complète paginée . c'est elle qui charge la page
/// suivante au scroll, pas la Home.
class CampaignsSection extends ConsumerWidget {
  const CampaignsSection({
    super.key,
    required this.onSeeMore,
    this.onTapCampaign,
  });
  final VoidCallback onSeeMore;
  final void Function(CampaignFlyer c)? onTapCampaign;

  /// Limite imposée par le brief client : les 5 plus récentes sur Home.
  static const int kHomeLimit = 5;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final feedAsync = ref.watch(homeFeedProvider);
    final feed = feedAsync.valueOrNull;
    final all = feed?.campaigns ?? const <CampaignFlyer>[];
    // Loading : on montre des skeletons soft plutôt qu'un blanc complet.
    final isLoading = feedAsync.isLoading && feed == null;
    if (!isLoading && all.isEmpty) return const SizedBox.shrink();
    final campaigns = all.take(kHomeLimit).toList();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _SectionHeader(
          title: 'Campagnes en cours',
          onSeeMore: onSeeMore,
          loading: isLoading,
        ),
        SizedBox(
          height: 256,
          child: ListView.separated(
            scrollDirection: Axis.horizontal,
            padding: const EdgeInsets.symmetric(horizontal: 16),
            physics: const BouncingScrollPhysics(),
            itemCount: isLoading ? 2 : campaigns.length,
            separatorBuilder: (_, __) => const SizedBox(width: 14),
            itemBuilder: (_, i) => isLoading
                ? const _SkeletonCard(width: 272, withChip: true)
                : _CampaignCard(c: campaigns[i], onTap: onTapCampaign),
          ),
        ),
        const SizedBox(height: 6),
      ],
    );
  }
}

/// Section "Actualités" . articles avec image de couverture.
///
/// Sur la Home on n'affiche que les 3 plus récentes . la page in-app `/news`
/// se charge de la pagination complète.
class NewsSection extends ConsumerWidget {
  const NewsSection({
    super.key,
    required this.onSeeMore,
    this.onTapArticle,
  });
  final VoidCallback onSeeMore;
  final void Function(NewsArticle a)? onTapArticle;

  /// Limite imposée par le brief client : les 5 plus récentes sur Home.
  static const int kHomeLimit = 5;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final feedAsync = ref.watch(homeFeedProvider);
    final feed = feedAsync.valueOrNull;
    final all = feed?.articles ?? const <NewsArticle>[];
    final isLoading = feedAsync.isLoading && feed == null;
    if (!isLoading && all.isEmpty) return const SizedBox.shrink();
    final articles = all.take(kHomeLimit).toList();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _SectionHeader(
          title: 'Actualités',
          onSeeMore: onSeeMore,
          loading: isLoading,
        ),
        SizedBox(
          height: 278,
          child: ListView.separated(
            scrollDirection: Axis.horizontal,
            padding: const EdgeInsets.symmetric(horizontal: 16),
            physics: const BouncingScrollPhysics(),
            itemCount: isLoading ? 2 : articles.length,
            separatorBuilder: (_, __) => const SizedBox(width: 14),
            itemBuilder: (_, i) => isLoading
                ? const _SkeletonCard(width: 268, withChip: true)
                : _ArticleCard(a: articles[i], onTap: onTapArticle),
          ),
        ),
        const SizedBox(height: 6),
      ],
    );
  }
}

class _SectionHeader extends StatelessWidget {
  const _SectionHeader({
    required this.title,
    required this.onSeeMore,
    this.loading = false,
  });
  final String title;
  final VoidCallback onSeeMore;
  final bool loading;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 14, 16, 10),
      child: Row(
        children: [
          Expanded(
            child: Text(
              title,
              style: const TextStyle(
                color: PaColors.inkPrimary,
                fontSize: 16,
                fontWeight: FontWeight.w700,
                letterSpacing: -0.2,
              ),
            ),
          ),
          if (loading)
            const _DotsLoading()
          else
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
                      fontSize: 13,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                  SizedBox(width: 2),
                  Icon(Icons.chevron_right_rounded,
                      color: PaColors.teal, size: 17,),
                ],
              ),
            ),
        ],
      ),
    );
  }
}


/// 3 petits dots animés pour signaler "chargement en cours" dans un header,
/// plus discret qu'un CircularProgressIndicator.
class _DotsLoading extends StatefulWidget {
  const _DotsLoading();
  @override
  State<_DotsLoading> createState() => _DotsLoadingState();
}

class _DotsLoadingState extends State<_DotsLoading>
    with SingleTickerProviderStateMixin {
  late final AnimationController _ctrl;
  @override
  void initState() {
    super.initState();
    _ctrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1200),
    )..repeat();
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _ctrl,
      builder: (_, __) {
        final t = _ctrl.value;
        return Row(
          mainAxisSize: MainAxisSize.min,
          children: List.generate(3, (i) {
            final phase = (t + i * 0.18) % 1.0;
            final opacity = (0.25 + 0.75 * (1 - (phase - 0.5).abs() * 2))
                .clamp(0.25, 1.0);
            return Padding(
              padding: const EdgeInsets.symmetric(horizontal: 1.5),
              child: Container(
                width: 5,
                height: 5,
                decoration: BoxDecoration(
                  color: PaColors.teal.withValues(alpha: opacity),
                  shape: BoxShape.circle,
                ),
              ),
            );
          }),
        );
      },
    );
  }
}


/// Skeleton card uniforme pour les sections en chargement (campagnes + actus).
/// Image placeholder shimmer + 2-3 lignes de texte shimmer + chip optionnel.
class _SkeletonCard extends StatelessWidget {
  const _SkeletonCard({required this.width, this.withChip = false});

  final double width;
  final bool withChip;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: width,
      child: PaCard(
        padding: EdgeInsets.zero,
        child: PaShimmer(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Image placeholder
              AspectRatio(
                aspectRatio: 16 / 9,
                child: Container(
                  decoration: const BoxDecoration(
                    color: PaColors.line,
                    borderRadius: BorderRadius.vertical(
                      top: Radius.circular(10),
                    ),
                  ),
                ),
              ),
              Padding(
                padding: const EdgeInsets.fromLTRB(14, 14, 14, 16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    if (withChip) ...[
                      const PaShimmerBox(width: 60, height: 14, borderRadius: 4),
                      const SizedBox(height: 10),
                    ],
                    const PaShimmerBox(width: 200, height: 13, borderRadius: 4),
                    const SizedBox(height: 8),
                    const PaShimmerBox(width: 140, height: 11, borderRadius: 4),
                    const SizedBox(height: 6),
                    const PaShimmerBox(width: 90, height: 11, borderRadius: 4),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _CampaignCard extends StatelessWidget {
  const _CampaignCard({required this.c, this.onTap});
  final CampaignFlyer c;
  final void Function(CampaignFlyer c)? onTap;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: 272,
      child: PaCard(
        padding: EdgeInsets.zero,
        onTap: onTap == null ? null : () => onTap!(c),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Stack(
              children: [
                ClipRRect(
                  borderRadius: const BorderRadius.vertical(
                    top: Radius.circular(10),
                  ),
                  child: AspectRatio(
                    aspectRatio: 16 / 9,
                    child: CachedNetworkImage(
                            imageUrl: c.flyerUrl ?? '',
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
                        horizontal: 9, vertical: 5,),
                    decoration: BoxDecoration(
                      color: Colors.white.withValues(alpha: 0.92),
                      borderRadius: BorderRadius.circular(8),
                      boxShadow: [
                        BoxShadow(
                          color: Colors.black.withValues(alpha: 0.08),
                          blurRadius: 6,
                          offset: const Offset(0, 2),
                        ),
                      ],
                    ),
                    child: Text(
                      c.profilCible.toUpperCase(),
                      style: const TextStyle(
                        color: PaColors.teal,
                        fontSize: 10,
                        fontWeight: FontWeight.w800,
                        letterSpacing: 1.4,
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
                          size: 14, color: PaColors.teal,),
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
                          size: 13, color: PaColors.inkMuted,),
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
                color: PaColors.teal, size: 36,),
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
  const _ArticleCard({required this.a, this.onTap});
  final NewsArticle a;
  final void Function(NewsArticle a)? onTap;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: 268,
      child: PaCard(
        padding: EdgeInsets.zero,
        onTap: onTap == null ? null : () => onTap!(a),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            ClipRRect(
              borderRadius: const BorderRadius.vertical(
                top: Radius.circular(10),
              ),
              child: AspectRatio(
                aspectRatio: 16 / 9,
                child: CachedNetworkImage(
                        imageUrl: a.heroImageUrl ?? '',
                        fit: BoxFit.cover,
                        fadeInDuration: const Duration(milliseconds: 200),
                        placeholder: (_, __) => _PlaceholderArticle(title: a.title),
                        errorWidget: (_, __, ___) =>
                            _PlaceholderArticle(title: a.title),
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
                        horizontal: 9, vertical: 4,),
                    decoration: BoxDecoration(
                      color: PaColors.blue.withValues(alpha: 0.10),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: const Text(
                      'ACTUALITÉ',
                      style: TextStyle(
                        color: PaColors.blue,
                        fontSize: 10,
                        fontWeight: FontWeight.w800,
                        letterSpacing: 1.4,
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

}

/// Placeholder card actualité . gradient déterministe par titre + icône
/// catégorie + filigrane brand. Donne une présence visuelle au lieu d'un
/// rectangle terne quand l'article n'a pas de hero image.
class _PlaceholderArticle extends StatelessWidget {
  const _PlaceholderArticle({this.title = ''});
  final String title;

  static const _palettes = <List<Color>>[
    [Color(0xFF1E3A8A), Color(0xFF0EA5E9)],
    [Color(0xFF065F46), Color(0xFF10B981)],
    [Color(0xFF7C3AED), Color(0xFFEC4899)],
    [Color(0xFFB45309), Color(0xFFF59E0B)],
    [Color(0xFF0F766E), Color(0xFF14B8A6)],
    [Color(0xFF1E40AF), Color(0xFF8B5CF6)],
  ];

  static const _icons = <IconData>[
    Icons.trending_up_rounded,
    Icons.savings_outlined,
    Icons.school_outlined,
    Icons.handshake_outlined,
    Icons.lightbulb_outline_rounded,
    Icons.local_florist_outlined,
  ];

  int get _slot {
    var h = 0;
    for (final c in title.runes) {
      h = (h * 31 + c) & 0x7fffffff;
    }
    return h % _palettes.length;
  }

  @override
  Widget build(BuildContext context) {
    final palette = _palettes[_slot];
    final icon = _icons[_slot];
    return Stack(
      fit: StackFit.expand,
      children: [
        Container(
          decoration: BoxDecoration(
            gradient: LinearGradient(
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
              colors: palette,
            ),
          ),
        ),
        Positioned(
          top: -40,
          right: -30,
          child: IgnorePointer(
            child: Container(
              width: 130,
              height: 130,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                gradient: RadialGradient(
                  colors: [
                    Colors.white.withValues(alpha: 0.22),
                    Colors.white.withValues(alpha: 0),
                  ],
                ),
              ),
            ),
          ),
        ),
        Center(
          child: Container(
            width: 54,
            height: 54,
            decoration: BoxDecoration(
              color: Colors.white.withValues(alpha: 0.16),
              shape: BoxShape.circle,
              border: Border.all(
                color: Colors.white.withValues(alpha: 0.3),
                width: 1.2,
              ),
            ),
            alignment: Alignment.center,
            child: Icon(icon, color: Colors.white, size: 22),
          ),
        ),
        const Positioned(
          bottom: 8,
          right: 10,
          child: IgnorePointer(
            child: Opacity(
              opacity: 0.32,
              child: Text(
                'GATHÉ',
                style: TextStyle(
                  color: Colors.white,
                  fontSize: 8.5,
                  fontWeight: FontWeight.w800,
                  letterSpacing: 1.8,
                ),
              ),
            ),
          ),
        ),
      ],
    );
  }
}
