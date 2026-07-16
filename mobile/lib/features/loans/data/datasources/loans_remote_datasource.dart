import '../../../forms/domain/entities/form_schema.dart';
import '../../domain/entities/eligibility.dart';
import '../../domain/entities/lender_payout.dart';
import '../../domain/entities/loan.dart';
import '../../domain/entities/loan_renewal.dart';
import '../../domain/entities/loan_request.dart';
import '../../domain/entities/loan_request_submission.dart';

abstract class LoansRemoteDataSource {
  Future<List<Loan>> myActiveLoans();

  Future<List<LoanRequestEntity>> myRequests();

  Future<Eligibility> eligibility();

  /// CH-12 — Versements d'intérêts reçus en tant que prêteur (refonte §7.5).
  Future<List<LenderPayout>> myLenderPayouts();

  Future<LoanRequestSubmission> submitRequest({
    required num montantDemande,
    required int dureeMois,
    required String motif,
    // CH-9 — Canal choisi par le membre. Optionnels pour rétro-compat.
    LoanReceiveChannel? moyenReception,
    String? recipientPhone,
    // CH-5 — Champs scalaires extra du FormSchema actif.
    Map<String, Object?> extraValues = const {},
  });

  /// CH-7 — Règle les frais d'étude (`frais_demande_credit`) via Mobile Money.
  /// Le backend identifie la LoanRequest EN_ATTENTE du membre côté webhook.
  Future<void> payStudyFee({
    required String phone,
    required String network,
    int? montant,
  });

  /// Porte des frais 2026 — 3e canal : déduction sur l'épargne classique.
  ///
  /// Rien à voir avec [payStudyFee] : c'est un transfert interne, donc
  /// synchrone. Pas de Tara, pas de `paymentUrl`, pas de webhook à attendre —
  /// la demande a déjà changé de statut au retour.
  ///
  /// Lève une erreur métier si le retirable ne couvre pas les frais (le
  /// placement et l'épargne gelée en garantie ne sont pas ponctionnables).
  Future<void> payStudyFeeFromSavings({required int requestId});

  /// CH-5 — Récupère le FormSchema actif pour le formulaire de demande.
  /// `null` si aucun schéma actif (mode legacy).
  Future<FormSchema?> getActiveLoanRequestSchema();

  /// CH-5 — Upload multipart d'une pièce jointe sur un LoanRequest existant.
  Future<void> uploadLoanRequestAttachment({
    required int loanRequestId,
    required String schemaFieldId,
    required String filePath,
    required String fileName,
  });

  Future<Loan> repay({
    required int loanId,
    required num montant,
    required String phone,
    required String network,
  });

  Future<LoanRenewalEntity> requestRenewal({
    required int loanId,
    required bool comptant,
  });
}
