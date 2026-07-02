import 'package:dio/dio.dart';

import '../../../../core/network/api_client.dart';
import '../../../../core/network/api_config.dart';
import '../../../../core/network/api_exceptions.dart';
import '../../domain/entities/feed_item.dart';

/// LOT 11 + CMS — Sources distantes pour le flux Home (campagnes + actualités).
///
/// - Campagnes : `GET /api/v1/loans/campaigns/active/?limit=&offset=` retourne
///   une page paginée des campagnes ouvertes (count/next/previous/results) avec
///   flyer URL absolue.
/// - Actualités : `GET /api/v2/pages/?type=cms.BlogPostPage&limit=&offset=`
///   (Wagtail API v2). On demande `cover_image_data` qui contient un dict
///   `{url, width, height, alt}` (rendition fill-1280x720). `meta.total_count`
///   donne le total pour la pagination ; on calcule `offset+limit < total`.
class FeedDioDataSource {
  FeedDioDataSource(this._client);

  final ApiClient _client;
  Dio get _dio => _client.dio;

  Future<FeedPage<CampaignFlyer>> activeCampaigns({
    int limit = 10,
    int offset = 0,
  }) async {
    try {
      final res = await _dio.get<Map<String, dynamic>>(
        '/loans/campaigns/active/',
        queryParameters: {'limit': limit, 'offset': offset},
      );
      final data = res.data ?? const {};
      final results = (data['results'] as List?) ?? const [];
      return FeedPage(
        items: results
            .whereType<Map<String, dynamic>>()
            .map(_parseCampaign)
            .toList(growable: false),
        total: (data['count'] as num?)?.toInt() ?? 0,
        hasNext: data['next'] != null,
        nextOffset: offset + limit,
      );
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }

  Future<FeedPage<NewsArticle>> latestArticles({
    int limit = 10,
    int offset = 0,
  }) async {
    try {
      final url = '${ApiConfig.baseUrl}/api/v2/pages/';
      final res = await _dio.get<Map<String, dynamic>>(
        url,
        queryParameters: {
          'type': 'cms.BlogPostPage',
          // cover_image_data = property model qui renvoie {url, width, height, alt}
          // depuis une rendition fill-1280x720, parfait pour un carousel mobile.
          'fields': 'excerpt,first_published_at,cover_image_data',
          'limit': limit,
          'offset': offset,
          'order': '-first_published_at',
        },
      );
      final data = res.data ?? const {};
      final items = (data['items'] as List?) ?? const [];
      final total = ((data['meta'] as Map?)?['total_count'] as num?)?.toInt() ?? 0;
      return FeedPage(
        items: items
            .whereType<Map<String, dynamic>>()
            .map(_parseArticle)
            .toList(growable: false),
        total: total,
        hasNext: offset + limit < total,
        nextOffset: offset + limit,
      );
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
      montantMin: num.tryParse('${json['montant_min']}') ?? 0,
      montantMax: num.tryParse('${json['montant_max']}') ?? 0,
      tauxInteret: num.tryParse('${json['taux_interet']}') ?? 0,
      dateFin: DateTime.tryParse((json['date_fin'] as String?) ?? '') ??
          DateTime.now(),
      flyerUrl: (json['flyer_url'] as String?)?.isNotEmpty == true
          ? json['flyer_url'] as String
          : null,
      fraisEtudeMontant: json['frais_etude_montant'] == null
          ? null
          : num.tryParse('${json['frais_etude_montant']}'),
      membreRequis: json['membre_requis'] as bool? ?? true,
    );
  }

  NewsArticle _parseArticle(Map<String, dynamic> json) {
    final meta = (json['meta'] as Map<String, dynamic>?) ?? const {};
    String? cover;
    final coverRaw = json['cover_image_data'];
    if (coverRaw is Map<String, dynamic>) {
      final relative = coverRaw['url'] as String?;
      if (relative != null && relative.isNotEmpty) {
        // L'URL renvoyée par Wagtail rendition est relative (/media/...).
        // On la complète avec la baseUrl Dio pour que CachedNetworkImage
        // puisse aller la chercher depuis le device.
        cover = relative.startsWith('http')
            ? relative
            : '${ApiConfig.baseUrl}$relative';
      }
    }
    // Wagtail expose html_url comme http://localhost:3200/... Lorsque l'app
    // tourne sur device, localhost résout sur le téléphone, pas la machine
    // hôte. On remplace 'localhost' par la baseUrl host pour que le tap
    // ouvre la vitrine sur le bon host.
    String htmlUrl = (meta['html_url'] as String?) ?? '';
    if (htmlUrl.contains('://localhost:')) {
      final host = Uri.parse(ApiConfig.baseUrl).host;
      htmlUrl = htmlUrl.replaceFirst('localhost', host);
    }
    return NewsArticle(
      id: (json['id'] as num?)?.toInt() ?? 0,
      title: (json['title'] as String?) ?? '',
      excerpt: (json['excerpt'] as String?) ?? '',
      publishedAt: DateTime.tryParse(
            (meta['first_published_at'] as String?) ?? '',
          ) ??
          DateTime.now(),
      htmlUrl: htmlUrl,
      heroImageUrl: cover,
    );
  }
}

/// Wrapper pagination — items chargés + flag has_next + offset à demander.
class FeedPage<T> {
  const FeedPage({
    required this.items,
    required this.total,
    required this.hasNext,
    required this.nextOffset,
  });

  final List<T> items;
  final int total;
  final bool hasNext;
  final int nextOffset;
}
