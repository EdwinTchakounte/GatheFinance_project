import 'package:flutter/foundation.dart';

import 'savings_transaction.dart';

@immutable
class SavingsAccount {
  const SavingsAccount({
    required this.id,
    required this.solde,
    required this.dateOuverture,
    required this.tauxInteret,
    required this.transactions,
    this.soldeLibre,
    this.soldePlacementActif,
    this.soldeDisponibleRetrait,
    this.montantGeleCredit,
    this.montantGeleApport,
    this.montantGeleAvaliste,
    this.placementOpen,
    this.placementEligibilityMonths,
    this.cachedAt,
  });

  final int id;
  final num solde;
  final DateTime dateOuverture;
  final num tauxInteret;
  final List<SavingsTransaction> transactions;

  /// Épargne classique uniquement : part librement retirable (= solde total −
  /// placements encore actifs) et montant bloqué en placement (garantit le
  /// funding crédit). `null` pour le compte de collecte, qui n'expose pas ces
  /// champs. L'écran de retrait borne la saisie sur [soldeRetirable].
  final num? soldeLibre;
  final num? soldePlacementActif;

  /// Refonte garantie crédit 2026 (épargne classique) : part réellement
  /// disponible au retrait (`solde_disponible_retrait`) une fois retiré le
  /// montant gelé en garantie de crédit (`montant_gele_credit`). `null` pour
  /// la collecte / snapshots plus anciens.
  final num? soldeDisponibleRetrait;
  final num? montantGeleCredit;

  /// Scission du gel par MOTIF (règle « mobilisable ssi motif = ce crédit ») :
  ///   • [montantGeleApport]   = collatéral de MES crédits → mobilisable pour les
  ///     solder (bouton « Transférer mon apport gelé ») ;
  ///   • [montantGeleAvaliste] = caution donnée sur le crédit d'un AUTRE membre →
  ///     NON mobilisable, libérée à la clôture du crédit garanti.
  /// `null` pour la collecte / snapshots plus anciens.
  final num? montantGeleApport;
  final num? montantGeleAvaliste;

  /// Épargne classique : `true` tant que CE membre peut encore verser en
  /// PLACEMENT (verrou global + fenêtre des N premiers mois d'ancienneté).
  /// Quand `false`, l'UI masque le choix « placement » → tout dépôt part en
  /// épargne libre. `null` = donnée absente (collecte / snapshot ancien) →
  /// l'UI traite alors le placement comme ouvert (comportement historique).
  final bool? placementOpen;

  /// Durée de la fenêtre d'éligibilité au placement (mois), pour l'affichage
  /// (« placement ouvert les 6 premiers mois »). `null` si non fourni.
  final int? placementEligibilityMonths;

  /// Plafond réellement retirable : la part explicitement disponible au retrait
  /// si le backend la fournit (épargne classique, garantie crédit déduite),
  /// sinon la part libre, sinon le solde complet (collecte).
  num get soldeRetirable => soldeDisponibleRetrait ?? soldeLibre ?? solde;

  /// Quand on a chargé ce snapshot depuis le cache local (offline fallback).
  /// `null` quand la donnée vient d'un fetch réseau frais. L'UI affiche une
  /// bannière "données du XX/XX à HH:MM" si non null.
  final DateTime? cachedAt;

  /// Copie immuable avec valeurs surchargées — utilisée pour les optimistic
  /// updates côté presentation (ex. dépôt simulé).
  SavingsAccount copyWith({
    num? solde,
    List<SavingsTransaction>? transactions,
    DateTime? cachedAt,
  }) {
    return SavingsAccount(
      id: id,
      solde: solde ?? this.solde,
      soldeLibre: soldeLibre,
      soldePlacementActif: soldePlacementActif,
      soldeDisponibleRetrait: soldeDisponibleRetrait,
      montantGeleCredit: montantGeleCredit,
      montantGeleApport: montantGeleApport,
      montantGeleAvaliste: montantGeleAvaliste,
      placementOpen: placementOpen,
      placementEligibilityMonths: placementEligibilityMonths,
      dateOuverture: dateOuverture,
      tauxInteret: tauxInteret,
      transactions: transactions ?? this.transactions,
      cachedAt: cachedAt ?? this.cachedAt,
    );
  }

  Map<String, Object?> toJson() => {
        'id': id,
        'solde': solde,
        if (soldeLibre != null) 'solde_libre': soldeLibre,
        if (soldePlacementActif != null)
          'solde_placement_actif': soldePlacementActif,
        if (soldeDisponibleRetrait != null)
          'solde_disponible_retrait': soldeDisponibleRetrait,
        if (montantGeleCredit != null) 'montant_gele_credit': montantGeleCredit,
        if (montantGeleApport != null) 'montant_gele_apport': montantGeleApport,
        if (montantGeleAvaliste != null)
          'montant_gele_avaliste': montantGeleAvaliste,
        if (placementOpen != null) 'placement_open': placementOpen,
        if (placementEligibilityMonths != null)
          'placement_eligibility_months': placementEligibilityMonths,
        'date_ouverture': dateOuverture.toIso8601String(),
        'taux_interet': tauxInteret,
        'transactions': transactions.map((t) => t.toJson()).toList(),
      };

  static SavingsAccount fromJson(Map<String, dynamic> json) {
    return SavingsAccount(
      id: (json['id'] as num?)?.toInt() ?? 0,
      solde: (json['solde'] as num?) ?? 0,
      // Présents uniquement sur le snapshot épargne classique (null sinon).
      soldeLibre: json['solde_libre'] as num?,
      soldePlacementActif: json['solde_placement_actif'] as num?,
      soldeDisponibleRetrait: json['solde_disponible_retrait'] as num?,
      montantGeleCredit: json['montant_gele_credit'] as num?,
      montantGeleApport: json['montant_gele_apport'] as num?,
      montantGeleAvaliste: json['montant_gele_avaliste'] as num?,
      placementOpen: json['placement_open'] as bool?,
      placementEligibilityMonths:
          (json['placement_eligibility_months'] as num?)?.toInt(),
      dateOuverture:
          DateTime.tryParse((json['date_ouverture'] as String?) ?? '') ??
              DateTime.now(),
      tauxInteret: (json['taux_interet'] as num?) ?? 0,
      transactions: ((json['transactions'] as List?) ?? const [])
          .map((e) => SavingsTransaction.fromJson(e as Map<String, dynamic>))
          .toList(growable: false),
    );
  }
}
