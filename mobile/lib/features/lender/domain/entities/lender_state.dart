import 'package:flutter/foundation.dart';

/// Etat agrege de l'espace preteur d'un membre, alimente par
/// `GET /api/v1/savings/me/lender/`.
///
/// Le backend renvoie :
///   - `consent` : null si le membre n'a jamais signe, sinon objet decrivant
///     la convention (mode A global vs B tranches) et son etat (revoque ou non).
///   - `tranches` : liste detaillee des tranches du membre tous statuts.
///   - `totals` : agregat XAF par statut (disponible / engagee / liberee / annulee).
///
/// Note : la fenetre 24h de consentement par-funding-request (BUSINESS_RULES_2026
/// §5.4) n'est PAS le chemin nominal. L'admin engage directement les tranches
/// via `admin_compose_funding_manual` -> le preteur est notifie + les interets
/// sont credites automatiquement. Aucun ecran d'acceptation cote membre.
@immutable
class LenderState {
  const LenderState({
    required this.consent,
    required this.tranches,
    required this.totals,
  });

  final LenderConsent? consent;
  final List<LenderTranche> tranches;
  final LenderTotals totals;

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
