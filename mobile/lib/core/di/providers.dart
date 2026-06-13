/// Injection de dépendances centralisée — un endroit unique pour câbler les
/// couches (data → domain → presentation).
///
/// Convention :
///   - `xxxDataSourceProvider`   → instance singleton de la datasource
///   - `xxxRepositoryProvider`   → impl consommant la datasource
///   - `xxxUseCaseProvider`      → use case consommant le repository
///   - Les notifiers (`AsyncNotifierProvider`) consomment uniquement les usecases.
///
/// Pour basculer sur l'API réelle : remplacer `XxxMockDataSource()` par
/// `XxxDioDataSource(dio)` dans ce fichier — rien d'autre à toucher.
library;

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../network/api_client.dart';
import '../network/api_config.dart';
import '../usecases/usecase.dart';

// ---- Auth -----------------------------------------------------------------
import '../../features/auth/data/datasources/auth_dio_datasource.dart';
import '../../features/auth/data/datasources/membership_dio_datasource.dart';
import '../../features/auth/data/datasources/auth_mock_datasource.dart';
import '../../features/auth/data/datasources/auth_remote_datasource.dart';
import '../../features/auth/data/repositories/auth_repository_impl.dart';
import '../../features/auth/domain/repositories/auth_repository.dart';
import '../../features/auth/domain/usecases/confirm_password_reset.dart';
import '../../features/auth/domain/usecases/get_current_member.dart';
import '../../features/auth/domain/usecases/request_password_reset.dart';
import '../../features/auth/domain/usecases/sign_in.dart';
import '../../features/auth/domain/usecases/sign_out.dart';

// ---- Savings --------------------------------------------------------------
import '../../features/savings/data/datasources/classic_savings_mock_datasource.dart';
import '../../features/savings/data/datasources/savings_dio_datasource.dart';
import '../../features/savings/data/datasources/savings_mock_datasource.dart';
import '../../features/savings/data/datasources/savings_remote_datasource.dart';
import '../../features/savings/data/repositories/savings_repository_impl.dart';
import '../../features/savings/domain/repositories/savings_repository.dart';
import '../../features/savings/domain/usecases/deposit_savings.dart';
import '../../features/savings/domain/usecases/get_my_savings.dart';

// ---- Loans ----------------------------------------------------------------
import '../../features/loans/data/datasources/loans_dio_datasource.dart';
import '../../features/loans/data/datasources/loans_mock_datasource.dart';
import '../../features/loans/data/datasources/loans_remote_datasource.dart';
import '../../features/loans/data/repositories/loans_repository_impl.dart';
import '../../features/loans/domain/repositories/loans_repository.dart';
import '../../features/loans/domain/usecases/get_eligibility.dart';
import '../../features/loans/domain/usecases/get_my_active_loans.dart';
import '../../features/loans/domain/usecases/get_my_lender_payouts.dart';
import '../../features/loans/domain/usecases/get_my_loan_requests.dart';
import '../../features/loans/domain/usecases/get_active_loan_request_schema.dart';
import '../../features/loans/domain/usecases/make_loan_repayment.dart';
import '../../features/loans/domain/usecases/pay_loan_request_study_fee.dart';
import '../../features/loans/domain/usecases/request_loan_renewal.dart';
import '../../features/loans/domain/usecases/submit_loan_request.dart';
import '../../features/loans/domain/usecases/upload_loan_request_attachment.dart';

// ---- Booklet --------------------------------------------------------------
import '../../features/booklet/data/datasources/booklet_dio_datasource.dart';
import '../../features/booklet/data/datasources/booklet_mock_datasource.dart';
import '../../features/booklet/data/datasources/booklet_remote_datasource.dart';
import '../../features/booklet/data/repositories/booklet_repository_impl.dart';
import '../../features/booklet/domain/repositories/booklet_repository.dart';
import '../../features/booklet/domain/usecases/get_my_booklet_orders.dart';
import '../../features/booklet/domain/usecases/order_booklet.dart';

// ---- Notifications --------------------------------------------------------
import '../../features/notifications/data/datasources/notifications_dio_datasource.dart';
import '../../features/notifications/data/datasources/notifications_mock_datasource.dart';
import '../../features/notifications/data/datasources/notifications_remote_datasource.dart';
import '../../features/notifications/data/repositories/notifications_repository_impl.dart';
import '../../features/notifications/domain/repositories/notifications_repository.dart';
import '../../features/notifications/domain/usecases/list_notifications.dart';
import '../../features/notifications/domain/usecases/mark_notification_read.dart';

