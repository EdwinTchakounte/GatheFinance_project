import 'package:flutter_test/flutter_test.dart';
import 'package:gathe_finance/core/error/error_message.dart';
import 'package:gathe_finance/core/error/exceptions.dart';
import 'package:gathe_finance/core/error/failures.dart';

void main() {
  group('friendlyError', () {
    test('4xx ServerException → affiche le message métier (detail), pas «souci serveur»', () {
      // Régression : un 400 « Ce crédit n'est pas remboursable » ne doit PAS
      // devenir « Nos serveurs rencontrent un souci ».
      const e = ServerException("Ce crédit n'est pas remboursable (déjà clôturé ?).", 400);
      expect(friendlyError(e), "Ce crédit n'est pas remboursable (déjà clôturé ?).");
    });

    test('409 ServerException → message métier', () {
      const e = ServerException('Aucun apport gelé disponible pour ce crédit.', 409);
      expect(friendlyError(e), 'Aucun apport gelé disponible pour ce crédit.');
    });

    test('5xx ServerException → message serveur générique', () {
      const e = ServerException('boom', 500);
      expect(friendlyError(e), contains('serveurs rencontrent'));
    });

    test('BusinessFailure → message tel quel', () {
      const f = BusinessFailure('Montant trop élevé.');
      expect(friendlyError(f), 'Montant trop élevé.');
    });

    test('NetworkException « Connexion impossible » → message hors-ligne', () {
      const e = NetworkException('Connexion impossible.');
      expect(friendlyError(e), contains('connexion internet'));
    });
  });
}
