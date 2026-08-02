import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gathe_finance/core/network/api_client.dart';
import 'package:gathe_finance/features/forms/domain/entities/form_schema.dart';
import 'package:gathe_finance/features/loans/data/datasources/loans_dio_datasource.dart';
import 'package:gathe_finance/features/loans/domain/entities/loan.dart';
import 'package:gathe_finance/features/loans/domain/entities/loan_installment.dart';
import 'package:gathe_finance/features/loans/domain/entities/loan_renewal.dart';
import 'package:gathe_finance/features/loans/domain/entities/loan_request.dart';

import '../../../../helpers/dio_test_adapter.dart';

ApiClient _client(ScriptedAdapter adapter) {
  final dio = Dio(BaseOptions(baseUrl: 'http://test.local/api/v1'))
    ..httpClientAdapter = adapter;
  return ApiClient.forTest(dio: dio);
}

Map<String, dynamic> _loanPayload({
  int id = 1,
  String statut = 'actif',
}) {
  return {
    'id': id,
    'numero_dossier': 'GF-CR-2026-000$id',
    'montant': '500000.00',
    'taux_interet': '0.10',
    'duree_mois': 6,
    'date_decaissement': '2026-04-01',
    'date_premiere_echeance': '2026-05-01',
    'montant_total_du': '550000.00',
    'solde_restant': '300000.00',
    'statut': statut,
    'statut_display': statut,
    'installments': [
      {
        'id': 10,
        'numero_echeance': 1,
        'date_echeance': '2026-05-01',
        'montant_capital': '83333',
        'montant_interets': '8333',
        'montant_total': '91666',
        'montant_paye': '91666',
        'statut': 'payee',
        'statut_display': 'Payée',
      },
      {
        'id': 11,
        'numero_echeance': 2,
        'date_echeance': '2026-06-01',
        'montant_capital': '83333',
        'montant_interets': '8333',
        'montant_total': '91666',
        'montant_paye': '0',
        'statut': 'a_venir',
        'statut_display': 'À venir',
      },
    ],
  };
}

