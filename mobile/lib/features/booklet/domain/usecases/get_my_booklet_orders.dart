import '../../../../core/usecases/usecase.dart';
import '../entities/booklet_order.dart';
import '../repositories/booklet_repository.dart';

class GetMyBookletOrders extends UseCase<List<BookletOrder>, NoParams> {
  const GetMyBookletOrders(this._repo);
  final BookletRepository _repo;

  @override
  Future<List<BookletOrder>> call(NoParams params) => _repo.myOrders();
}
