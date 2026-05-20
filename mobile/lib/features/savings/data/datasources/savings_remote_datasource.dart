import '../../domain/entities/savings_account.dart';

abstract class SavingsRemoteDataSource {
  Future<SavingsAccount> fetchMine();

  Future<SavingsAccount> deposit({
    required num amount,
    required String phone,
    required String network,
  });
}