void main() {
  group('LoansDioDataSource — reads', () {
    test('eligibility parse motifs + plafond', () async {
      final adapter = ScriptedAdapter()
        ..on('/loans/me/eligibility/',
            method: 'GET',
            status: 200,
            body: {
              'eligible': false,
              'plafond_max': '2000000',
              'motifs_ineligibilite': ['Un crédit est déjà en cours.'],
              'solde_epargne': '50000',
              'ratio_garantie': '0.1',
            },);
      final ds = LoansDioDataSource(_client(adapter));
      final e = await ds.eligibility();
      expect(e.eligible, isFalse);
      expect(e.plafondMax, 2000000);
      expect(e.motifs, contains('Un crédit est déjà en cours.'));
    });

    test('myActiveLoans parse Loan + installments', () async {
      final adapter = ScriptedAdapter()
        ..on('/loans/me/active/',
            method: 'GET', status: 200, body: [_loanPayload()],);
      final ds = LoansDioDataSource(_client(adapter));
      final loans = await ds.myActiveLoans();
      expect(loans, hasLength(1));
      expect(loans.first.id, 1);
      expect(loans.first.statut, LoanStatus.actif);
      expect(loans.first.installments, hasLength(2));
      expect(loans.first.installments[0].statut, InstallmentStatus.payee);
      expect(loans.first.installments[1].statut, InstallmentStatus.aVenir);
    });

    test('myRequests parse status mappings', () async {
      final adapter = ScriptedAdapter()
        ..on('/loans/me/requests/',
            method: 'GET',
            status: 200,
            body: [
              {
                'id': 1,
                'montant_demande': '200000',
                'duree_mois': 6,
                'motif': 'Test',
                'statut': 'en_attente_avaliste',
                'date_soumission': '2026-06-01T08:00:00Z',
              },
              {
                'id': 2,
                'montant_demande': '100000',
                'duree_mois': 4,
                'motif': 'Test2',
                'statut': 'rejetee_campagne',
                'date_soumission': '2026-06-02T08:00:00Z',
              },
            ],);
      final ds = LoansDioDataSource(_client(adapter));
      final reqs = await ds.myRequests();
      expect(reqs, hasLength(2));
      // Refonte BRC . les sous-statuts ne sont plus agreges, le mobile
      // distingue precisement 'en attente avaliste' / 'rejetee campagne'
      // pour orienter le membre.
      expect(reqs[0].statut, LoanRequestStatus.enAttenteAvaliste);
      expect(reqs[1].statut, LoanRequestStatus.rejeteeCampagne);
    });

    // Régression #82 — une entrée malformée ne doit PAS vider toute la liste.
    // Avant la résilience (parse par item), un seul item au JSON inattendu
    // faisait échouer `.map().toList()` → le membre ne voyait AUCUNE demande,
    // dont sa demande EN_ATTENTE à régler (invisible = cul-de-sac).
    test('myRequests skips a malformed entry and keeps the valid ones (#82)',
        () async {
      final adapter = ScriptedAdapter()
        ..on('/loans/me/requests/',
            method: 'GET',
            status: 200,
            body: [
              // Entrée cassée : pas d'`id` → _parseRequest lève.
              {
                'montant_demande': '999',
                'statut': 'rejetee',
                'date_soumission': '2026-06-01T08:00:00Z',
              },
              // Demande EN_ATTENTE type #38 (senior_brc, gel, agence, BRC).
              {
                'id': 38,
                'montant_demande': '50000.00',
                'duree_mois': 2,
                'motif': 'Fonds',
                'statut': 'en_attente',
                'date_soumission': '2026-07-30T08:00:00Z',
                'voie': 'senior_brc',
                'moyen_reception': 'agence_especes',
                'montant_gele_demandeur': '10000.00',
                'frais_etude_montant': '5000.00',
                'frais_demande_credit_paye': false,
                'epargne_disponible_frais': '21000.00',
                'is_brc': true,
              },
            ],);
      final ds = LoansDioDataSource(_client(adapter));
      final reqs = await ds.myRequests();
      // L'entrée cassée est écartée, la demande #38 SURVIT et reste visible.
      expect(reqs, hasLength(1));
      expect(reqs.single.id, 38);
      expect(reqs.single.statut, LoanRequestStatus.enAttente);
      expect(reqs.single.isBrc, isTrue);
      expect(reqs.single.fraisPaye, isFalse);
    });
  });

  group('LoansDioDataSource — writes', () {
    test('submitRequest unwrap loan_request key', () async {
      final adapter = ScriptedAdapter()
        ..on('/auth/csrf/', method: 'GET', status: 200)
        ..on('/loans/requests/',
            method: 'POST',
            status: 200,
            body: {
              'loan_request': {
                'id': 42,
                'montant_demande': '150000',
                'duree_mois': 4,
                'motif': 'Test',
                'statut': 'en_attente',
                'date_soumission': '2026-06-01T08:00:00Z',
              },
              'route': 'senior_brc',
            },);
      final ds = LoansDioDataSource(_client(adapter));
      final submission = await ds.submitRequest(
        montantDemande: 150000,
        dureeMois: 4,
        motif: 'Test',
      );
      expect(submission.request.id, 42);
      expect(submission.request.statut, LoanRequestStatus.enAttente);
      // CH-7 — Sans bloc `frais_a_payer` côté backend, studyFee reste null.
      expect(submission.studyFee, isNull);
    });

    test('submitRequest parse frais_a_payer block (CH-7)', () async {
      final adapter = ScriptedAdapter()
        ..on('/auth/csrf/', method: 'GET', status: 200)
        ..on('/loans/requests/',
            method: 'POST',
            status: 200,
            body: {
              'loan_request': {
                'id': 43,
                'montant_demande': '200000',
                'duree_mois': 4,
                'motif': 'Test',
                'statut': 'en_attente',
                'date_soumission': '2026-06-01T08:00:00Z',
              },
              'frais_a_payer': {
                'code': 'DEMANDE_CREDIT',
                'libelle': 'Frais d\'étude du dossier',
                'montant': '5000',
                'non_remboursable': true,
                'notice': 'Ces frais sont non-remboursables.',
              },
            },);
      final ds = LoansDioDataSource(_client(adapter));
      final submission = await ds.submitRequest(
        montantDemande: 200000,
        dureeMois: 4,
        motif: 'Test',
      );
      expect(submission.studyFee, isNotNull);
      expect(submission.studyFee!.montant, 5000);
      expect(submission.studyFee!.nonRemboursable, isTrue);
      expect(submission.studyFee!.notice, contains('non-remboursables'));
    });

    test('payStudyFee POST /payments/init/ type=frais_demande_credit',
        () async {
      final adapter = ScriptedAdapter()
        ..on('/auth/csrf/', method: 'GET', status: 200)
        ..on('/payments/init/',
            method: 'POST',
            status: 200,
            body: {'payment': {'id': 99}},);
      final ds = LoansDioDataSource(_client(adapter));
      await ds.payStudyFee(phone: '+237699112233', network: 'mtn');
      // Pas de retour à valider — succès = pas d'exception.
    });

    test(
        'payStudyFeeFromSavings POST /loans/requests/{id}/study-fee/from-savings/',
        () async {
      // Porte des frais 2026 — 3e canal. Ne DOIT PAS passer par
      // /payments/init/ : cet endpoint force source=mobile_money et attend un
      // encaissement externe. Ici c'est un transfert interne.
      final adapter = ScriptedAdapter()
        ..on('/auth/csrf/', method: 'GET', status: 200)
        ..on('/loans/requests/42/study-fee/from-savings/',
            method: 'POST',
            status: 200,
            body: {'id': 42, 'statut': 'en_instruction'},);
      final ds = LoansDioDataSource(_client(adapter));
      await ds.payStudyFeeFromSavings(requestId: 42);
    });

    test('payStudyFeeFromSavings remonte le 409 en erreur métier', () async {
      // Le backend refuse si le retirable ne couvre pas les frais (placement
      // et épargne gelée en garantie non ponctionnables). Le message doit
      // remonter au membre, pas être avalé.
      final adapter = ScriptedAdapter()
        ..on('/auth/csrf/', method: 'GET', status: 200)
        ..on('/loans/requests/42/study-fee/from-savings/',
            method: 'POST',
            status: 409,
            body: {'detail': 'Épargne disponible insuffisante : 1000 XAF.'},);
      final ds = LoansDioDataSource(_client(adapter));
      expect(
        () => ds.payStudyFeeFromSavings(requestId: 42),
        throwsA(isA<Object>()),
      );
    });

    test('submitRequest fusionne extraValues dans le body (CH-5)', () async {
      final adapter = ScriptedAdapter()
        ..on('/auth/csrf/', method: 'GET', status: 200)
        ..on('/loans/requests/',
            method: 'POST',
            status: 200,
            body: {
              'loan_request': {
                'id': 44,
                'montant_demande': '120000',
                'duree_mois': 3,
                'motif': 'Test',
                'statut': 'en_attente',
                'date_soumission': '2026-06-13T08:00:00Z',
              },
              'route': 'senior_brc',
            },);
      final ds = LoansDioDataSource(_client(adapter));
      await ds.submitRequest(
        montantDemande: 120000,
        dureeMois: 3,
        motif: 'Test',
        extraValues: const {
          'nom_complet': 'Jean Mballa',
          'statut_pro': 'independant',
        },
      );
      final init = adapter.recorded
          .firstWhere((r) => r.path.contains('/loans/requests/'));
      expect(init.body, contains('"nom_complet":"Jean Mballa"'));
      expect(init.body, contains('"statut_pro":"independant"'));
    });

    test(
        'getActiveLoanRequestSchema parse sections + champs typés (CH-5)',
        () async {
      final adapter = ScriptedAdapter()
        ..on('/forms/schemas/loan_request/active/',
            method: 'GET',
            status: 200,
            body: {
              'id': 7,
              'kind': 'loan_request',
              'version': 3,
              'title': 'Demande de crédit',
              'description': 'Renseignez votre dossier',
              'schema': {
                'sections': [
                  {
                    'id': 'identity',
                    'title': 'Identité',
                    'fields': [
                      {
                        'id': 'nom_complet',
                        'type': 'text',
                        'label': 'Nom complet',
                        'required': true,
                        'max_length': 120,
                      },
                      {
                        'id': 'statut_pro',
                        'type': 'select',
                        'label': 'Statut',
                        'options': [
                          {'value': 'salarie', 'label': 'Salarié'},
                          {'value': 'indep', 'label': 'Indépendant'},
                        ],
                      },
                      {
                        'id': 'carte_cga',
                        'type': 'file',
                        'label': 'Carte CGA',
                        'accept': 'image/*,application/pdf',
                        'max_size_mb': 5,
                        'condition': {
                          'field': 'statut_pro',
                          'operator': 'equals',
                          'value': 'indep',
                        },
                      },
                    ],
                  },
                ],
              },
            },);
      final ds = LoansDioDataSource(_client(adapter));
      final schema = await ds.getActiveLoanRequestSchema();
      expect(schema, isNotNull);
      expect(schema!.kind, 'loan_request');
      expect(schema.version, 3);
      expect(schema.sections, hasLength(1));
      final fields = schema.sections.first.fields;
      expect(fields, hasLength(3));
      expect(fields[0].type, FormFieldType.text);
      expect(fields[0].required, isTrue);
      expect(fields[0].maxLength, 120);
      expect(fields[1].type, FormFieldType.select);
      expect(fields[1].options.map((o) => o.value), ['salarie', 'indep']);
      expect(fields[2].type, FormFieldType.file);
      expect(fields[2].maxSizeMb, 5);
      expect(fields[2].condition!.operator, FormFieldConditionOperator.equals);
      expect(fields[2].condition!.value, 'indep');
    });

    test('getActiveLoanRequestSchema renvoie null sur 404 (legacy)',
        () async {
      final adapter = ScriptedAdapter()
        ..on('/forms/schemas/loan_request/active/',
            method: 'GET',
            status: 404,
            body: {'detail': 'Aucun schéma actif.'},);
      final ds = LoansDioDataSource(_client(adapter));
      final schema = await ds.getActiveLoanRequestSchema();
      expect(schema, isNull);
    });

    test('repay POST /payments/init/ type=remboursement + loan_id', () async {
      final adapter = ScriptedAdapter()
        ..on('/auth/csrf/', method: 'GET', status: 200)
        ..on('/payments/init/',
            method: 'POST',
            status: 200,
            body: {'payment': {'id': 1}},)
        ..on('/loans/me/active/',
            method: 'GET', status: 200, body: [_loanPayload(id: 7)],);
      final ds = LoansDioDataSource(_client(adapter));
      await ds.repay(
        loanId: 7,
        montant: 10000,
        phone: '+237699112233',
        network: 'MTN',
      );
      final init = adapter.recorded
          .firstWhere((r) => r.path.contains('/payments/init/'));
      expect(init.body, contains('"type":"remboursement"'));
      expect(init.body, contains('"loan_id":7'));
    });

    test('requestRenewal envoie interets_au_comptant', () async {
      final adapter = ScriptedAdapter()
        ..on('/auth/csrf/', method: 'GET', status: 200)
        ..on('/loans/7/renewal/',
            method: 'POST',
            status: 200,
            body: {
              'renewal': {
                'id': 1,
                'loan_id': 7,
                'nouvelle_duree_mois': 7,
                'statut': 'demandee',
                'date_demande': '2026-06-01T08:00:00Z',
                'frais_reconduction_payment_id': null,
              },
            },);
      final ds = LoansDioDataSource(_client(adapter));
      final r = await ds.requestRenewal(loanId: 7, comptant: true);
      expect(r.statut, LoanRenewalStatus.demandee);
      expect(r.loanId, 7);
      expect(r.comptant, isTrue);
      final post = adapter.recorded
          .firstWhere((req) => req.path.contains('renewal'));
      expect(post.body, contains('"interets_au_comptant":true'));
    });
  });
}
