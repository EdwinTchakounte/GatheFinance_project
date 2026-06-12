import '../entities/savings_account.dart';

abstract class SavingsRepository {
  /// Snapshot du compte d'épargne du membre courant (solde + N dernières opérations).
  Future<SavingsAccount> fetchMine();

  /// Lance un dépôt — renvoie la version du compte une fois le hook métier
  /// appliqué côté backend. En mock : un dépôt validé synchroniquement.
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
  });
}
