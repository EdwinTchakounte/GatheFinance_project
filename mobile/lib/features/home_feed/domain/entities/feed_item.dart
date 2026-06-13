import 'package:flutter/foundation.dart';

/// Entités du flux Home : campagnes micro-crédit actives + actualités blog.
///
/// Les deux types partagent un usage similaire côté UI (carousel horizontal
/// avec image + titre + CTA) mais leurs sources backend sont distinctes —
/// on garde donc deux classes séparées, et le `feed_dio_datasource` les
/// charge en parallèle.
@immutable
class CampaignFlyer {
  const CampaignFlyer({
    required this.id,
    required this.nom,
    required this.profilCible,
    required this.montantMax,
    required this.tauxInteret,
    required this.dateFin,
    required this.flyerUrl,
  });

  final int id;
  final String nom;
  final String profilCible;
  final num montantMax;
  final num tauxInteret;
  final DateTime dateFin;
  final String? flyerUrl;
}

@immutable
class NewsArticle {
  const NewsArticle({
    required this.id,
    required this.title,
    required this.excerpt,
    required this.publishedAt,
    required this.htmlUrl,
    this.heroImageUrl,
  });

  final int id;
  final String title;
  final String excerpt;
  final DateTime publishedAt;
  final String htmlUrl;
  final String? heroImageUrl;
}
