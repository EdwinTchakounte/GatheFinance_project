import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gathe_finance/core/utils/pollable_notifier.dart';

/// Source de données pilotable par les tests (le notifier la lit à chaque
/// build/poll).
int Function() _fetch = () => 0;

class _TestNotifier extends AsyncNotifier<int> with PollableAsyncNotifier<int> {
  int freshCount = 0;

  @override
  Future<int> build() async {
    final v = _fetch();
    seedPollHash(v);
    return v;
  }

  Future<void> poll() => silentRefresh(
        () async => _fetch(),
        onFreshData: (_) => freshCount++,
      );
}

final _provider = AsyncNotifierProvider<_TestNotifier, int>(_TestNotifier.new);

void main() {
  setUp(() => _fetch = () => 0);

  test('silentRefresh garde la donnée affichée si le fetch échoue', () async {
    _fetch = () => 1;
    final c = ProviderContainer();
    addTearDown(c.dispose);
    final n = c.read(_provider.notifier);
    await c.read(_provider.future);
    expect(c.read(_provider).value, 1);

    _fetch = () => throw Exception('réseau coupé');
    await n.poll();

    // Toujours de la donnée (pas d'écran d'erreur), valeur préservée.
    expect(c.read(_provider).hasValue, isTrue);
    expect(c.read(_provider).value, 1);
    expect(c.read(_provider).hasError, isFalse);
  });

  test('silentRefresh dédupe : aucun push si la donnée est identique',
      () async {
    _fetch = () => 5;
    final c = ProviderContainer();
    addTearDown(c.dispose);
    final n = c.read(_provider.notifier);
    await c.read(_provider.future);

    var rebuilds = 0;
    c.listen(_provider, (_, __) => rebuilds++);

    _fetch = () => 5; // identique
    await n.poll();
    expect(rebuilds, 0, reason: 'donnée identique → aucun nouvel état');
    expect(n.freshCount, 0);

    _fetch = () => 6; // change
    await n.poll();
    expect(rebuilds, 1);
    expect(n.freshCount, 1, reason: 'onFreshData seulement sur vrai changement');
    expect(c.read(_provider).value, 6);
  });

  test('silentRefresh propage l\'erreur si aucune donnée à préserver',
      () async {
    _fetch = () => throw Exception('boom');
    final c = ProviderContainer();
    addTearDown(c.dispose);
    final n = c.read(_provider.notifier);
    // build échoue → state en erreur.
    await expectLater(c.read(_provider.future), throwsA(isA<Exception>()));
    expect(c.read(_provider).hasError, isTrue);

    // Toujours en erreur, un poll qui échoue encore montre l'erreur.
    await n.poll();
    expect(c.read(_provider).hasError, isTrue);
  });
}
