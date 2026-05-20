import '../domain/entities/contribution.dart';

/// Source mock — renvoie l'historique des cotisations d'un membre.
/// Le backend exposera plus tard `GET /api/v1/payments/me/?kind=cotisations`.
class ContributionsMockDataSource {
  Future<List<Contribution>> fetchMine() async {
    await Future<void>.delayed(const Duration(milliseconds: 280));
    final now = DateTime.now();
    return [
      Contribution(
        id: 1,
        type: ContributionType.fraisInscription,
        montant: 5000,
        statut: ContributionStatus.valide,
        date: now.subtract(const Duration(days: 65)),
        reference: 'GF-2026-00001',
      ),
      Contribution(
        id: 2,
        type: ContributionType.fraisAdhesion,
        montant: 50000,
        statut: ContributionStatus.valide,
        date: now.subtract(const Duration(days: 60)),
        reference: 'GF-2026-00002',
      ),
      Contribution(
        id: 3,
        type: ContributionType.fraisCarnet,
        montant: 2500,
        statut: ContributionStatus.valide,
        date: now.subtract(const Duration(days: 55)),
        reference: 'GF-2026-00003',
      ),
      Contribution(
        id: 4,
        type: ContributionType.fraisDemandeCredit,
        montant: 3000,
        statut: ContributionStatus.valide,
        date: now.subtract(const Duration(days: 28)),
        reference: 'GF-2026-00004',
      ),
      Contribution(
        id: 5,
        type: ContributionType.fraisReconduction,
        montant: 7500,
        statut: ContributionStatus.enAttente,
        date: now.subtract(const Duration(days: 2)),
        reference: 'GF-2026-00005',
      ),
    ];
  }
}
