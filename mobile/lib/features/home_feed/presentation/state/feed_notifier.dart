import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/di/providers.dart';
import '../../data/datasources/feed_dio_datasource.dart';
import '../../domain/entities/feed_item.dart';

final feedDataSourceProvider = Provider<FeedDioDataSource>((ref) {
  return FeedDioDataSource(ref.watch(apiClientProvider));
});

const int _kPageSize = 10;

/// État partagé pour les 2 carousels : items chargés cumulés + flags
/// de pagination. Le widget peut demander `loadMore(kind)` lorsqu'il
/// arrive en bout de scroll.
class FeedState {
  const FeedState({
    required this.campaigns,
    required this.campaignsHasNext,
    required this.campaignsLoading,
    required this.articles,
    required this.articlesHasNext,
    required this.articlesLoading,
  });

  final List<CampaignFlyer> campaigns;
  final bool campaignsHasNext;
  final bool campaignsLoading;
  final List<NewsArticle> articles;
  final bool articlesHasNext;
  final bool articlesLoading;

  static const empty = FeedState(
    campaigns: [],
    campaignsHasNext: false,
    campaignsLoading: false,
    articles: [],
    articlesHasNext: false,
    articlesLoading: false,
  );

  FeedState copyWith({
    List<CampaignFlyer>? campaigns,
    bool? campaignsHasNext,
    bool? campaignsLoading,
    List<NewsArticle>? articles,
    bool? articlesHasNext,
    bool? articlesLoading,
  }) {
    return FeedState(
      campaigns: campaigns ?? this.campaigns,
      campaignsHasNext: campaignsHasNext ?? this.campaignsHasNext,
      campaignsLoading: campaignsLoading ?? this.campaignsLoading,
      articles: articles ?? this.articles,
      articlesHasNext: articlesHasNext ?? this.articlesHasNext,
      articlesLoading: articlesLoading ?? this.articlesLoading,
    );
  }
}

class HomeFeedNotifier extends AutoDisposeAsyncNotifier<FeedState> {
  @override
  Future<FeedState> build() async {
    // Garde la donnée même si plus aucun widget watch . la Home dispose
    // souvent du Notifier en navigation latérale et le re-fetcherait
    // inutilement.
    ref.keepAlive();
    return _loadInitial();
  }

  Future<FeedState> _loadInitial() async {
    final ds = ref.read(feedDataSourceProvider);
    // Chargements parallèles avec catchError indépendant : si l'une
    // plante, l'autre s'affiche quand même.
    final campF =
        ds.activeCampaigns(limit: _kPageSize, offset: 0).catchError((_) {
      return const FeedPage<CampaignFlyer>(
        items: [],
        total: 0,
        hasNext: false,
        nextOffset: 0,
      );
    });
    final newsF = ds.latestArticles(limit: _kPageSize, offset: 0).catchError((_) {
      return const FeedPage<NewsArticle>(
        items: [],
        total: 0,
        hasNext: false,
        nextOffset: 0,
      );
    });
    final results = await Future.wait([campF, newsF]);
    final camp = results[0] as FeedPage<CampaignFlyer>;
    final news = results[1] as FeedPage<NewsArticle>;
    return FeedState(
      campaigns: camp.items,
      campaignsHasNext: camp.hasNext,
      campaignsLoading: false,
      articles: news.items,
      articlesHasNext: news.hasNext,
      articlesLoading: false,
    );
  }

  Future<void> refresh() async {
    state = const AsyncLoading();
    state = await AsyncValue.guard(_loadInitial);
  }

  /// Charge la page suivante de campagnes en cumul. Idempotent : ne fait
  /// rien si `campaignsLoading` ou `!campaignsHasNext`.
  Future<void> loadMoreCampaigns() async {
    final current = state.valueOrNull;
    if (current == null) return;
    if (current.campaignsLoading || !current.campaignsHasNext) return;
    state = AsyncData(current.copyWith(campaignsLoading: true));
    try {
      final page = await ref.read(feedDataSourceProvider).activeCampaigns(
            limit: _kPageSize,
            offset: current.campaigns.length,
          );
      state = AsyncData(
        current.copyWith(
          campaigns: [...current.campaigns, ...page.items],
          campaignsHasNext: page.hasNext,
          campaignsLoading: false,
        ),
      );
    } catch (_) {
      state = AsyncData(current.copyWith(campaignsLoading: false));
    }
  }

  /// Charge la page suivante d'articles en cumul.
  Future<void> loadMoreArticles() async {
    final current = state.valueOrNull;
    if (current == null) return;
    if (current.articlesLoading || !current.articlesHasNext) return;
    state = AsyncData(current.copyWith(articlesLoading: true));
    try {
      final page = await ref.read(feedDataSourceProvider).latestArticles(
            limit: _kPageSize,
            offset: current.articles.length,
          );
      state = AsyncData(
        current.copyWith(
          articles: [...current.articles, ...page.items],
          articlesHasNext: page.hasNext,
          articlesLoading: false,
        ),
      );
    } catch (_) {
      state = AsyncData(current.copyWith(articlesLoading: false));
    }
  }
}

final homeFeedProvider =
    AsyncNotifierProvider.autoDispose<HomeFeedNotifier, FeedState>(
  HomeFeedNotifier.new,
);
