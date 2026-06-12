import '../entities/eligibility.dart';
import '../entities/lender_payout.dart';
import '../entities/loan.dart';
import '../entities/loan_renewal.dart';
import '../entities/loan_request.dart';

abstract class LoansRepository {
  /// Crédits en cours du membre (statut != cloture).
  Future<List<Loan>> myActiveLoans();

  /// Demandes de crédit du membre (toutes statuts confondus).
  Future<List<LoanRequestEntity>> myRequests();

  /// CH-12 — Versements d'intérêts reçus en tant que prêteur, triés par
  /// date desc (les 200 plus récents).
  Future<List<LenderPayout>> myLenderPayouts();

  /// Vérification d'éligibilité à une **nouvelle** demande de crédit.
  Future<Eligibility> eligibility();

  /// Soumet une demande de crédit — renvoie la LoanRequest créée.
  /// Lève `ValidationFailure` / `BusinessFailure` côté domain.
  ///
  /// CH-9 — [moyenReception] + [recipientPhone] : canal choisi par le membre
  /// pour recevoir le décaissement. Optionnels pour rétro-compat ; quand
  /// renseignés, le téléphone est obligatoire si le canal est Tara OM/MoMo.
  Future<LoanRequestEntity> submitRequest({
    required num montantDemande,
    required int dureeMois,
    required String motif,
    LoanReceiveChannel? moyenReception,
    String? recipientPhone,
  });

  /// Effectue un remboursement d'échéance via Mobile Money.
  /// Renvoie le Loan mis à jour (solde restant, statut, échéances).
  Future<Loan> repay({
    required int loanId,
    required num montant,
    required String phone,
    required String network,
  });

  /// Demande la reconduction d'un crédit en cours (Articles 9-11).
  /// [comptant] = true → intérêts versés au comptant (10 %), sinon reportés
  /// (15 %). Lève `BusinessFailure` si le crédit a déjà été reconduit.
  Future<LoanRenewalEntity> requestRenewal({
    required int loanId,
    required bool comptant,
  });
}
