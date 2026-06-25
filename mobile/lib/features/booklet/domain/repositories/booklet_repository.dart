import '../entities/booklet_order.dart';

abstract class BookletRepository {
  /// Liste des commandes du membre, plus récente d'abord.
  Future<List<BookletOrder>> myOrders();

  /// Lance une nouvelle commande (paiement Mobile Money simulé).
  Future<BookletOrder> order({
    required String phone,
    required String network,
    int? montant,
  });
}
