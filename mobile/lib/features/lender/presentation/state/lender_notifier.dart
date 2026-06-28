import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/di/providers.dart';
import '../../data/datasources/lender_dio_datasource.dart';
import '../../domain/entities/lender_state.dart';

/// Provider mince autour du datasource Dio. Pas de UseCase dedie :
/// les actions (opt-in, revoke, addTranche, cancelTranche) sont appelees
/// directement depuis la page car elles mutent toutes le meme etat agrege.
///
/// Note : pas de respondFunding ici. L'admin engage les tranches directement
/// cote backend, le preteur recoit une notif et les interets sont credites
/// automatiquement sur son compte epargne classique.
final lenderDataSourceProvider = Provider<LenderDioDataSource>((ref) {
  return LenderDioDataSource(ref.watch(apiClientProvider));
});

class LenderNotifier extends AutoDisposeAsyncNotifier<LenderState> {
  @override
  Future<LenderState> build() {
    return ref.read(lenderDataSourceProvider).me();
  }

  Future<void> refresh() async {
    state = const AsyncLoading();
    state = await AsyncValue.guard(
      () => ref.read(lenderDataSourceProvider).me(),
    );
  }

  Future<void> optIn({required bool isGlobal}) async {
    final ds = ref.read(lenderDataSourceProvider);
    final next = await ds.optIn(isGlobal: isGlobal);
    state = AsyncData(next);
  }

  Future<void> revoke() async {
    final ds = ref.read(lenderDataSourceProvider);
    final next = await ds.revoke();
    state = AsyncData(next);
  }

  Future<void> addTranche(num montant) async {
    final ds = ref.read(lenderDataSourceProvider);
    await ds.addTranche(montant: montant);
    await refresh();
  }
}

final lenderProvider =
    AsyncNotifierProvider.autoDispose<LenderNotifier, LenderState>(
  LenderNotifier.new,
);
