import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/di/providers.dart';
import '../../../../core/usecases/usecase.dart';
import '../../../../core/utils/pollable_notifier.dart';
import '../../domain/entities/eligibility.dart';
import '../../domain/entities/loan.dart';
import '../../domain/entities/loan_renewal.dart';
import '../../domain/entities/loan_request.dart';
import '../../domain/entities/loan_request_submission.dart';
import '../../domain/usecases/make_loan_repayment.dart';
import '../../domain/usecases/pay_loan_request_study_fee.dart';
import '../../domain/usecases/pay_study_fee_from_savings.dart';
import '../../domain/usecases/request_loan_renewal.dart';
import '../../domain/usecases/submit_loan_request.dart';
import '../../domain/usecases/upload_loan_request_attachment.dart';


/// Liste des crédits actifs du membre . reload après chaque write.
class LoansNotifier extends AsyncNotifier<List<Loan>>
    with PollableAsyncNotifier<List<Loan>> {
  late final _getMine = ref.read(getMyActiveLoansUseCaseProvider);

  @override
  Future<List<Loan>> build() async {
    final loans = await _getMine.call(const NoParams());
    seedPollHash(loans);
    return loans;
  }

  Future<void> refresh() =>
      silentRefresh(() => _getMine.call(const NoParams()));

  /// Effectue un remboursement → met à jour la liste avec le Loan retourné.
  Future<Loan> repay({
    required int loanId,
    required num montant,
    required String phone,
    required String network,
  }) async {
    final useCase = ref.read(makeLoanRepaymentUseCaseProvider);
    final updated = await useCase.call(
      MakeLoanRepaymentParams(
        loanId: loanId,
        montant: montant,
        phone: phone,
        network: network,
      ),
    );
    await refresh();
    return updated;
  }

  /// Demande la reconduction d'un crédit (Articles 9-11).
  Future<LoanRenewalEntity> requestRenewal({
    required int loanId,
    required bool comptant,
  }) async {
    final useCase = ref.read(requestLoanRenewalUseCaseProvider);
    final renewal = await useCase.call(
      RequestLoanRenewalParams(
        loanId: loanId,
        comptant: comptant,
      ),
    );
    await refresh();
    return renewal;
  }

  /// Règle les intérêts de reconduction sur l'épargne classique.
  Future<LoanRenewalEntity> payRenewalInterestFromSavings(int renewalId) async {
    final repo = ref.read(loansRepositoryProvider);
    final updated = await repo.payRenewalInterestFromSavings(renewalId);
    await refresh();
    return updated;
  }
}

final loansProvider =
    AsyncNotifierProvider<LoansNotifier, List<Loan>>(LoansNotifier.new);


/// Crédits CLÔTURÉS du membre (non masqués). Sert la section « Clôturés » :
/// un crédit dont les remboursements sont finis y apparaît en « Clôturé », et
/// le membre peut le masquer de sa vue (soft-hide, rien n'est supprimé en base).
class ClosedLoansNotifier extends AsyncNotifier<List<Loan>> {
  @override
  Future<List<Loan>> build() =>
      ref.read(loansRepositoryProvider).myClosedLoans();

  Future<void> refresh() async {
    state = const AsyncLoading();
    state = await AsyncValue.guard(
      () => ref.read(loansRepositoryProvider).myClosedLoans(),
    );
  }

  /// Masque un crédit clôturé de la vue du membre puis rafraîchit la liste.
  Future<void> hide(int loanId) async {
    await ref.read(loansRepositoryProvider).hideLoan(loanId);
    await refresh();
  }
}

final closedLoansProvider =
    AsyncNotifierProvider<ClosedLoansNotifier, List<Loan>>(
  ClosedLoansNotifier.new,
);


