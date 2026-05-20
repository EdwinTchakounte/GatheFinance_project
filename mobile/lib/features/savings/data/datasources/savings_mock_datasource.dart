import '../../../loans/domain/loan_terms.dart';
import '../../domain/entities/savings_account.dart';
import '../../domain/entities/savings_transaction.dart';
import 'savings_remote_datasource.dart';

/// Source en mémoire — un seul `SavingsAccount` partagé pour le mock.
/// Les opérations (`deposit`) mutent localement avant de retourner un snapshot.
class SavingsMockDataSource implements SavingsRemoteDataSource {
  SavingsAccount? _account;

  static SavingsAccount _seed() {
    // Épargne conforme au Règlement (Article 4) :
    //   - collecte journalière de 1 000 FCFA
    //   - intérêt de 1 % PAR MOIS sur le solde (et non 3,5 % annuel)
    // Historique reconstruit pour que `soldeApres` soit cohérent.
    final now = DateTime.now();
    final tx = <SavingsTransaction>[];
    num solde = 0;
    var id = 1;

    // Versement initial (1re cotisation) ~50 j avant.
    solde += 1000;
    tx.add(SavingsTransaction(
      id: id++,
      type: SavingsType.depot,
      montant: 1000,
      soldeApres: solde,
      date: now.subtract(const Duration(days: 50)),
    ));

    // ~40 cotisations journalières de 1 000 (cumulées au solde ; seules les
    // plus récentes sont détaillées dans l'historique affiché).
    for (var d = 49; d >= 10; d--) {
      solde += 1000;
    }

    // Intérêt mensuel 1 % crédité à J-20 (1 % du solde d'alors).
    final interet = (solde * kSavingsMonthlyRate).roundToDouble();
    solde += interet;
    tx.add(SavingsTransaction(
      id: id++,
      type: SavingsType.interet,
      montant: interet,
      soldeApres: solde,
      date: now.subtract(const Duration(days: 20)),
    ));

    // 5 dernières cotisations journalières (J-4 → J0).
    for (var d = 4; d >= 0; d--) {
      solde += 1000;
      tx.add(SavingsTransaction(
        id: id++,
        type: SavingsType.depot,
        montant: 1000,
        soldeApres: solde,
        date: now.subtract(Duration(days: d)),
      ));
    }

    // Tri décroissant (plus récent d'abord) pour l'affichage.
    tx.sort((a, b) => b.date.compareTo(a.date));

    return SavingsAccount(
      id: 1,
      solde: solde,
      dateOuverture: now.subtract(const Duration(days: 50)),
      tauxInteret: kSavingsMonthlyRate, // 1 % / mois (Art. 4)
      transactions: tx,
    );
  }

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
  }) async {
    // Simule l'appel Tara + le webhook
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
