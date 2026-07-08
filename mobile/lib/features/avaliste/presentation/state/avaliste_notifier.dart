import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/di/providers.dart';
import '../../domain/entities/avaliste_mandat.dart';
import '../../domain/usecases/avaliste_usecases.dart';

class AvalisteNotifier extends AutoDisposeAsyncNotifier<AvalisteMandatList> {
  late final ListAvalisteMandats _list =
      ref.read(listAvalisteMandatsUseCaseProvider);
  late final RespondAvalisteMandat _respond =
      ref.read(respondAvalisteMandatUseCaseProvider);

  @override
  Future<AvalisteMandatList> build() {
    return _list.call(const ListAvalisteParams());
  }

  Future<void> refresh() async {
    state = const AsyncLoading();
    state = await AsyncValue.guard(
      () => _list.call(const ListAvalisteParams()),
    );
  }

  /// Répond à un mandat . émet un nouveau snapshot avec l'item à jour.
  /// Renvoie le mandat modifié ; remonte une [Exception] sur erreur (l'UI
  /// affiche un toast).
  Future<AvalisteMandat> respond({
    required int mandatId,
    required bool accept,
    String? motif,
    String? cniAvaliste,
    String? cniFichierPath,
    String? cniFichierName,
  }) async {
    final updated = await _respond.call(
      RespondAvalisteParams(
        mandatId: mandatId,
        accept: accept,
        motif: motif,
        cniAvaliste: cniAvaliste,
        cniFichierPath: cniFichierPath,
        cniFichierName: cniFichierName,
      ),
    );
    // Recharge complet . la liste reflète l'éventuelle décrémentation
    // de `pendingCount` côté serveur.
    final reloaded = await _list.call(const ListAvalisteParams());
    state = AsyncValue.data(reloaded);
    return updated;
  }
}

final avalisteProvider =
    AsyncNotifierProvider.autoDispose<AvalisteNotifier, AvalisteMandatList>(
  AvalisteNotifier.new,
);
