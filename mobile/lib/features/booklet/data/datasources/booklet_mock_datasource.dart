import '../../domain/entities/booklet_order.dart';
import 'booklet_remote_datasource.dart';

class BookletMockDataSource implements BookletRemoteDataSource {
  BookletMockDataSource() {
    // Une commande historique délivrée pour montrer le cas « historique ».
    _orders.add(
      BookletOrder(
        id: 1,
        statut: BookletStatus.delivree,
        dateCommande: DateTime.now().subtract(const Duration(days: 90)),
        dateImpression: DateTime.now().subtract(const Duration(days: 88)),
        dateDelivrance: DateTime.now().subtract(const Duration(days: 86)),
        montant: 1000,
        notesAgence: 'Retiré à l\'agence centrale.',
      ),
    );
  }

  final List<BookletOrder> _orders = [];
  int _nextId = 2;

  @override
  Future<List<BookletOrder>> myOrders() async {
    await Future<void>.delayed(const Duration(milliseconds: 280));
    final sorted = [..._orders]
      ..sort((a, b) => b.dateCommande.compareTo(a.dateCommande));
    return List.unmodifiable(sorted);
  }

  @override
  Future<BookletOrder> order({
    required String phone,
    required String network,
  }) async {
    // Simule l'init Mobile Money + webhook qui valide le paiement.
    await Future<void>.delayed(const Duration(milliseconds: 1700));
    final order = BookletOrder(
      id: _nextId++,
      statut: BookletStatus.payee, // après paiement → statut initial
      dateCommande: DateTime.now(),
      montant: 1000,
    );
    _orders.insert(0, order);
    return order;
  }
}
