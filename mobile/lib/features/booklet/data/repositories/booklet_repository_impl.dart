import '../../../../core/error/exceptions.dart';
import '../../../../core/error/failures.dart';
import '../../domain/entities/booklet_order.dart';
import '../../domain/repositories/booklet_repository.dart';
import '../datasources/booklet_remote_datasource.dart';

class BookletRepositoryImpl implements BookletRepository {
  const BookletRepositoryImpl(this._remote);
  final BookletRemoteDataSource _remote;

  Future<T> _run<T>(Future<T> Function() op) async {
    try {
      return await op();
    } on NetworkException catch (e) {
      throw NetworkFailure(e.message);
    } on ServerException catch (e) {
      final code = e.statusCode ?? 500;
      if (code >= 400 && code < 500) throw BusinessFailure(e.message);
      throw UnexpectedFailure(e.message);
    }
  }

  @override
  Future<List<BookletOrder>> myOrders() => _run(_remote.myOrders);

  @override
  Future<BookletOrder> order({
    required String phone,
    required String network,
    int? montant,
  }) =>
      _run(() => _remote.order(
            phone: phone,
            network: network,
            montant: montant,
          ),);
}
