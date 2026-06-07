import '../domain/entities/contribution.dart';
import 'contributions_remote_datasource.dart';

/// Source mock — renvoie l'historique des cotisations d'un membre.
/// Réelle source : `GET /api/v1/payments/me/?type=...` (cf. `ContributionsDioDataSource`).
class ContributionsMockDataSource implements ContributionsRemoteDataSource {
  @override
  Future<List<Contribution>> fetchMine() async {
    await Future<void>.delayed(const Duration(milliseconds: 280));
    final now = DateTime.now();
    // Montants conformes au Règlement (Article 1 : adhésion 10 000 +
    // inscription 2 000 ; Article 4 : carnet 1 000). La reconduction est
    // SANS frais (BR1) → aucune ligne fraisReconduction.
    return [
      Contribution(
        id: 1,
        type: ContributionType.fraisInscription,
        montant: 2000,
        statut: ContributionStatus.valide,
        date: now.subtract(const Duration(days: 65)),
        reference: 'GF-2026-00001',
      ),
      Contribution(
        id: 2,
        type: ContributionType.fraisAdhesion,
        montant: 10000,
        statut: ContributionStatus.valide,
        date: now.subtract(const Duration(days: 60)),
        reference: 'GF-2026-00002',
      ),
      Contribution(
        id: 3,
        type: ContributionType.fraisCarnet,
        montant: 1000,
        statut: ContributionStatus.valide,
        date: now.subtract(const Duration(days: 55)),
        reference: 'GF-2026-00003',
      ),
      Contribution(
        id: 4,
        type: ContributionType.fraisDemandeCredit,
        montant: 5000,
        statut: ContributionStatus.enAttente,
        date: now.subtract(const Duration(days: 2)),
        reference: 'GF-2026-00004',
      ),
    ];
  }
}
