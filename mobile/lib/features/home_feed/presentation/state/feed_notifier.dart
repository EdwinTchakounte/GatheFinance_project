import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/di/providers.dart';
import '../../data/datasources/feed_dio_datasource.dart';
import '../../domain/entities/feed_item.dart';

/// Notifier maintenant les 2 listes en RAM. `autoDispose` avec `.keepAlive()`
/// suit la stratégie cache : on garde les données entre navigations rapides,
/// mais on libère si l'utilisateur sort longtemps. Le pull-to-refresh de la
/// Home force un re-fetch frais via `refresh()`.
final feedDataSourceProvider = Provider<FeedDioDataSource>((ref) {
  return FeedDioDataSource(ref.watch(apiClientProvider));
});

class _FeedState {
  const _FeedState({
    required this.campaigns,
    required this.articles,
  });

  final List<CampaignFlyer> campaigns;
  final List<NewsArticle> articles;

  bool get isEmpty => campaigns.isEmpty && articles.isEmpty;
}

class HomeFeedNotifier extends AutoDisposeAsyncNotifier<_FeedState> {
  @override
  Future<_FeedState> build() async {
    // Garde la donnée même si plus aucun widget watch — la Home dispose
    // du Notifier en navigation latérale et le re-fetcherait inutilement.
    ref.keepAlive();
    return _load();
  }

  Future<_FeedState> _load() async {
    final ds = ref.read(feedDataSourceProvider);
    // On charge les 2 listes indépendamment : si l'une plante (ex.
    // erreur Wagtail), on affiche quand même l'autre côté UI plutôt
    // que de masquer toute la home feed.
    final campaignsF = ds.activeCampaigns().catchError((_) => <CampaignFlyer>[]);
    final articlesF = ds.latestArticles().catchError((_) => <NewsArticle>[]);
    final results = await Future.wait([campaignsF, articlesF]);
    return _FeedState(
      campaigns: results[0] as List<CampaignFlyer>,
      articles: results[1] as List<NewsArticle>,
    );
  }

  Future<void> refresh() async {
    state = const AsyncLoading();
    state = await AsyncValue.guard(_load);
  }
}

final homeFeedProvider =
    AsyncNotifierProvider.autoDispose<HomeFeedNotifier, _FeedState>(
  HomeFeedNotifier.new,
);

/// Exposés séparément pour que la Home puisse afficher l'un ou l'autre
/// pendant que le second charge encore.
final activeCampaignsProvider = Provider.autoDispose<List<CampaignFlyer>>((ref) {
  return ref.watch(homeFeedProvider).valueOrNull?.campaigns ?? const [];
});

final latestArticlesProvider = Provider.autoDispose<List<NewsArticle>>((ref) {
  return ref.watch(homeFeedProvider).valueOrNull?.articles ?? const [];
});
