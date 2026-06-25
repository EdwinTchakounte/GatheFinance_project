import 'package:flutter/foundation.dart';

import '../../../../core/error/failures.dart';
import '../../../../core/usecases/usecase.dart';
import '../entities/booklet_order.dart';
import '../repositories/booklet_repository.dart';

@immutable
class OrderBookletParams {
  const OrderBookletParams({
    required this.phone,
    required this.network,
    this.montant,
  });
  final String phone;
  final String network;
  final int? montant;
}

class OrderBooklet extends UseCase<BookletOrder, OrderBookletParams> {
  const OrderBooklet(this._repo);
  final BookletRepository _repo;

  @override
  Future<BookletOrder> call(OrderBookletParams params) async {
    final digits = params.phone.replaceAll(RegExp(r'\D'), '');
    if (digits.length < 8) {
      throw const ValidationFailure(
        'Numéro Mobile Money incomplet.',
        field: 'phone',
      );
    }
    return _repo.order(
      phone: params.phone,
      network: params.network,
      montant: params.montant,
    );
  }
}
