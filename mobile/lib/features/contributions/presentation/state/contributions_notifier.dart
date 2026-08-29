import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/di/providers.dart';
import '../../data/contributions_dio_datasource.dart';
import '../../data/contributions_remote_datasource.dart';
import '../../domain/entities/contribution.dart';

final contributionsDataSourceProvider =
    Provider<ContributionsRemoteDataSource>(
  (ref) => ContributionsDioDataSource(ref.watch(apiClientProvider)),
);

final _dsProvider = contributionsDataSourceProvider;

class ContributionsNotifier
    extends AutoDisposeAsyncNotifier<List<Contribution>> {
  @override
  Future<List<Contribution>> build() {
    return ref.read(_dsProvider).fetchMine();
  }

  Future<void> refresh() async {
    state = const AsyncLoading();
    state = await AsyncValue.guard(() => ref.read(_dsProvider).fetchMine());
  }
}

final contributionsProvider = AsyncNotifierProvider.autoDispose<
    ContributionsNotifier, List<Contribution>>(ContributionsNotifier.new);

/// Total des cotisations *validées* . pour la page « Mes états ».
/// Le libellé est « Total versé à la coopérative » → on somme ce que le membre
/// a RÉELLEMENT payé (montant + frais de transaction Tara), pas seulement le
/// montant net crédité.
final totalContributionsValideesProvider = Provider.autoDispose<num>((ref) {
  final list = ref.watch(contributionsProvider).valueOrNull ?? [];
  num n = 0;
  for (final c in list) {
    if (c.statut == ContributionStatus.valide) n += c.totalPaye;
  }
  return n;
});