// ---- Avaliste (LOT 21) ----------------------------------------------------
import '../../features/avaliste/data/datasources/avaliste_dio_datasource.dart';
import '../../features/avaliste/data/datasources/avaliste_mock_datasource.dart';
import '../../features/avaliste/data/datasources/avaliste_remote_datasource.dart';
import '../../features/avaliste/data/repositories/avaliste_repository_impl.dart';
import '../../features/avaliste/domain/repositories/avaliste_repository.dart';
import '../../features/avaliste/domain/usecases/avaliste_usecases.dart';

// ---- Onboarding -----------------------------------------------------------
import '../../features/onboarding/data/datasources/onboarding_local_datasource.dart';
import '../../features/onboarding/data/repositories/onboarding_repository_impl.dart';
import '../../features/onboarding/domain/repositories/onboarding_repository.dart';
import '../../features/onboarding/domain/usecases/onboarding_usecases.dart';


// ===========================================================================
// CORE — HTTP client (override dans main() après création async)
// ===========================================================================

/// Client HTTP partagé (Dio + cookies). Lance une erreur explicite si on
/// tente de l'utiliser sans avoir bootstrappé `ApiClient.create()` dans `main()`.
/// En mode mocks (`USE_MOCKS=true`) il n'est jamais lu : les datasources
/// renvoient des données en mémoire.
final apiClientProvider = Provider<ApiClient>((ref) {
  throw StateError(
    'ApiClient non initialisé — main() doit override apiClientProvider '
    'avec le résultat de ApiClient.create() avant runApp().',
  );
});


// ===========================================================================
// AUTH
// ===========================================================================

final authDataSourceProvider = Provider<AuthRemoteDataSource>(
  (ref) => ApiConfig.useMocks
      ? AuthMockDataSource()
      : AuthDioDataSource(ref.watch(apiClientProvider)),
);

final authRepositoryProvider = Provider<AuthRepository>(
  (ref) => AuthRepositoryImpl(ref.watch(authDataSourceProvider)),
);

final signInUseCaseProvider = Provider<SignIn>(
  (ref) => SignIn(ref.watch(authRepositoryProvider)),
);

final signOutUseCaseProvider = Provider<SignOut>(
  (ref) => SignOut(ref.watch(authRepositoryProvider)),
);

// Mot de passe oublié — étape 1 : demande d'envoi OTP.
final requestPasswordResetUseCaseProvider = Provider<RequestPasswordReset>(
  (ref) => RequestPasswordReset(ref.watch(authRepositoryProvider)),
);

// Mot de passe oublié — étape 2 : confirmation OTP + nouveau mot de passe.
final confirmPasswordResetUseCaseProvider = Provider<ConfirmPasswordReset>(
  (ref) => ConfirmPasswordReset(ref.watch(authRepositoryProvider)),
);

final getCurrentMemberUseCaseProvider = Provider<GetCurrentMember>(
  (ref) => GetCurrentMember(ref.watch(authRepositoryProvider)),
);


// ===========================================================================
// SAVINGS
// ===========================================================================

final savingsDataSourceProvider = Provider<SavingsRemoteDataSource>(
  (ref) => ApiConfig.useMocks
      ? SavingsMockDataSource()
      : SavingsDioDataSource(
          ref.watch(apiClientProvider),
          SavingsAccountKind.cotisation,
        ),
);

final savingsRepositoryProvider = Provider<SavingsRepository>(
  (ref) => SavingsRepositoryImpl(ref.watch(savingsDataSourceProvider)),
);

final getMySavingsUseCaseProvider = Provider<GetMySavings>(
  (ref) => GetMySavings(ref.watch(savingsRepositoryProvider)),
);

final depositSavingsUseCaseProvider = Provider<DepositSavings>(
  (ref) => DepositSavings(ref.watch(savingsRepositoryProvider)),
);

// Épargne classique — dissociée de la cotisation (endpoint distinct).
final classicSavingsDataSourceProvider = Provider<SavingsRemoteDataSource>(
  (ref) => ApiConfig.useMocks
      ? ClassicSavingsMockDataSource()
      : SavingsDioDataSource(
          ref.watch(apiClientProvider),
          SavingsAccountKind.classique,
        ),
);

