import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/di/providers.dart';
import '../../../../core/utils/pollable_notifier.dart';
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
    this.campaignsError = false,
    required this.articles,
    required this.articlesHasNext,
    required this.articlesLoading,
    this.articlesError = false,
  });

  final List<CampaignFlyer> campaigns;
  final bool campaignsHasNext;
  final bool campaignsLoading;

  /// Le dernier fetch des campagnes a échoué (réseau). Permet à l'UI de
  /// distinguer « aucune campagne » d'un « chargement impossible » et
  /// d'offrir un retry au lieu d'un empty state trompeur.
  final bool campaignsError;

  final List<NewsArticle> articles;
  final bool articlesHasNext;
  final bool articlesLoading;
  final bool articlesError;

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
    bool? campaignsError,
    List<NewsArticle>? articles,
    bool? articlesHasNext,
    bool? articlesLoading,
    bool? articlesError,
  }) {
    return FeedState(
      campaigns: campaigns ?? this.campaigns,
      campaignsHasNext: campaignsHasNext ?? this.campaignsHasNext,
      campaignsLoading: campaignsLoading ?? this.campaignsLoading,
      campaignsError: campaignsError ?? this.campaignsError,
      articles: articles ?? this.articles,
      articlesHasNext: articlesHasNext ?? this.articlesHasNext,
      articlesLoading: articlesLoading ?? this.articlesLoading,
      articlesError: articlesError ?? this.articlesError,
    );
  }
}

class HomeFeedNotifier extends AutoDisposeAsyncNotifier<FeedState>
    with PollableAutoDisposeAsyncNotifier<FeedState> {
  @override
  Future<FeedState> build() async {
    // Garde la donnée même si plus aucun widget watch . la Home dispose
    // souvent du Notifier en navigation latérale et le re-fetcherait
    // inutilement.
    ref.keepAlive();
    final initial = await _loadInitial();
    seedPollHash(initial);
    return initial;
  }

  Future<FeedState> _loadInitial() async {
    final ds = ref.read(feedDataSourceProvider);
    // Chargements parallèles avec catchError indépendant : si l'une
    // plante, l'autre s'affiche quand même. On mémorise l'échec par flux pour
    // que l'UI affiche un retry plutôt qu'un empty state trompeur.
    var campErr = false;
    var newsErr = false;
    final campF =
        ds.activeCampaigns(limit: _kPageSize, offset: 0).catchError((_) {
      campErr = true;
      return const FeedPage<CampaignFlyer>(
        items: [],
        total: 0,
        hasNext: false,
        nextOffset: 0,
      );
    });
    final newsF = ds.latestArticles(limit: _kPageSize, offset: 0).catchError((_) {
      newsErr = true;
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
      campaignsError: campErr,
      articles: news.items,
      articlesHasNext: news.hasNext,
      articlesLoading: false,
      articlesError: newsErr,
    );
  }

  Future<void> refresh() => silentRefresh(_loadInitial);

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
