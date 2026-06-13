import 'package:dio/dio.dart';

import '../../../../core/network/api_client.dart';
import '../../../../core/network/api_config.dart';
import '../../../../core/network/api_exceptions.dart';
import '../../domain/entities/feed_item.dart';

/// LOT 11 + CMS — Sources distantes pour le flux Home (campagnes + actualités).
///
/// - Campagnes : `GET /api/v1/loans/campaigns/active/` retourne les campagnes
///   actuellement ouvertes avec leur flyer (URL absolue).
/// - Actualités : `GET /api/v2/pages/?type=cms.BlogPostPage` (Wagtail API v2)
///   pour la liste des derniers articles. L'API Wagtail vit hors `/api/v1/`,
///   on utilise donc une URL absolue construite sur `ApiConfig.baseUrl`.
class FeedDioDataSource {
  FeedDioDataSource(this._client);

  final ApiClient _client;
  Dio get _dio => _client.dio;

  Future<List<CampaignFlyer>> activeCampaigns() async {
    try {
      final res = await _dio.get<Map<String, dynamic>>(
        '/loans/campaigns/active/',
      );
      final results = (res.data?['results'] as List?) ?? const [];
      return results
          .whereType<Map<String, dynamic>>()
          .map(_parseCampaign)
          .toList(growable: false);
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }

  Future<List<NewsArticle>> latestArticles({int limit = 5}) async {
    try {
      final url = '${ApiConfig.baseUrl}/api/v2/pages/';
      final res = await _dio.get<Map<String, dynamic>>(
        url,
        queryParameters: {
          'type': 'cms.BlogPostPage',
          // hero_image n'est pas un champ filtrable Wagtail v2 dans la
          // vue listing (400 "unknown fields"). On le récupère plus tard
          // depuis le détail si besoin ; le carousel actuel fonctionne
          // sans visuel.
          'fields': 'excerpt,first_published_at',
          'limit': limit,
          'order': '-first_published_at',
        },
      );
      final items = (res.data?['items'] as List?) ?? const [];
      return items
          .whereType<Map<String, dynamic>>()
          .map(_parseArticle)
          .toList(growable: false);
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }

  // ── Parsing ────────────────────────────────────────────────────────────

  CampaignFlyer _parseCampaign(Map<String, dynamic> json) {
    return CampaignFlyer(
      id: (json['id'] as num?)?.toInt() ?? 0,
      nom: (json['nom'] as String?) ?? '',
      profilCible: (json['profil_cible'] as String?) ?? '',
      montantMax: num.tryParse('${json['montant_max']}') ?? 0,
      tauxInteret: num.tryParse('${json['taux_interet']}') ?? 0,
      dateFin: DateTime.tryParse((json['date_fin'] as String?) ?? '') ??
          DateTime.now(),
      flyerUrl: (json['flyer_url'] as String?)?.isNotEmpty == true
          ? json['flyer_url'] as String
          : null,
    );
  }

  NewsArticle _parseArticle(Map<String, dynamic> json) {
    final meta = (json['meta'] as Map<String, dynamic>?) ?? const {};
    // Wagtail expose les images via un endpoint /api/v2/images/<id>/. Pour
    // simplifier la première version, on ne tente pas une 2e requête : on
    // reprend `hero_image` brut s'il pointe déjà sur une URL, sinon on
    // laisse l'UI fallback sur un dégradé.
    final heroRaw = json['hero_image'];
    String? heroUrl;
    if (heroRaw is Map<String, dynamic>) {
      final detailUrl = (heroRaw['meta'] as Map?)?['detail_url'] as String?;
      heroUrl = detailUrl;
    } else if (heroRaw is String) {
      heroUrl = heroRaw;
    }
    return NewsArticle(
      id: (json['id'] as num?)?.toInt() ?? 0,
      title: (json['title'] as String?) ?? '',
      excerpt: (json['excerpt'] as String?) ?? '',
      publishedAt: DateTime.tryParse(
            (meta['first_published_at'] as String?) ?? '',
          ) ??
          DateTime.now(),
      htmlUrl: (meta['html_url'] as String?) ?? '',
      heroImageUrl: heroUrl,
    );
  }
}
