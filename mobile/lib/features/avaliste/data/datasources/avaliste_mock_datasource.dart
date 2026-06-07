import '../../../../core/error/exceptions.dart';
import '../../domain/entities/avaliste_mandat.dart';
import 'avaliste_remote_datasource.dart';

/// Mock — 2 mandats : 1 pending, 1 accepted. Permet de tester l'UI sans
/// backend. Le `respond()` mute l'item en mémoire.
class AvalisteMockDataSource implements AvalisteRemoteDataSource {
  final List<AvalisteMandat> _store = [
    AvalisteMandat(
      id: 1,
      statut: AvalisteStatut.pending,
      statutDisplay: 'En attente',
      respondedAt: null,
      refusMotif: '',
      createdAt: DateTime.now().subtract(const Duration(hours: 12)),
      demandeur: const AvalisteDemandeur(
        id: 42,
        numeroMembre: 'GF-2026-0042',
        prenom: 'Awa',
        nom: 'Sow',
      ),
      loanRequest: AvalisteLoanRequest(
        id: 101,
        montantDemande: 250000,
        dureeMois: 6,
        motif: 'Achat matériel commerce',
        statut: 'en_attente_avaliste',
        dateSoumission: DateTime.now().subtract(const Duration(hours: 12)),
      ),
      couverture: const AvalisteCouverture(
        epargneBorrower: 50000,
        epargneAvaliste: 300000,
        ratio: 1.2,
      ),
    ),
    AvalisteMandat(
      id: 2,
      statut: AvalisteStatut.accepted,
      statutDisplay: 'Accepté',
      respondedAt: DateTime.now().subtract(const Duration(days: 6)),
      refusMotif: '',
      createdAt: DateTime.now().subtract(const Duration(days: 8)),
      demandeur: const AvalisteDemandeur(
        id: 73,
        numeroMembre: 'GF-2026-0073',
        prenom: 'Marc',
        nom: 'Talla',
      ),
      loanRequest: AvalisteLoanRequest(
        id: 88,
        montantDemande: 150000,
        dureeMois: 4,
        motif: 'Travaux logement',
        statut: 'approuvee',
        dateSoumission: DateTime.now().subtract(const Duration(days: 8)),
      ),
      couverture: const AvalisteCouverture(
        epargneBorrower: 35000,
        epargneAvaliste: 200000,
        ratio: 1.33,
      ),
    ),
  ];

  @override
  Future<AvalisteMandatList> list({AvalisteStatut? statut}) async {
    await Future<void>.delayed(const Duration(milliseconds: 380));
    final items = statut == null
        ? _store
        : _store.where((m) => m.statut == statut).toList();
    final pending =
        _store.where((m) => m.statut == AvalisteStatut.pending).length;
    return AvalisteMandatList(
      items: List.unmodifiable(items),
      pendingCount: pending,
    );
  }

  @override
  Future<AvalisteMandat> respond({
    required int mandatId,
    required bool accept,
    String? motif,
  }) async {
    await Future<void>.delayed(const Duration(milliseconds: 600));
    final idx = _store.indexWhere((m) => m.id == mandatId);
    if (idx < 0) {
      throw const ServerException('Mandat introuvable', 404);
    }
    final current = _store[idx];
    if (!current.isPending) {
      throw const ServerException(
        'Ce mandat a déjà reçu une réponse.',
        409,
      );
    }
    final updated = AvalisteMandat(
      id: current.id,
      statut: accept ? AvalisteStatut.accepted : AvalisteStatut.refused,
      statutDisplay: accept ? 'Accepté' : 'Refusé',
      respondedAt: DateTime.now(),
      refusMotif: accept ? '' : (motif?.trim() ?? ''),
      createdAt: current.createdAt,
      demandeur: current.demandeur,
      loanRequest: current.loanRequest,
      couverture: current.couverture,
    );
    _store[idx] = updated;
    return updated;
  }
}
