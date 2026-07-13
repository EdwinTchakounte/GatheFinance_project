import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';

/// Rafraîchissement « silencieux » pour les notifiers branchés à un
/// `LivePoller` (poll toutes les 30 s).
///
/// Problème réglé : historiquement `refresh()` faisait
/// `state = AsyncLoading()` puis rechargeait. Sur une page live, ça jetait la
/// donnée affichée → rebuild complet + flicker des skeletons + badge de notifs
/// qui retombe à 0, à CHAQUE tick, même quand rien n'avait changé.
///
/// [silentRefresh] :
///  1. ne touche PAS au state pendant le fetch (la donnée reste affichée) ;
///  2. ne remplace le state que si le contenu a réellement changé
///     (déduplication par hash JSON) → zéro rebuild inutile ;
///  3. sur échec, conserve la donnée déjà affichée si on en a une (un tick de
///     polling raté ne vide pas l'écran) ; ne propage l'erreur que si l'écran
///     n'avait encore aucune donnée.
///
/// Deux mixins car `AsyncNotifier` et `AutoDisposeAsyncNotifier` n'ont pas de
/// super-type public commun (leur base `AsyncNotifierBase` est masquée par
/// riverpod). La logique est factorisée dans [_PollDedup] ; les mixins sont de
/// simples adaptateurs qui branchent le `state` du notifier.
///
/// Pour les écritures explicites (dépôt, remboursement…), garder le pattern
/// `state = AsyncLoading()` habituel : là, l'utilisateur ATTEND un feedback.

/// Cœur de la dédup, sans dépendance au type de notifier.
class _PollDedup<T> {
  String? _lastHash;

  /// Amorce le hash avec la donnée initiale (évite un rebuild superflu au
  /// premier tick).
  void seed(T value) => _lastHash = _hash(value);

  /// À partir du [current] state et du résultat [fetched] d'un fetch,
  /// retourne le nouveau state à poser (`null` = ne rien changer) et la
  /// valeur fraîche acceptée (`null` = aucune).
  (AsyncValue<T>?, T?) reduce(AsyncValue<T> current, AsyncValue<T> fetched) {
    if (fetched.hasValue) {
      final value = fetched.requireValue;
      final hash = _hash(value);
      if (current.hasValue && hash == _lastHash) {
        return (null, null); // donnée identique : rien à repousser.
      }
      _lastHash = hash;
      return (AsyncValue.data(value), value);
    }
    // fetch en erreur.
    if (!current.hasValue) {
      return (fetched, null); // aucune donnée à préserver → montrer l'erreur.
    }
    return (null, null); // on garde l'écran tel quel (tick raté).
  }

  static String _hash(Object? snapshot) {
    if (snapshot == null) return '';
    try {
      final encoded = jsonEncode(
        snapshot,
        toEncodable: (obj) {
          try {
            return (obj as dynamic).toJson();
          } catch (_) {
            return obj.toString();
          }
        },
      );
      return encoded.hashCode.toString();
    } catch (_) {
      return snapshot.toString().hashCode.toString();
    }
  }
}

/// Variante pour [AsyncNotifier].
mixin PollableAsyncNotifier<T> on AsyncNotifier<T> {
  final _dedup = _PollDedup<T>();

  /// À appeler depuis `build()` pour amorcer le hash de dédup.
  void seedPollHash(T value) => _dedup.seed(value);

  /// Recharge via [fetch] sans flicker. [onFreshData] (optionnel) n'est appelé
  /// que sur donnée réellement nouvelle (persistance snapshot best-effort).
  Future<void> silentRefresh(
    Future<T> Function() fetch, {
    void Function(T data)? onFreshData,
  }) async {
    final fetched = await AsyncValue.guard(fetch);
    final (next, fresh) = _dedup.reduce(state, fetched);
    if (next != null) state = next;
    if (fresh != null) onFreshData?.call(fresh);
  }
}

/// Variante pour [AutoDisposeAsyncNotifier] (corps identique).
mixin PollableAutoDisposeAsyncNotifier<T> on AutoDisposeAsyncNotifier<T> {
  final _dedup = _PollDedup<T>();

  void seedPollHash(T value) => _dedup.seed(value);

  Future<void> silentRefresh(
    Future<T> Function() fetch, {
    void Function(T data)? onFreshData,
  }) async {
    final fetched = await AsyncValue.guard(fetch);
    final (next, fresh) = _dedup.reduce(state, fetched);
    if (next != null) state = next;
    if (fresh != null) onFreshData?.call(fresh);
  }
}