final classicSavingsRepositoryProvider = Provider<SavingsRepository>(
  (ref) => SavingsRepositoryImpl(ref.watch(classicSavingsDataSourceProvider)),
);

final getMyClassicSavingsUseCaseProvider = Provider<GetMySavings>(
  (ref) => GetMySavings(ref.watch(classicSavingsRepositoryProvider)),
);

final depositClassicSavingsUseCaseProvider = Provider<DepositSavings>(
  (ref) => DepositSavings(ref.watch(classicSavingsRepositoryProvider)),
);


// ===========================================================================
// LOANS
// ===========================================================================

final loansDataSourceProvider = Provider<LoansRemoteDataSource>(
  (ref) => ApiConfig.useMocks
      ? LoansMockDataSource()
      : LoansDioDataSource(ref.watch(apiClientProvider)),
);

final loansRepositoryProvider = Provider<LoansRepository>(
  (ref) => LoansRepositoryImpl(ref.watch(loansDataSourceProvider)),
);

final getMyActiveLoansUseCaseProvider = Provider<GetMyActiveLoans>(
  (ref) => GetMyActiveLoans(ref.watch(loansRepositoryProvider)),
);

final getMyLoanRequestsUseCaseProvider = Provider<GetMyLoanRequests>(
  (ref) => GetMyLoanRequests(ref.watch(loansRepositoryProvider)),
);

final getEligibilityUseCaseProvider = Provider<GetEligibility>(
  (ref) => GetEligibility(ref.watch(loansRepositoryProvider)),
);

final submitLoanRequestUseCaseProvider = Provider<SubmitLoanRequest>(
  (ref) => SubmitLoanRequest(ref.watch(loansRepositoryProvider)),
);

// Adhésion publique (sans auth) — POST /api/forms/adhesion/ + captcha.
final membershipDataSourceProvider =
    Provider<MembershipDioDataSource>((ref) {
  return MembershipDioDataSource(ref.watch(apiClientProvider));
});

/// FormSchema actif (kind=adhesion) — null si admin n'a pas défini de version
/// active → mode legacy hardcoded. Auto-fetch + autoDispose.
final activeAdhesionSchemaProvider = FutureProvider.autoDispose((ref) async {
  return ref.watch(membershipDataSourceProvider).getActiveAdhesionSchema();
});

// CH-7 — Paiement des frais d'étude de la demande EN_ATTENTE.
final payLoanRequestStudyFeeUseCaseProvider =
    Provider<PayLoanRequestStudyFee>(
  (ref) => PayLoanRequestStudyFee(ref.watch(loansRepositoryProvider)),
);

// CH-5 — Récupération du FormSchema actif pour le formulaire de demande.
final getActiveLoanRequestSchemaUseCaseProvider =
    Provider<GetActiveLoanRequestSchema>(
  (ref) => GetActiveLoanRequestSchema(ref.watch(loansRepositoryProvider)),
);

// CH-5 — Upload d'une pièce jointe sur un LoanRequest.
final uploadLoanRequestAttachmentUseCaseProvider =
    Provider<UploadLoanRequestAttachment>(
  (ref) => UploadLoanRequestAttachment(ref.watch(loansRepositoryProvider)),
);

/// CH-5 — FormSchema actif (loan_request), null si mode legacy. Auto-fetché
/// à l'ouverture du sheet de demande. L'UI le watch via `.when()`.
final activeLoanRequestSchemaProvider =
    FutureProvider.autoDispose((ref) async {
  final useCase = ref.watch(getActiveLoanRequestSchemaUseCaseProvider);
  return useCase.call(const NoParams());
});

final makeLoanRepaymentUseCaseProvider = Provider<MakeLoanRepayment>(
  (ref) => MakeLoanRepayment(ref.watch(loansRepositoryProvider)),
);

final requestLoanRenewalUseCaseProvider = Provider<RequestLoanRenewal>(
  (ref) => RequestLoanRenewal(ref.watch(loansRepositoryProvider)),
);

// CH-12 — Lecture des versements prêteur du membre connecté.
final getMyLenderPayoutsUseCaseProvider = Provider<GetMyLenderPayouts>(
  (ref) => GetMyLenderPayouts(ref.watch(loansRepositoryProvider)),
);

