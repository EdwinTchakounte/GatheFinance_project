import '../../../../core/error/exceptions.dart';
import '../../domain/entities/eligibility.dart';
import '../../domain/entities/loan.dart';
import '../../domain/entities/loan_installment.dart';
import '../../domain/entities/loan_renewal.dart';
import '../../domain/entities/loan_request.dart';
import '../../domain/loan_terms.dart';
import 'loans_remote_datasource.dart';

/// État mémoire pour tout le domaine crédit. Tous les writes mutent ces
/// listes ; les fetchs renvoient un snapshot. Le jour du switch vers Dio,
/// ce fichier disparaît au profit de `loans_dio_datasource.dart`.
class LoansMockDataSource implements LoansRemoteDataSource {
  LoansMockDataSource() {
    _seed();
  }

  late List<Loan> _activeLoans;
  final List<LoanRequestEntity> _requests = [];
  final List<LoanRenewalEntity> _renewals = [];
  int _nextRequestId = 100;
  int _nextRenewalId = 200;

  void _seed() {
    // Crédit conforme au Règlement (Articles 5, 7, 8) :
    //   montant 300 000 → palier 201k-350k → 4 mois (Art. 7)
    //   taux 10 % flat → intérêts 30 000, total dû 330 000 (Art. 5)
    //   modalité mensuelle → 4 échéances de 82 500 (75 000 capital + 7 500 int.)
    const montant = 300000;
    final bd = computeLoanBreakdown(montant);
    final today = DateTime.now();
    // 1re échéance il y a ~23 jours (déjà payée), décaissement il y a ~30 j.
    final premiereEcheance = today.subtract(const Duration(days: 23));

    final installments = <LoanInstallment>[];
    num capitalCum = 0;
    num interetsCum = 0;
    for (var i = 0; i < bd.nbEcheances; i++) {
      final n = i + 1;
      final isLast = n == bd.nbEcheances;
      final capital = isLast
          ? (bd.montant - capitalCum)
          : bd.capitalParEcheance.roundToDouble();
      final interets = isLast
          ? (bd.interetsTotaux - interetsCum)
          : bd.interetsParEcheance.roundToDouble();
      capitalCum += capital;
      interetsCum += interets;
      final total = capital + interets;
      final isPaid = n == 1; // 1re échéance réglée
      installments.add(LoanInstallment(
        id: n,
        numero: n,
        // mensuel → +1 mois par échéance
        dateEcheance: DateTime(
          premiereEcheance.year,
          premiereEcheance.month + i,
          premiereEcheance.day,
        ),
        montantCapital: capital,
        montantInterets: interets,
        montantTotal: total,
        montantPaye: isPaid ? total : 0,
        statut: isPaid ? InstallmentStatus.payee : InstallmentStatus.aVenir,
      ));
    }
    final dejaPaye = installments
        .where((i) => i.statut == InstallmentStatus.payee)
        .fold<num>(0, (s, i) => s + i.montantTotal);

    _activeLoans = [
      Loan(
        id: 1,
        numeroDossier: 'GF-CR-2026-0001',
        montant: montant,
        tauxInteret: kLoanInterestRate, // 0.10 flat (Art. 5)
        dureeMois: bd.dureeMois,
        dateDecaissement: today.subtract(const Duration(days: 30)),
        datePremiereEcheance: premiereEcheance,
        montantTotalDu: bd.montantTotalDu,
        soldeRestant: bd.montantTotalDu - dejaPaye,
        statut: LoanStatus.actif,
        installments: installments,
      ),
    ];
  }

  // -- Reads ----------------------------------------------------------------

  @override
  Future<List<Loan>> myActiveLoans() async {
    await Future<void>.delayed(const Duration(milliseconds: 400));
    return List.unmodifiable(_activeLoans);
  }

  @override
  Future<List<LoanRequestEntity>> myRequests() async {
    await Future<void>.delayed(const Duration(milliseconds: 300));
    return List.unmodifiable(_requests);
  }

  @override
  Future<Eligibility> eligibility() async {
    await Future<void>.delayed(const Duration(milliseconds: 250));
    // Le Règlement ne plafonne PAS le crédit par l'épargne (pas de ratio×10).
    // L'octroi est à l'appréciation du comité (Art. 6). On expose seulement
    // les blocages durs : crédit déjà actif, demande déjà en cours.
    const soldeEpargne = 48500; // aligné sur le seed épargne
    final hasActive = _activeLoans.any((l) =>
        l.statut == LoanStatus.actif || l.statut == LoanStatus.enRetard);
    final hasPendingReq = _requests.any((r) =>
        r.statut == LoanRequestStatus.enAttente ||
        r.statut == LoanRequestStatus.enInstruction);
    final motifs = <String>[];
    if (hasActive) motifs.add('Un crédit est déjà en cours.');
    if (hasPendingReq) motifs.add('Une demande est déjà en instruction.');
    return Eligibility(
      eligible: motifs.isEmpty,
      // Plafond = dernier palier du règlement (≥ 951 000 → 9 mois). Au-delà,
      // décision comité. Pas de cap basé sur l'épargne.
      plafondMax: 2000000,
      soldeEpargne: soldeEpargne,
      ratioGarantie: 0, // pas de ratio garantie dans le règlement
      motifs: motifs,
    );
  }

