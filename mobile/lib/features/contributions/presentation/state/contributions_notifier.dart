import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/di/providers.dart';
import '../../../../core/network/api_config.dart';
import '../../data/contributions_dio_datasource.dart';
import '../../data/contributions_mock_datasource.dart';
import '../../data/contributions_remote_datasource.dart';
import '../../domain/entities/contribution.dart';

/// Sélectionne mock ou Dio selon `ApiConfig.useMocks`. Aligné sur la
/// convention `xxxDataSourceProvider` des autres features.
final contributionsDataSourceProvider =
    Provider<ContributionsRemoteDataSource>(
  (ref) => ApiConfig.useMocks
      ? ContributionsMockDataSource()
      : ContributionsDioDataSource(ref.watch(apiClientProvider)),
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

/// Total des cotisations *validées* — pour la page « Mes états ».
final totalContributionsValideesProvider = Provider.autoDispose<num>((ref) {
  final list = ref.watch(contributionsProvider).valueOrNull ?? [];
  num n = 0;
  for (final c in list) {
    if (c.statut == ContributionStatus.valide) n += c.montant;
  }
  return n;
});
