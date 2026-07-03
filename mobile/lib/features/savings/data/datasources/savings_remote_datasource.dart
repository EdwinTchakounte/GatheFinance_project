import '../../domain/entities/savings_account.dart';
import '../../domain/entities/withdrawal_request.dart';

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

  /// Demande un retrait — le backend débite atomiquement le solde et place
  /// la demande en attente de validation admin. Refusé si montant > solde ou
  /// si une demande est déjà en attente.
  Future<WithdrawalRequest> requestWithdrawal({
    required num amount,
    required String motif,
    required WithdrawalChannel channel,
    String recipientPhone = '',
    MomoNetwork? network,
    WithdrawalSource source = WithdrawalSource.collecte,
  });

  /// Liste les demandes de retrait du membre courant (les plus récentes
  /// d'abord). Renvoie une liste vide si aucune demande.
  Future<List<WithdrawalRequest>> listMyWithdrawals();
}
