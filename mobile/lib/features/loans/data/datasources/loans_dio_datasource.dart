import 'package:dio/dio.dart';

import '../../../../core/error/exceptions.dart';
import '../../../../core/network/api_client.dart';
import '../../../../core/network/api_exceptions.dart';
import '../../../../core/services/tara_checkout_launcher.dart';
import '../../domain/entities/eligibility.dart';
import '../../domain/entities/lender_payout.dart';
import '../../domain/entities/loan.dart';
import '../../domain/entities/loan_installment.dart';
import '../../../forms/domain/entities/form_schema.dart';
import '../../domain/entities/loan_renewal.dart';
import '../../domain/entities/loan_request.dart';
import '../../domain/entities/loan_request_submission.dart';
import 'loans_remote_datasource.dart';

// -- Top-level helpers used by the datasource -------------------------------

/// CH-5 — Désérialise un FormSchema renvoyé par
/// `GET /forms/schemas/loan_request/active/`.
FormSchema _parseFormSchema(Map<String, dynamic> json) {
  final schemaJson = (json['schema'] as Map<String, dynamic>?) ?? const {};
  final rawSections = (schemaJson['sections'] as List<dynamic>?) ?? const [];
  return FormSchema(
    id: (json['id'] as num?)?.toInt() ?? 0,
    kind: (json['kind'] as String?) ?? 'loan_request',
    version: (json['version'] as num?)?.toInt() ?? 1,
    title: (json['title'] as String?) ?? '',
    description: json['description'] as String?,
    sections: rawSections
        .whereType<Map<String, dynamic>>()
        .map(_parseSection)
        .toList(growable: false),
  );
}

FormSection _parseSection(Map<String, dynamic> json) {
  final rawFields = (json['fields'] as List<dynamic>?) ?? const [];
  return FormSection(
    id: (json['id'] as String?) ?? '',
    title: (json['title'] as String?) ?? '',
    description: json['description'] as String?,
    fields: rawFields
        .whereType<Map<String, dynamic>>()
        .map(_parseFormField)
        .toList(growable: false),
  );
}

FormSchemaField _parseFormField(Map<String, dynamic> json) {
  final rawOptions = (json['options'] as List<dynamic>?) ?? const [];
  final rawCondition = json['condition'] as Map<String, dynamic>?;
  return FormSchemaField(
    id: (json['id'] as String?) ?? '',
    type: _parseFieldType((json['type'] as String?) ?? 'text'),
    label: (json['label'] as String?) ?? '',
    required: (json['required'] as bool?) ?? false,
    placeholder: json['placeholder'] as String?,
    helpText: json['help_text'] as String?,
    maxLength: (json['max_length'] as num?)?.toInt(),
    min: json['min'] as num?,
    max: json['max'] as num?,
    accept: json['accept'] as String?,
    maxSizeMb: (json['max_size_mb'] as num?)?.toInt(),
    options: rawOptions
        .whereType<Map<String, dynamic>>()
        .map((o) => FormFieldOption(
              value: (o['value'] as Object?)?.toString() ?? '',
              label: (o['label'] as String?) ?? '',
            ),)
        .toList(growable: false),
    condition: rawCondition == null ? null : _parseCondition(rawCondition),
    isLocked: (json['is_locked'] as bool?) ?? false,
  );
}

FormFieldType _parseFieldType(String raw) {
  switch (raw) {
    case 'email':
      return FormFieldType.email;
    case 'tel':
      return FormFieldType.tel;
    case 'number':
      return FormFieldType.number;
    case 'textarea':
      return FormFieldType.textarea;
    case 'select':
      return FormFieldType.select;
    case 'radio':
      return FormFieldType.radio;
    case 'checkbox':
      return FormFieldType.checkbox;
    case 'file':
      return FormFieldType.file;
    case 'date':
      return FormFieldType.date;
    case 'text':
    default:
      return FormFieldType.text;
  }
}

