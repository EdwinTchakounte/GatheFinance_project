import '../entities/savings_account.dart';
import '../entities/savings_transaction.dart';
import '../entities/withdrawal_request.dart';

abstract class SavingsRepository {
  /// Snapshot du compte d'épargne du membre courant (solde + N dernières opérations).
  Future<SavingsAccount> fetchMine();

  /// Historique COMPLET des transactions (paginé serveur, agrégé). Sert la page
  /// Historique pour remonter au-delà des 10 dernières du snapshot.
  Future<List<SavingsTransaction>> fetchAllTransactions({int maxPages});

  /// Lance un dépôt — renvoie la version du compte une fois le hook métier
  /// appliqué côté backend.
  ///
  /// `phone` / `network` sont les coordonnées Mobile Money. `BusinessFailure`
  /// si le montant viole une règle (< 100 XAF, etc.).
  ///
  /// CH-3 — [isPlacement] ne s'applique qu'aux dépôts d'épargne classique :
  /// `true` = sous-canal **placement** (bloqué 12 mois, rapporte un intérêt
  /// capitalisé à maturité). Ignoré côté backend pour la cotisation.
  Future<SavingsAccount> deposit({
    required num amount,
    required String phone,
    required String network,
    bool isPlacement = false,
    // LOT 6 — Multi-jours pré-payé (cotisation uniquement, max 30 j.).
    int nbJoursCouverts = 1,
  });

  /// Demande un retrait depuis le compte cotisation. Le solde est débité
  /// atomiquement côté backend ; la demande passe en attente de validation
  /// admin. Lance `BusinessFailure` si montant > solde ou si une demande est
  /// déjà en attente.
  Future<WithdrawalRequest> requestWithdrawal({
    required num amount,
    required String motif,
    required WithdrawalChannel channel,
    String recipientPhone = '',
    MomoNetwork? network,
    WithdrawalSource source = WithdrawalSource.collecte,
  });

  /// Liste des demandes de retrait du membre (les plus récentes d'abord).
  Future<List<WithdrawalRequest>> listMyWithdrawals();
}
