import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/di/providers.dart';
import '../../../../core/usecases/usecase.dart';
import '../../../../core/utils/pollable_notifier.dart';
import '../../domain/entities/booklet_order.dart';
import '../../domain/usecases/order_booklet.dart';

class BookletNotifier extends AsyncNotifier<List<BookletOrder>>
    with PollableAsyncNotifier<List<BookletOrder>> {
  late final _getMine = ref.read(getMyBookletOrdersUseCaseProvider);

  @override
  Future<List<BookletOrder>> build() async {
    final orders = await _getMine.call(const NoParams());
    seedPollHash(orders);
    return orders;
  }

  Future<void> refresh() =>
      silentRefresh(() => _getMine.call(const NoParams()));

  Future<BookletOrder> order({
    required String phone,
    required String network,
    int? montant,
  }) async {
    final useCase = ref.read(orderBookletUseCaseProvider);
    final created = await useCase.call(
      OrderBookletParams(phone: phone, network: network, montant: montant),
    );
    await refresh();
    return created;
  }
}

final bookletProvider =
    AsyncNotifierProvider<BookletNotifier, List<BookletOrder>>(
        BookletNotifier.new,);
