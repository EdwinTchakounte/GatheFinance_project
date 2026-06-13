import '../../domain/entities/savings_account.dart';
import '../../domain/entities/savings_transaction.dart';
import 'savings_remote_datasource.dart';

/// Source en mémoire pour l'**épargne classique** — dissociée de la cotisation
/// journalière. Compte vierge au départ (solde 0) : le membre l'alimente par
/// des dépôts libres. Les règles métier (taux, plafonds) seront branchées plus
/// tard côté backend (`ClassicSavingsConfig`).
class ClassicSavingsMockDataSource implements SavingsRemoteDataSource {
  SavingsAccount? _account;

  static SavingsAccount _seed() => SavingsAccount(
        id: 2,
        solde: 0,
        dateOuverture: DateTime.now(),
        tauxInteret: 0, // règles à définir
        transactions: const [],
      );

  @override
  Future<SavingsAccount> fetchMine() async {
    await Future<void>.delayed(const Duration(milliseconds: 350));
    _account ??= _seed();
    return _account!;
  }

  @override
  Future<SavingsAccount> deposit({
    required num amount,
    required String phone,
    required String network,
    bool isPlacement = false,
    int nbJoursCouverts = 1,
  }) async {
    // Simule l'appel Tara + le webhook (dépôt épargne classique).
    await Future<void>.delayed(const Duration(milliseconds: 1900));
    _account ??= _seed();
    final newBalance = _account!.solde + amount;
    final newTx = SavingsTransaction(
      id: DateTime.now().millisecondsSinceEpoch,
      type: SavingsType.depot,
      montant: amount,
      soldeApres: newBalance,
      date: DateTime.now(),
    );
    _account = _account!.copyWith(
      solde: newBalance,
      transactions: [newTx, ..._account!.transactions],
    );
    return _account!;
  }
}