FormFieldCondition _parseCondition(Map<String, dynamic> json) {
  final op = (json['operator'] as String?) ?? 'equals';
  return FormFieldCondition(
    field: (json['field'] as String?) ?? '',
    operator: switch (op) {
      'not_equals' => FormFieldConditionOperator.notEquals,
      'in' => FormFieldConditionOperator.inList,
      _ => FormFieldConditionOperator.equals,
    },
    value: json['value'],
  );
}

/// CH-7 — Désérialise le bloc `frais_a_payer` renvoyé par
/// `POST /loans/requests/`. Renvoie `null` si le bloc est absent ou
/// inexploitable (rétro-compat avec l'API pré-CH-7).
LoanRequestStudyFee? _parseStudyFee(Map<String, dynamic>? json) {
  if (json == null) return null;
  final montantRaw = json['montant'];
  if (montantRaw == null) return null;
  final montant = montantRaw is num
      ? montantRaw
      : num.tryParse(montantRaw.toString());
  if (montant == null) return null;
  return LoanRequestStudyFee(
    montant: montant,
    libelle: (json['libelle'] as String?) ?? 'Frais d\'étude du dossier',
    notice: (json['notice'] as String?) ?? '',
    nonRemboursable: (json['non_remboursable'] as bool?) ?? true,
  );
}

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
      final raw = res.data ?? const [];
      // Robustesse : on parse chaque demande INDÉPENDAMMENT. Une seule entrée au
      // JSON inattendu ne doit PAS vider toute la liste — sinon le membre ne voit
      // AUCUNE de ses demandes (dont une éventuelle demande en cours à régler) et
      // se retrouve bloqué face à un écran vide trompeur. On saute l'entrée
      // fautive et on garde le reste.
      final parsed = <LoanRequestEntity>[];
      var skipped = 0;
      for (final r in raw) {
        try {
          parsed.add(_parseRequest(r as Map<String, dynamic>));
        } catch (e) {
          skipped++;
          assert(() {
            // ignore: avoid_print
            print('[loans] myRequests: entrée ignorée (parse impossible) : $e');
            return true;
          }());
        }
      }
      assert(() {
        if (skipped > 0) {
          // ignore: avoid_print
          print('[loans] myRequests: $skipped/${raw.length} demande(s) ignorée(s)');
        }
        return true;
      }());
      return List.unmodifiable(parsed);
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
  Future<List<Loan>> myClosedLoans() async {
    try {
      final res = await _dio.get<List<dynamic>>('/loans/me/closed/');
      return (res.data ?? const [])
          .map((l) => _parseLoan(l as Map<String, dynamic>))
          .toList(growable: false);
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }

  @override
  Future<void> hideLoan(int loanId) async {
    try {
      await _dio.post<Map<String, dynamic>>('/loans/me/loans/$loanId/hide/');
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }

  @override
  Future<List<LenderPayout>> myLenderPayouts() async {
    try {
      final res =
          await _dio.get<Map<String, dynamic>>('/loans/me/lender-payouts/');
      final data = res.data ?? const {};
      final rows = (data['results'] as List<dynamic>?) ?? const [];
      return rows
          .map((r) => _parseLenderPayout(r as Map<String, dynamic>))
          .toList(growable: false);
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }

  @override
  Future<LoanRequestSubmission> submitRequest({
    required num montantDemande,
    required int dureeMois,
    required String motif,
    LoanReceiveChannel? moyenReception,
    String? recipientPhone,
    Map<String, Object?> extraValues = const {},
  }) async {
    try {
      final body = <String, dynamic>{
        'montant_demande': montantDemande,
        'duree_mois': dureeMois,
        'motif': motif,
      };
      // CH-9 — Propage le canal de réception choisi par le membre. Le backend
      // valide la cohérence (phone requis si tara_*).
      if (moyenReception != null) {
        body['moyen_reception'] = _receiveChannelToApi(moyenReception);
        if (recipientPhone != null && recipientPhone.trim().isNotEmpty) {
          body['recipient_phone'] = recipientPhone.trim();
        }
      }
      // CH-5 — Fusion des champs scalaires du FormSchema. Les champs hardcoded
      // l'emportent (sécurité contre un id de field qui collisionne par
      // accident avec une colonne métier). Le backend route le reste dans
      // `extra_payload` via `apply_form_schema`.
      for (final entry in extraValues.entries) {
        if (entry.value == null) continue;
        body.putIfAbsent(entry.key, () => entry.value);
      }
      final res = await _dio.post<Map<String, dynamic>>(
        '/loans/requests/',
        data: body,
      );
      final data = res.data ?? const {};
      // Le backend renvoie { loan_request, route, route_details, frais_a_payer }.
      final lr = data['loan_request'] as Map<String, dynamic>? ?? data;
      final request = _parseRequest(lr);
      // CH-7 — Bloc frais_a_payer : montant + libellé + notice non-remboursable.
      final feeJson = data['frais_a_payer'] as Map<String, dynamic>?;
      final studyFee = _parseStudyFee(feeJson);
      return LoanRequestSubmission(request: request, studyFee: studyFee);
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }

  @override
  Future<void> payStudyFee({
    required String phone,
    required String network,
    int? montant,
  }) async {
    try {
      // CH-7 — Le backend est AUTORITAIRE sur le montant (FeeType.DEMANDE_CREDIT)
      // et identifie la LoanRequest cible par le membre (en_attente). Le hook
      // `_hook_loan_request_fees` la promeut en `en_instruction` à validation.
      final response = await _dio.post<Map<String, dynamic>>(
        '/payments/init/',
        data: {
          'type': 'frais_demande_credit',
          'montant': montant ?? 0,
          'phone': phone,
          'network': network,
        },
      );
      LastTaraResponse.update(response.data);
      await TaraCheckoutLauncher.launchFromInitResponse(response.data);
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }

  @override
  Future<void> payStudyFeeFromSavings({required int requestId}) async {
    try {
      // Transfert interne : le backend débite l'épargne classique et crée un
      // Payment déjà VALIDE, qui déclenche le même hook que les deux autres
      // canaux. Rien à lancer côté Tara, rien à attendre.
      await _dio.post<Map<String, dynamic>>(
        '/loans/requests/$requestId/study-fee/from-savings/',
      );
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }

  @override
  Future<void> respondCounterProposal({
    required int requestId,
    required bool accept,
    String? motif,
  }) async {
    try {
      final action = accept ? 'accept' : 'refuse';
      await _dio.post<Map<String, dynamic>>(
        '/loans/me/requests/$requestId/counter-proposal/$action/',
        data: accept ? null : {'motif': motif ?? ''},
      );
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }

  @override
  Future<FormSchema?> getActiveLoanRequestSchema() async {
    try {
      final res = await _dio.get<Map<String, dynamic>>(
        '/forms/schemas/loan_request/active/',
      );
      final data = res.data;
      if (data == null) return null;
      return _parseFormSchema(data);
    } on DioException catch (e) {
      // 404 = aucun schéma actif → mode legacy. On normalise en null.
      if (e.response?.statusCode == 404) return null;
      throw mapDioError(e);
    }
  }

  @override
  Future<void> uploadLoanRequestAttachment({
    required int loanRequestId,
    required String schemaFieldId,
    required String filePath,
    required String fileName,
  }) async {
    try {
      final form = FormData.fromMap({
        'schema_field_id': schemaFieldId,
        'fichier': await MultipartFile.fromFile(
          filePath,
          filename: fileName,
        ),
      });
      await _dio.post<Map<String, dynamic>>(
        '/loans/requests/$loanRequestId/attachments/',
        data: form,
      );
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
      final response = await _dio.post<Map<String, dynamic>>(
        '/payments/init/',
        data: {
          'type': 'remboursement',
          'montant': montant,
          'phone': phone,
          'network': network,
          'loan_id': loanId,
        },
      );
      await TaraCheckoutLauncher.launchFromInitResponse(response.data);
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
      // Le backend fige désormais le montant à la demande : on le lit au lieu
      // de le recalculer côté client (l'ancienne version renvoyait 0/0, ce qui
      // rendait tout écran de paiement impossible à construire).
      return LoanRenewalEntity(
        id: (r['id'] as num).toInt(),
        loanId: (r['loan_id'] as num?)?.toInt() ?? loanId,
        comptant: comptant,
        capitalRestant: _num(r['montant_a_reconduire_snapshot']),
        interetsReconduction: _num(r['interets_dus']),
        resteAPayer: _num(r['reste_a_payer']),
        interetsPayes: r['interets_payes'] == true,
        statut: _renewalStatus((r['statut'] as String?) ?? 'demandee'),
        dateDemande: _date(r['date_demande']),
        dateDecision: r['date_decision'] != null ? _date(r['date_decision']) : null,
      );
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }

  @override
  Future<LoanRenewalEntity> payRenewalInterestFromSavings(int renewalId) async {
    try {
      final res = await _dio.post<Map<String, dynamic>>(
        '/loans/renewals/$renewalId/pay-interest-from-savings/',
      );
      final data = res.data ?? const {};
      final r = (data['renewal'] as Map<String, dynamic>?) ?? data;
      return LoanRenewalEntity(
        id: (r['id'] as num).toInt(),
        loanId: (r['loan_id'] as num?)?.toInt() ?? 0,
        comptant: r['interets_au_comptant'] == true,
        capitalRestant: _num(r['montant_a_reconduire_snapshot']),
        interetsReconduction: _num(r['interets_dus']),
        resteAPayer: _num(r['reste_a_payer']),
        interetsPayes: r['interets_payes'] == true,
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
    moyenReception: _receiveChannelFromApi(json['moyen_reception'] as String?),
    recipientPhone: (json['recipient_phone'] as String?)?.trim().isNotEmpty == true
        ? (json['recipient_phone'] as String)
        : null,
    fieldVisitOutcome: _fieldVisitOutcomeFromApi(
      json['field_visit_outcome'] as String?,
    ),
    // §6 LOT 12 . Voie d'eligibilite (BRC / avaliste / campagne).
    // Backend renvoie `voie` (liste/détail), ou `route`/`eligibility_route`
    // (réponse de création). On prend le premier disponible.
    route: _loanRoute(
      (json['voie'] as String?) ??
          (json['route'] as String?) ??
          (json['eligibility_route'] as String?),
    ),
    // Montant que l'AVALISTE doit couvrir sur ce crédit (le manque). Exposé au
    // demandeur pour qu'il connaisse l'engagement demandé à son garant.
    avalisteMontantACouvrir: json['avaliste_montant_a_couvrir'] != null
        ? _num(json['avaliste_montant_a_couvrir'])
        : null,
    // L6 — Échéance indicative d'étude (soumission + ~1 mois). Nullable pour
    // les demandes legacy sans date calculée côté backend.
    dateLimiteEtude: _dateOrNull(json['date_limite_etude']),
    // CH-7 — Frais d'étude applicables (piloté admin), pour le « payer plus tard ».
    fraisEtudeMontant: json['frais_etude_montant'] != null
        ? _num(json['frais_etude_montant'])
        : null,
    // Porte des frais 2026 — de quoi choisir le canal sans second appel.
    fraisPaye: json['frais_demande_credit_paye'] == true,
    epargneDisponibleFrais: _num(json['epargne_disponible_frais'] ?? 0),
    // Attribut BRC déclaré — informatif, couplable à toute voie.
    isBrc: json['is_brc'] == true,
  );
}

Loan _parseLoan(Map<String, dynamic> json) {
  final installments = (json['installments'] as List<dynamic>?) ?? const [];
  return Loan(
    id: (json['id'] as num).toInt(),
    numeroDossier: (json['numero_dossier'] as String?) ?? '',
    numeroOrdre: (json['numero_ordre'] as num?)?.toInt() ?? 0,
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
    dateSoumission:
        json['date_soumission'] != null ? _date(json['date_soumission']) : null,
    dateButoire:
        json['date_butoire'] != null ? _date(json['date_butoire']) : null,
    modeRetenueInterets:
        _interestModeFromApi(json['mode_retenue_interets'] as String?),
    montantDecaisseNet: json['montant_decaisse_net'] != null
        ? _num(json['montant_decaisse_net'])
        : null,
    interetsRetenusSource: json['interets_retenus_source'] != null
        ? _num(json['interets_retenus_source'])
        : null,
    apportGele: _num(json['apport_gele'] ?? 0),
    apportGeleMotif: (json['apport_gele_motif'] as String?) ?? '',
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
    case 'approuvee_provisoire':
      return LoanRequestStatus.approuveeProvisoire;
    case 'approuvee':
      return LoanRequestStatus.approuvee;
    case 'rejetee':
      return LoanRequestStatus.rejetee;
    case 'rejetee_avaliste':
      return LoanRequestStatus.rejeteeAvaliste;
    case 'rejetee_campagne':
      return LoanRequestStatus.rejeteeCampagne;
    case 'en_attente_avaliste':
      return LoanRequestStatus.enAttenteAvaliste;
    case 'en_validation_campagne':
      return LoanRequestStatus.enValidationCampagne;
    case 'en_attente_funding':
      return LoanRequestStatus.enAttenteFunding;
    case 'en_attente':
    default:
      return LoanRequestStatus.enAttente;
  }
}

LoanRoute? _loanRoute(String? raw) {
  if (raw == null || raw.isEmpty) return null;
  switch (raw) {
    case 'senior_brc':
    case 'brc':
      return LoanRoute.seniorBrc;
    case 'avaliste':
      return LoanRoute.avaliste;
    case 'campagne':
      return LoanRoute.campagne;
    case 'garantie_materielle':
      return LoanRoute.garantieMaterielle;
    default:
      return null;
  }
}

LoanReceiveChannel? _receiveChannelFromApi(String? raw) {
  if (raw == null || raw.isEmpty) return null;
  switch (raw) {
    case 'tara_om':
      return LoanReceiveChannel.taraOm;
    case 'tara_momo':
      return LoanReceiveChannel.taraMomo;
    case 'agence_especes':
      return LoanReceiveChannel.agenceEspeces;
    default:
      return null;
  }
}

String _receiveChannelToApi(LoanReceiveChannel channel) {
  switch (channel) {
    case LoanReceiveChannel.taraOm:
      return 'tara_om';
    case LoanReceiveChannel.taraMomo:
      return 'tara_momo';
    case LoanReceiveChannel.agenceEspeces:
      return 'agence_especes';
  }
}

FieldVisitOutcome? _fieldVisitOutcomeFromApi(String? raw) {
  if (raw == null || raw.isEmpty) return null;
  switch (raw) {
    case 'favorable':
      return FieldVisitOutcome.favorable;
    case 'defavorable':
      return FieldVisitOutcome.defavorable;
    case 'a_revoir':
      return FieldVisitOutcome.aRevoir;
    default:
      return null;
  }
}

LoanInterestMode _interestModeFromApi(String? raw) {
  if (raw == 'source') return LoanInterestMode.source;
  return LoanInterestMode.echeances;
}

LenderPayout _parseLenderPayout(Map<String, dynamic> json) {
  final loan = (json['loan'] as Map<String, dynamic>?) ?? const {};
  return LenderPayout(
    id: (json['id'] as num).toInt(),
    montant: _num(json['montant']),
    date: _date(json['date']),
    kind: (json['kind'] as String?) == 'at_source'
        ? LenderPayoutKind.atSource
        : LenderPayoutKind.installment,
    loanNumeroDossier: (loan['numero_dossier'] as String?) ?? '',
    loanId: (loan['id'] as num?)?.toInt() ?? 0,
    quotePart: _num(json['quote_part']),
    installmentNumero: (json['installment_numero'] as num?)?.toInt(),
  );
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

/// Comme [_date] mais renvoie `null` au lieu d'un fallback `now()` quand la
/// valeur est absente ou inexploitable (dates optionnelles type L6).
DateTime? _dateOrNull(dynamic value) {
  if (value is String && value.isNotEmpty) {
    return DateTime.tryParse(value);
  }
  return null;
}