/// Liste des demandes de crédit du membre.
class LoanRequestsNotifier extends AsyncNotifier<List<LoanRequestEntity>>
    with PollableAsyncNotifier<List<LoanRequestEntity>> {
  late final _getMine = ref.read(getMyLoanRequestsUseCaseProvider);

  @override
  Future<List<LoanRequestEntity>> build() async {
    final reqs = await _getMine.call(const NoParams());
    seedPollHash(reqs);
    return reqs;
  }

  Future<void> refresh() =>
      silentRefresh(() => _getMine.call(const NoParams()));

  /// Soumet une nouvelle demande de crédit.
  ///
  /// CH-9 . [moyenReception] + [recipientPhone] : canal choisi par le membre
  /// pour recevoir le décaissement (optionnels).
  ///
  /// CH-7 . Renvoie un [LoanRequestSubmission] qui inclut la demande créée
  /// + le bloc `frais_a_payer` (montant + notice non-remboursable) à régler
  /// avant que la demande ne passe en instruction.
  Future<LoanRequestSubmission> submit({
    required num montantDemande,
    required int dureeMois,
    required String motif,
    LoanReceiveChannel? moyenReception,
    String? recipientPhone,
    Map<String, Object?> extraValues = const {},
  }) async {
    final useCase = ref.read(submitLoanRequestUseCaseProvider);
    final submission = await useCase.call(
      SubmitLoanRequestParams(
        montantDemande: montantDemande,
        dureeMois: dureeMois,
        motif: motif,
        moyenReception: moyenReception,
        recipientPhone: recipientPhone,
        extraValues: extraValues,
      ),
    );
    await refresh();
    return submission;
  }

  /// CH-5 . Upload une pièce jointe sur un LoanRequest existant.
  Future<void> uploadAttachment({
    required int loanRequestId,
    required String schemaFieldId,
    required String filePath,
    required String fileName,
  }) async {
    final useCase = ref.read(uploadLoanRequestAttachmentUseCaseProvider);
    await useCase.call(
      UploadLoanRequestAttachmentParams(
        loanRequestId: loanRequestId,
        schemaFieldId: schemaFieldId,
        filePath: filePath,
        fileName: fileName,
      ),
    );
  }

  /// CH-7 . Règle les frais d'étude de la demande EN_ATTENTE via Mobile Money.
  /// L'UI rafraîchit la liste pour refléter la bascule attendue en
  /// `enInstruction` (effective dès que le webhook Tara valide le paiement).
  Future<void> payStudyFee({
    required String phone,
    required String network,
    int? montant,
  }) async {
    final useCase = ref.read(payLoanRequestStudyFeeUseCaseProvider);
    await useCase.call(
      PayLoanRequestStudyFeeParams(
        phone: phone,
        network: network,
        montant: montant,
      ),
    );
    await refresh();
  }

  /// Porte des frais 2026 . Règle les frais sur l'épargne classique.
  /// Contrairement au canal Mobile Money, la bascule de statut est déjà
  /// effective au retour : le refresh reflète l'état final, pas une attente.
  Future<void> payStudyFeeFromSavings({required int requestId}) async {
    final useCase = ref.read(payStudyFeeFromSavingsUseCaseProvider);
    await useCase.call(PayStudyFeeFromSavingsParams(requestId: requestId));
    await refresh();
  }
}

final loanRequestsProvider = AsyncNotifierProvider<LoanRequestsNotifier,
    List<LoanRequestEntity>>(LoanRequestsNotifier.new);


/// Éligibilité du membre à demander un nouveau crédit.
class EligibilityNotifier extends AsyncNotifier<Eligibility>
    with PollableAsyncNotifier<Eligibility> {
  late final _get = ref.read(getEligibilityUseCaseProvider);

  @override
  Future<Eligibility> build() async {
    final elig = await _get.call(const NoParams());
    seedPollHash(elig);
    return elig;
  }

  Future<void> refresh() => silentRefresh(() => _get.call(const NoParams()));
}

final eligibilityProvider =
    AsyncNotifierProvider<EligibilityNotifier, Eligibility>(
        EligibilityNotifier.new,);