  // -- Writes ---------------------------------------------------------------

  @override
  Future<LoanRequestEntity> submitRequest({
    required num montantDemande,
    required int dureeMois,
    required String motif,
    LoanReceiveChannel? moyenReception,
    String? recipientPhone,
  }) async {
    await Future<void>.delayed(const Duration(milliseconds: 600));
    final req = LoanRequestEntity(
      id: _nextRequestId++,
      montantDemande: montantDemande,
      dureeMois: dureeMois,
      motif: motif,
      statut: LoanRequestStatus.enAttente, // frais à payer
      dateSoumission: DateTime.now(),
      moyenReception: moyenReception,
      recipientPhone: recipientPhone,
    );
    _requests.insert(0, req);
    return req;
  }

  @override
  Future<Loan> repay({
    required int loanId,
    required num montant,
    required String phone,
    required String network,
  }) async {
    // Simule la latence Tara + le webhook qui valide
    await Future<void>.delayed(const Duration(milliseconds: 1700));
    final idx = _activeLoans.indexWhere((l) => l.id == loanId);
    if (idx < 0) {
      throw const ServerException('Crédit introuvable', 404);
    }
    final loan = _activeLoans[idx];

    // Imputation FIFO simple sur les échéances non payées
    num reste = montant;
    final updatedInstallments = <LoanInstallment>[];
    var anyChanged = false;
    for (final inst in loan.installments) {
      if (reste <= 0 || inst.statut == InstallmentStatus.payee) {
        updatedInstallments.add(inst);
        continue;
      }
      final du = inst.montantTotal - inst.montantPaye;
      final impute = reste >= du ? du : reste;
      final newPaye = inst.montantPaye + impute;
      final newStatut = newPaye >= inst.montantTotal
          ? InstallmentStatus.payee
          : InstallmentStatus.partielle;
      updatedInstallments.add(LoanInstallment(
        id: inst.id,
        numero: inst.numero,
        dateEcheance: inst.dateEcheance,
        montantCapital: inst.montantCapital,
        montantInterets: inst.montantInterets,
        montantTotal: inst.montantTotal,
        montantPaye: newPaye,
        statut: newStatut,
      ));
      reste -= impute;
      anyChanged = true;
    }
    if (!anyChanged) {
      throw const ServerException('Aucune échéance à imputer', 400);
    }

    final imputeTotal = montant - reste;
    final newSolde = (loan.soldeRestant - imputeTotal).clamp(0, double.infinity);
    final allPaid = updatedInstallments.every(
      (i) => i.statut == InstallmentStatus.payee,
    );
    final updated = Loan(
      id: loan.id,
      numeroDossier: loan.numeroDossier,
      montant: loan.montant,
      tauxInteret: loan.tauxInteret,
      dureeMois: loan.dureeMois,
      dateDecaissement: loan.dateDecaissement,
      datePremiereEcheance: loan.datePremiereEcheance,
      montantTotalDu: loan.montantTotalDu,
      soldeRestant: newSolde,
      statut: allPaid ? LoanStatus.cloture : loan.statut,
      installments: updatedInstallments,
    );
    if (allPaid) {
      _activeLoans.removeAt(idx);
    } else {
      _activeLoans[idx] = updated;
    }
    return updated;
  }

  @override
  Future<LoanRenewalEntity> requestRenewal({
    required int loanId,
    required bool comptant,
  }) async {
    await Future<void>.delayed(const Duration(milliseconds: 500));
    final loan = _activeLoans.firstWhere(
      (l) => l.id == loanId,
      orElse: () => throw const ServerException('Crédit introuvable', 404),
    );
    // Article 11 : une seule reconduction par crédit, bloquée même à la
    // soumission. On rejette si le crédit est déjà marqué reconduit OU si une
    // demande non rejetée existe déjà.
    final dejaReconduit = loan.dejaReconduit ||
        _renewals.any((r) =>
            r.loanId == loan.id && r.statut != LoanRenewalStatus.rejetee);
    if (dejaReconduit) {
      throw const ServerException(
        'Ce crédit a déjà fait l’objet d’une reconduction. '
        'Une seule reconduction est autorisée par crédit (Article 11).',
        409,
      );
    }
    // Article 11 : intérêts = taux × capital restant (pas d'intérêt sur
    // intérêt). 10 % au comptant, 15 % si reportés.
    final capitalRestant = loan.capitalRestant;
    final interets = renewalInterest(capitalRestant, comptant: comptant);
    final renewal = LoanRenewalEntity(
      id: _nextRenewalId++,
      loanId: loan.id,
      comptant: comptant,
      capitalRestant: capitalRestant,
      interetsReconduction: interets,
      statut: LoanRenewalStatus.demandee,
      dateDemande: DateTime.now(),
    );
    _renewals.insert(0, renewal);
    return renewal;
  }
}