/// CH-12 — État asynchrone de la liste des versements prêteur du membre.
/// Re-fetch automatique au montage. L'UI peut appeler `.invalidate(...)` pour
/// rafraîchir manuellement.
final myLenderPayoutsProvider = FutureProvider.autoDispose((ref) async {
  final useCase = ref.watch(getMyLenderPayoutsUseCaseProvider);
  return useCase.call(const NoParams());
});


// ===========================================================================
// BOOKLET
// ===========================================================================

final bookletDataSourceProvider = Provider<BookletRemoteDataSource>(
  (ref) => ApiConfig.useMocks
      ? BookletMockDataSource()
      : BookletDioDataSource(ref.watch(apiClientProvider)),
);

final bookletRepositoryProvider = Provider<BookletRepository>(
  (ref) => BookletRepositoryImpl(ref.watch(bookletDataSourceProvider)),
);

final getMyBookletOrdersUseCaseProvider = Provider<GetMyBookletOrders>(
  (ref) => GetMyBookletOrders(ref.watch(bookletRepositoryProvider)),
);

final orderBookletUseCaseProvider = Provider<OrderBooklet>(
  (ref) => OrderBooklet(ref.watch(bookletRepositoryProvider)),
);


// ===========================================================================
// NOTIFICATIONS
// ===========================================================================

final notificationsDataSourceProvider = Provider<NotificationsRemoteDataSource>(
  (ref) => ApiConfig.useMocks
      ? NotificationsMockDataSource()
      : NotificationsDioDataSource(ref.watch(apiClientProvider)),
);

final notificationsRepositoryProvider = Provider<NotificationsRepository>(
  (ref) => NotificationsRepositoryImpl(
    ref.watch(notificationsDataSourceProvider),
  ),
);

final listNotificationsUseCaseProvider = Provider<ListNotifications>(
  (ref) => ListNotifications(ref.watch(notificationsRepositoryProvider)),
);

final markNotificationReadUseCaseProvider = Provider<MarkNotificationRead>(
  (ref) => MarkNotificationRead(ref.watch(notificationsRepositoryProvider)),
);

final markAllNotificationsReadUseCaseProvider =
    Provider<MarkAllNotificationsRead>(
  (ref) => MarkAllNotificationsRead(ref.watch(notificationsRepositoryProvider)),
);


// ===========================================================================
// ONBOARDING
// ===========================================================================

final onboardingDataSourceProvider = Provider<OnboardingLocalDataSource>(
  (ref) => const OnboardingPrefsDataSource(),
);

final onboardingRepositoryProvider = Provider<OnboardingRepository>(
  (ref) => OnboardingRepositoryImpl(ref.watch(onboardingDataSourceProvider)),
);

final isOnboardingSeenUseCaseProvider = Provider<IsOnboardingSeen>(
  (ref) => IsOnboardingSeen(ref.watch(onboardingRepositoryProvider)),
);

final markOnboardingSeenUseCaseProvider = Provider<MarkOnboardingSeen>(
  (ref) => MarkOnboardingSeen(ref.watch(onboardingRepositoryProvider)),
);

final resetOnboardingUseCaseProvider = Provider<ResetOnboarding>(
  (ref) => ResetOnboarding(ref.watch(onboardingRepositoryProvider)),
);


// ===========================================================================
// AVALISTE (LOT 21)
// ===========================================================================

final avalisteDataSourceProvider = Provider<AvalisteRemoteDataSource>(
  (ref) => ApiConfig.useMocks
      ? AvalisteMockDataSource()
      : AvalisteDioDataSource(ref.watch(apiClientProvider)),
);

final avalisteRepositoryProvider = Provider<AvalisteRepository>(
  (ref) => AvalisteRepositoryImpl(ref.watch(avalisteDataSourceProvider)),
);

final listAvalisteMandatsUseCaseProvider = Provider<ListAvalisteMandats>(
  (ref) => ListAvalisteMandats(ref.watch(avalisteRepositoryProvider)),
);

final respondAvalisteMandatUseCaseProvider = Provider<RespondAvalisteMandat>(
  (ref) => RespondAvalisteMandat(ref.watch(avalisteRepositoryProvider)),
);
