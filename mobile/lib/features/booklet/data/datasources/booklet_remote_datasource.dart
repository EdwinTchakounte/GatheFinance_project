import '../../domain/entities/booklet_order.dart';

abstract class BookletRemoteDataSource {
  Future<List<BookletOrder>> myOrders();

  Future<BookletOrder> order({
    required String phone,
    required String network,
  });
}
