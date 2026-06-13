import 'package:flutter/foundation.dart';

/// LOT 19 — État agrégé de l'espace prêteur d'un membre, alimenté par
/// `GET /api/v1/savings/me/lender/`.
///
/// Le backend renvoie :
///   - `consent` : null si le membre n'a jamais signé, sinon objet décrivant
///     la convention (mode A global vs B tranches) et son état (révoqué ou non).
///   - `tranches` : liste détaillée des tranches du membre tous statuts.
///   - `totals` : agrégat XAF par statut (disponible / engagee / liberee / annulee).
///   - `pending_funding_requests` : demandes de financement en attente de
///     consentement (fenêtre 24h, §5.4 BUSINESS_RULES_2026).
@immutable
class LenderState {
  const LenderState({
    required this.consent,
    required this.tranches,
    required this.totals,
    required this.pendingFundingRequests,
  });

  final LenderConsent? consent;
  final List<LenderTranche> tranches;
  final LenderTotals totals;
  final List<FundingPending> pendingFundingRequests;

  bool get hasActiveConsent => consent != null && consent!.revokedAt == null;
}

@immutable
class LenderConsent {
  const LenderConsent({
    required this.isGlobal,
    required this.signedAt,
    required this.revokedAt,
  });

  final bool isGlobal;
  final DateTime signedAt;
  final DateTime? revokedAt;
}

@immutable
class LenderTranche {
  const LenderTranche({
    required this.id,
    required this.montant,
    required this.statut,
    required this.createdAt,
    this.loanId,
  });

  final int id;
  final num montant;
  final LenderTrancheStatut statut;
  final DateTime createdAt;
  final int? loanId;
}

enum LenderTrancheStatut { disponible, engagee, liberee, annulee }

@immutable
class LenderTotals {
  const LenderTotals({
    required this.disponible,
    required this.engagee,
    required this.liberee,
    required this.annulee,
  });

  final num disponible;
  final num engagee;
  final num liberee;
  final num annulee;
}

@immutable
class FundingPending {
  const FundingPending({
    required this.consentRequestId,
    required this.loanId,
    required this.memberName,
    required this.montant,
    required this.deadline,
  });

  final int consentRequestId;
  final int loanId;
  final String memberName;
  final num montant;
  final DateTime deadline;
}
