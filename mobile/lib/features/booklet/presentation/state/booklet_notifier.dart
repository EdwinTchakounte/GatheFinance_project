import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/di/providers.dart';
import '../../../../core/usecases/usecase.dart';
import '../../domain/entities/booklet_order.dart';
import '../../domain/usecases/order_booklet.dart';

class BookletNotifier extends AsyncNotifier<List<BookletOrder>> {
  late final _getMine = ref.read(getMyBookletOrdersUseCaseProvider);

  @override
  Future<List<BookletOrder>> build() => _getMine.call(const NoParams());

  Future<void> refresh() async {
    state = const AsyncValue.loading();
    state = await AsyncValue.guard(() => _getMine.call(const NoParams()));
  }

  Future<BookletOrder> order({
    required String phone,
    required String network,
  }) async {
    final useCase = ref.read(orderBookletUseCaseProvider);
    final created = await useCase.call(
      OrderBookletParams(phone: phone, network: network),
    );
    await refresh();
    return created;
  }
}

final bookletProvider =
    AsyncNotifierProvider<BookletNotifier, List<BookletOrder>>(
        BookletNotifier.new,);
