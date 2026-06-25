import '../../../forms/domain/entities/form_schema.dart';
import '../entities/eligibility.dart';
import '../entities/lender_payout.dart';
import '../entities/loan.dart';
import '../entities/loan_renewal.dart';
import '../entities/loan_request.dart';
import '../entities/loan_request_submission.dart';

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

  /// Soumet une demande de crédit — renvoie la LoanRequest créée + les
  /// frais d'étude à régler (CH-7).
  /// Lève `ValidationFailure` / `BusinessFailure` côté domain.
  ///
  /// CH-9 — [moyenReception] + [recipientPhone] : canal choisi par le membre
  /// pour recevoir le décaissement. Optionnels pour rétro-compat ; quand
  /// renseignés, le téléphone est obligatoire si le canal est Tara OM/MoMo.
  ///
  /// CH-5 — [extraValues] : valeurs scalaires des champs supplémentaires du
  /// FormSchema actif (loan_request). Fusionnées dans le body POST et
  /// routées par le backend dans `extra_payload`.
  Future<LoanRequestSubmission> submitRequest({
    required num montantDemande,
    required int dureeMois,
    required String motif,
    LoanReceiveChannel? moyenReception,
    String? recipientPhone,
    Map<String, Object?> extraValues = const {},
  });

  /// CH-7 — Règle les frais d'étude de la demande EN_ATTENTE du membre via
  /// Mobile Money. Le backend identifie la demande par le membre, donc pas
  /// besoin de passer le `requestId`. Le webhook Tara fera passer la demande
  /// en `en_instruction` à validation du paiement.
  Future<void> payStudyFee({
    required String phone,
    required String network,
    int? montant,
  });

  /// CH-5 — Récupère le `FormSchema` actif pour `loan_request`.
  ///
  /// Renvoie `null` si aucun schéma actif n'est défini côté admin (mode
  /// legacy : seuls les champs hardcoded du sheet sont rendus). Les erreurs
  /// transport sont propagées en `NetworkFailure`/`UnexpectedFailure`.
  Future<FormSchema?> getActiveLoanRequestSchema();

  /// CH-5 — Upload une pièce jointe pour un champ `file` du FormSchema sur
  /// un LoanRequest existant. Multipart : `fichier` + `schema_field_id`.
  /// Idempotent côté backend (re-upload remplace le précédent).
  Future<void> uploadLoanRequestAttachment({
    required int loanRequestId,
    required String schemaFieldId,
    required String filePath,
    required String fileName,
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
