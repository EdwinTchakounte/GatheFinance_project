import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../data/contributions_mock_datasource.dart';
import '../../domain/entities/contribution.dart';

final _dsProvider = Provider((_) => ContributionsMockDataSource());

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
