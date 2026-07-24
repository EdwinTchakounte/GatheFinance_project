import '../../../../core/error/exceptions.dart';
import '../../../../core/error/failures.dart';
import '../../domain/entities/savings_account.dart';
import '../../domain/entities/savings_transaction.dart';
import '../../domain/entities/withdrawal_request.dart';
import '../../domain/repositories/savings_repository.dart';
import '../datasources/savings_remote_datasource.dart';

class SavingsRepositoryImpl implements SavingsRepository {
  const SavingsRepositoryImpl(this._remote);
  final SavingsRemoteDataSource _remote;

  @override
  Future<SavingsAccount> fetchMine() async {
    try {
      return await _remote.fetchMine();
    } on NetworkException catch (e) {
      throw NetworkFailure(e.message);
    } on ServerException catch (e) {
      throw UnexpectedFailure(e.message);
    }
  }

  @override
  Future<List<SavingsTransaction>> fetchAllTransactions({int maxPages = 40}) async {
    try {
      return await _remote.fetchAllTransactions(maxPages: maxPages);
    } on NetworkException catch (e) {
      throw NetworkFailure(e.message);
    } on ServerException catch (e) {
      throw UnexpectedFailure(e.message);
    }
  }

  @override
  Future<SavingsAccount> deposit({
    required num amount,
    required String phone,
    required String network,
    bool isPlacement = false,
    int nbJoursCouverts = 1,
  }) async {
    try {
      return await _remote.deposit(
        amount: amount,
        phone: phone,
        network: network,
        isPlacement: isPlacement,
        nbJoursCouverts: nbJoursCouverts,
      );
    } on NetworkException catch (e) {
      throw NetworkFailure(e.message);
    } on ServerException catch (e) {
      throw UnexpectedFailure(e.message);
    }
  }

  @override
  Future<WithdrawalRequest> requestWithdrawal({
    required num amount,
    required String motif,
    required WithdrawalChannel channel,
    String recipientPhone = '',
    MomoNetwork? network,
    WithdrawalSource source = WithdrawalSource.collecte,
  }) async {
    try {
      return await _remote.requestWithdrawal(
        amount: amount,
        motif: motif,
        channel: channel,
        recipientPhone: recipientPhone,
        network: network,
        source: source,
      );
    } on NetworkException catch (e) {
      throw NetworkFailure(e.message);
    } on ServerException catch (e) {
      throw UnexpectedFailure(e.message);
    }
  }

  @override
  Future<List<WithdrawalRequest>> listMyWithdrawals() async {
    try {
      return await _remote.listMyWithdrawals();
    } on NetworkException catch (e) {
      throw NetworkFailure(e.message);
    } on ServerException catch (e) {
      throw UnexpectedFailure(e.message);
    }
  }
}
