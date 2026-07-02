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
    required this.montantMin,
    required this.montantMax,
    required this.tauxInteret,
    required this.dateFin,
    required this.flyerUrl,
    this.fraisEtudeMontant,
    this.membreRequis = true,
    this.documentsRequis = const [],
  });

  final int id;
  final String nom;
  final String profilCible;
  final num montantMin;
  final num montantMax;
  final num tauxInteret;
  final DateTime dateFin;
  // Frais d'étude : null = tarif standard, 0 = gratuit (« sans frais »).
  final num? fraisEtudeMontant;
  // False = campagne ouverte aux visiteurs non-membres (candidature vitrine).
  final bool membreRequis;
  // Pièces justificatives exigées du candidat (libellés). Vide = aucune.
  final List<String> documentsRequis;

  /// True si la campagne ne prélève aucun frais d'étude de dossier.
  bool get sansFrais => fraisEtudeMontant != null && fraisEtudeMontant == 0;
  // URL retournée par le backend — peuplée pour 100 % des campagnes
  // (vrai flyer si uploadé, sinon photo stock choisie côté serveur).
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
  // URL retournée par le backend — peuplée pour 100 % des articles
  // (vraie cover si uploadée sur Wagtail, sinon photo stock choisie
  // côté serveur via apps_cms.cms.stock_images). Le mobile ne fait
  // plus aucune logique de fallback.
  final String? heroImageUrl;
}
