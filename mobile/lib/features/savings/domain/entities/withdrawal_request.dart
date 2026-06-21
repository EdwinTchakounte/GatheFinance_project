/// Canal de remise choisi par le membre pour son retrait.
enum WithdrawalChannel {
  /// Espèces remises à l'agence — l'admin clique "Confirmer remise" quand
  /// il a effectivement remis l'argent au membre.
  presentiel,

  /// Mobile Money — payout Tara initié dès validation admin.
  momo,
}

/// Réseau Mobile Money (uniquement pour le canal [WithdrawalChannel.momo]).
enum MomoNetwork { mtn, orange, wave, airtel }

/// Statut du cycle de vie d'une demande de retrait.
///
/// Workflow :
/// ```
/// enAttente → approuvee (présentiel — solde débité, attente remise)
///                       → completee (admin marque "remis")
/// enAttente → enPayout (momo — solde débité, payout Tara en cours)
///                       → completee (webhook Tara confirme)
///                       → payoutFailed (Tara KO ; admin réessaye)
/// enAttente → rejetee
/// ```
enum WithdrawalStatus {
  enAttente,
  approuvee,
  enPayout,
  completee,
  payoutFailed,
  rejetee,
}

class WithdrawalRequest {
  const WithdrawalRequest({
    required this.id,
    required this.montant,
    required this.motif,
    required this.statut,
    required this.statutDisplay,
    required this.modePaiement,
    required this.modePaiementDisplay,
    required this.recipientPhoneMasked,
    required this.network,
    required this.motifRejet,
    required this.dateDemande,
    this.dateDecision,
    this.handedOverAt,
  });

  final int id;
  final num montant;
  final String motif;
  final WithdrawalStatus statut;
  final String statutDisplay;
  final WithdrawalChannel modePaiement;
  final String modePaiementDisplay;

  /// Numéro masqué (format `0612***34`). Vide pour les retraits présentiels.
  final String recipientPhoneMasked;
  final MomoNetwork? network;
  final String motifRejet;
  final DateTime dateDemande;
  final DateTime? dateDecision;
  final DateTime? handedOverAt;
}
