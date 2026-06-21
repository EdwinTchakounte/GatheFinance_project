import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/di/providers.dart';
import '../../../../core/usecases/usecase.dart';
import '../../domain/entities/eligibility.dart';
import '../../domain/entities/loan.dart';
import '../../domain/entities/loan_renewal.dart';
import '../../domain/entities/loan_request.dart';
import '../../domain/entities/loan_request_submission.dart';
import '../../domain/usecases/make_loan_repayment.dart';
import '../../domain/usecases/pay_loan_request_study_fee.dart';
import '../../domain/usecases/request_loan_renewal.dart';
import '../../domain/usecases/submit_loan_request.dart';
import '../../domain/usecases/upload_loan_request_attachment.dart';


/// Liste des crédits actifs du membre — reload après chaque write.
class LoansNotifier extends AsyncNotifier<List<Loan>> {
  late final _getMine = ref.read(getMyActiveLoansUseCaseProvider);

  @override
  Future<List<Loan>> build() => _getMine.call(const NoParams());

  Future<void> refresh() async {
    state = const AsyncValue.loading();
    state = await AsyncValue.guard(() => _getMine.call(const NoParams()));
  }

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
}

final loansProvider =
    AsyncNotifierProvider<LoansNotifier, List<Loan>>(LoansNotifier.new);


/// Liste des demandes de crédit du membre.
class LoanRequestsNotifier extends AsyncNotifier<List<LoanRequestEntity>> {
  late final _getMine = ref.read(getMyLoanRequestsUseCaseProvider);

  @override
  Future<List<LoanRequestEntity>> build() => _getMine.call(const NoParams());

  Future<void> refresh() async {
    state = const AsyncValue.loading();
    state = await AsyncValue.guard(() => _getMine.call(const NoParams()));
  }

  /// Soumet une nouvelle demande de crédit.
  ///
  /// CH-9 — [moyenReception] + [recipientPhone] : canal choisi par le membre
  /// pour recevoir le décaissement (optionnels).
  ///
  /// CH-7 — Renvoie un [LoanRequestSubmission] qui inclut la demande créée
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

  /// CH-5 — Upload une pièce jointe sur un LoanRequest existant.
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

  /// CH-7 — Règle les frais d'étude de la demande EN_ATTENTE via Mobile Money.
  /// L'UI rafraîchit la liste pour refléter la bascule attendue en
  /// `enInstruction` (effective dès que le webhook Tara valide le paiement).
  Future<void> payStudyFee({
    required String phone,
    required String network,
  }) async {
    final useCase = ref.read(payLoanRequestStudyFeeUseCaseProvider);
    await useCase.call(
      PayLoanRequestStudyFeeParams(phone: phone, network: network),
    );
    await refresh();
  }
}

final loanRequestsProvider = AsyncNotifierProvider<LoanRequestsNotifier,
    List<LoanRequestEntity>>(LoanRequestsNotifier.new);


/// Éligibilité du membre à demander un nouveau crédit.
class EligibilityNotifier extends AsyncNotifier<Eligibility> {
  late final _get = ref.read(getEligibilityUseCaseProvider);

  @override
  Future<Eligibility> build() => _get.call(const NoParams());

  Future<void> refresh() async {
    state = const AsyncValue.loading();
    state = await AsyncValue.guard(() => _get.call(const NoParams()));
  }
}

final eligibilityProvider =
    AsyncNotifierProvider<EligibilityNotifier, Eligibility>(
        EligibilityNotifier.new,);
