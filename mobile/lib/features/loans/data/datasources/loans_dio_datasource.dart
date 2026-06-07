import 'package:dio/dio.dart';

import '../../../../core/error/exceptions.dart';
import '../../../../core/network/api_client.dart';
import '../../../../core/network/api_exceptions.dart';
import '../../domain/entities/eligibility.dart';
import '../../domain/entities/loan.dart';
import '../../domain/entities/loan_installment.dart';
import '../../domain/entities/loan_renewal.dart';
import '../../domain/entities/loan_request.dart';
import 'loans_remote_datasource.dart';

/// Implémentation HTTP de [LoansRemoteDataSource].
///
/// Mappage des endpoints :
///   - GET  /loans/me/eligibility/   → [eligibility]
///   - GET  /loans/me/requests/      → [myRequests]
///   - GET  /loans/me/active/        → [myActiveLoans]
///   - POST /loans/requests/         → [submitRequest]
///   - POST /loans/{id}/renewal/     → [requestRenewal]
///   - POST /payments/init/ + GET    → [repay] (remboursement = paiement async)
class LoansDioDataSource implements LoansRemoteDataSource {
  LoansDioDataSource(this._client);

  final ApiClient _client;
  Dio get _dio => _client.dio;

  @override
  Future<Eligibility> eligibility() async {
    try {
      final res = await _dio.get<Map<String, dynamic>>('/loans/me/eligibility/');
      final data = res.data ?? const {};
      return Eligibility(
        eligible: (data['eligible'] as bool?) ?? false,
        plafondMax: _num(data['plafond_max']),
        soldeEpargne: _num(data['solde_epargne']),
        ratioGarantie: _num(data['ratio_garantie']),
        motifs: ((data['motifs_ineligibilite'] as List<dynamic>?) ?? const [])
            .map((m) => m.toString())
            .toList(growable: false),
      );
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }

  @override
  Future<List<LoanRequestEntity>> myRequests() async {
    try {
      final res = await _dio.get<List<dynamic>>('/loans/me/requests/');
      return (res.data ?? const [])
          .map((r) => _parseRequest(r as Map<String, dynamic>))
          .toList(growable: false);
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }

  @override
  Future<List<Loan>> myActiveLoans() async {
    try {
      final res = await _dio.get<List<dynamic>>('/loans/me/active/');
      return (res.data ?? const [])
          .map((l) => _parseLoan(l as Map<String, dynamic>))
          .toList(growable: false);
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }

  @override
  Future<LoanRequestEntity> submitRequest({
    required num montantDemande,
    required int dureeMois,
    required String motif,
  }) async {
    try {
      final res = await _dio.post<Map<String, dynamic>>(
        '/loans/requests/',
        data: {
          'montant_demande': montantDemande,
          'duree_mois': dureeMois,
          'motif': motif,
        },
      );
      final data = res.data ?? const {};
      // Le backend renvoie { loan_request, route, route_details, frais_a_payer }.
      // On ne projète QUE le LoanRequest dans l'entité — l'UI consultera la
      // route via un appel séparé si besoin (LOT 18 avaliste / LOT 19 campaign).
      final lr = data['loan_request'] as Map<String, dynamic>? ?? data;
      return _parseRequest(lr);
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }

  @override
  Future<Loan> repay({
    required int loanId,
    required num montant,
    required String phone,
    required String network,
  }) async {
    try {
      await _dio.post<Map<String, dynamic>>(
        '/payments/init/',
        data: {
          'type': 'remboursement',
          'montant': montant,
          'phone': phone,
          'network': network,
          'loan_id': loanId,
        },
      );
      // Le webhook valide le paiement plus tard. On renvoie le snapshot
      // actuel du crédit — l'UI doit poller pour voir l'imputation FIFO.
      final loans = await myActiveLoans();
      return loans.firstWhere(
        (l) => l.id == loanId,
        orElse: () => throw const ServerException('Crédit introuvable', 404),
      );
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }

  @override
  Future<LoanRenewalEntity> requestRenewal({
    required int loanId,
    required bool comptant,
  }) async {
    try {
      final res = await _dio.post<Map<String, dynamic>>(
        '/loans/$loanId/renewal/',
        data: {'interets_au_comptant': comptant},
      );
      final data = res.data ?? const {};
      // Le backend renvoie { renewal: {...} }.
      final r = (data['renewal'] as Map<String, dynamic>?) ?? data;
      // capitalRestant / interetsReconduction ne sont pas dans la réponse
      // backend (calculés côté serveur, stockés ailleurs). L'UI les
      // recalculera à partir du Loan via loan_terms.dart.
      return LoanRenewalEntity(
        id: (r['id'] as num).toInt(),
        loanId: (r['loan_id'] as num?)?.toInt() ?? loanId,
        comptant: comptant,
        capitalRestant: 0,
        interetsReconduction: 0,
        statut: _renewalStatus((r['statut'] as String?) ?? 'demandee'),
        dateDemande: _date(r['date_demande']),
        dateDecision: r['date_decision'] != null ? _date(r['date_decision']) : null,
      );
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }
}

// -- Parsing helpers --------------------------------------------------------

LoanRequestEntity _parseRequest(Map<String, dynamic> json) {
  return LoanRequestEntity(
    id: (json['id'] as num).toInt(),
    montantDemande: _num(json['montant_demande']),
    dureeMois: (json['duree_mois'] as num?)?.toInt() ?? 0,
    motif: (json['motif'] as String?) ?? '',
    statut: _requestStatus((json['statut'] as String?) ?? 'en_attente'),
    dateSoumission: _date(json['date_soumission']),
    dateDecision: json['date_decision'] != null ? _date(json['date_decision']) : null,
    motifRejet: (json['motif_rejet'] as String?) ?? '',
    montantRevise: json['montant_revise'] != null ? _num(json['montant_revise']) : null,
    dureeRevisee: (json['duree_revisee'] as num?)?.toInt(),
  );
}

Loan _parseLoan(Map<String, dynamic> json) {
  final installments = (json['installments'] as List<dynamic>?) ?? const [];
  return Loan(
    id: (json['id'] as num).toInt(),
    numeroDossier: (json['numero_dossier'] as String?) ?? '',
    montant: _num(json['montant']),
    tauxInteret: _num(json['taux_interet']),
    dureeMois: (json['duree_mois'] as num?)?.toInt() ?? 0,
    dateDecaissement: _date(json['date_decaissement']),
    datePremiereEcheance: _date(json['date_premiere_echeance']),
    montantTotalDu: _num(json['montant_total_du']),
    soldeRestant: _num(json['solde_restant']),
    statut: _loanStatus((json['statut'] as String?) ?? 'actif'),
    installments: installments
        .map((i) => _parseInstallment(i as Map<String, dynamic>))
        .toList(growable: false),
  );
}

LoanInstallment _parseInstallment(Map<String, dynamic> json) {
  return LoanInstallment(
    id: (json['id'] as num).toInt(),
    numero: (json['numero_echeance'] as num?)?.toInt() ?? 0,
    dateEcheance: _date(json['date_echeance']),
    montantCapital: _num(json['montant_capital']),
    montantInterets: _num(json['montant_interets']),
    montantTotal: _num(json['montant_total']),
    montantPaye: _num(json['montant_paye']),
    statut: _installmentStatus((json['statut'] as String?) ?? 'a_venir'),
  );
}

LoanStatus _loanStatus(String raw) {
  switch (raw) {
    case 'en_retard':
      return LoanStatus.enRetard;
    case 'cloture':
      return LoanStatus.cloture;
    case 'contentieux':
      return LoanStatus.contentieux;
    case 'actif':
    default:
      return LoanStatus.actif;
  }
}

InstallmentStatus _installmentStatus(String raw) {
  switch (raw) {
    case 'payee':
      return InstallmentStatus.payee;
    case 'en_retard':
      return InstallmentStatus.enRetard;
    case 'partielle':
      return InstallmentStatus.partielle;
    case 'a_venir':
    default:
      return InstallmentStatus.aVenir;
  }
}

LoanRequestStatus _requestStatus(String raw) {
  switch (raw) {
    case 'en_instruction':
      return LoanRequestStatus.enInstruction;
    case 'en_attente_acceptation_membre':
      return LoanRequestStatus.enAttenteAcceptationMembre;
    case 'approuvee':
      return LoanRequestStatus.approuvee;
    case 'rejetee':
    case 'rejetee_avaliste':
    case 'rejetee_campagne':
      return LoanRequestStatus.rejetee;
    case 'en_attente':
    case 'en_attente_avaliste':
    case 'en_validation_campagne':
    default:
      return LoanRequestStatus.enAttente;
  }
}

LoanRenewalStatus _renewalStatus(String raw) {
  switch (raw) {
    case 'approuvee':
      return LoanRenewalStatus.approuvee;
    case 'rejetee':
      return LoanRenewalStatus.rejetee;
    case 'demandee':
    default:
      return LoanRenewalStatus.demandee;
  }
}

num _num(dynamic value) {
  if (value is num) return value;
  if (value is String) return num.tryParse(value) ?? 0;
  return 0;
}

DateTime _date(dynamic value) {
  if (value is String && value.isNotEmpty) {
    return DateTime.tryParse(value) ?? DateTime.now();
  }
  return DateTime.now();
}
