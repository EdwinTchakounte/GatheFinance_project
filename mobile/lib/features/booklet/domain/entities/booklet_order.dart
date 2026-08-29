import 'package:flutter/foundation.dart';

enum BookletStatus { payee, enImpression, delivree }

/// Commande de carnet membre — miroir de `apps_coop.members.BookletOrder`
/// côté backend. Statut progresse : payee → enImpression → delivree.
@immutable
class BookletOrder {
  const BookletOrder({
    required this.id,
    required this.statut,
    required this.dateCommande,
    required this.montant,
    this.typeDisplay = '',
    this.dateImpression,
    this.dateDelivrance,
    this.notesAgence = '',
  });

  final int id;
  final BookletStatus statut;
  final DateTime dateCommande;
  final num montant;
  // Type de carnet (collecte / tontine / caisse), libellé prêt à afficher —
  // carnet par type. Vide si non renvoyé par le backend.
  final String typeDisplay;
  final DateTime? dateImpression;
  final DateTime? dateDelivrance;
  final String notesAgence;
}
