import '../../domain/entities/savings_account.dart';

abstract class SavingsRemoteDataSource {
  Future<SavingsAccount> fetchMine();

  Future<SavingsAccount> deposit({
    required num amount,
    required String phone,
    required String network,
    bool isPlacement = false,
    // LOT 6 — Multi-jours pré-payé : > 1 valide uniquement pour la cotisation
    // journalière (`epargne`). Le backend valide montant = nbJours × min_per_day.
    int nbJoursCouverts = 1,
  });
}
