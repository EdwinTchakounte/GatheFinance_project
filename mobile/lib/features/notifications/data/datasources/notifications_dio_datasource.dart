import 'package:dio/dio.dart';

import '../../../../core/network/api_client.dart';
import '../../../../core/network/api_exceptions.dart';
import '../../domain/entities/app_notification.dart';
import 'notifications_remote_datasource.dart';

/// Implémentation HTTP de [NotificationsRemoteDataSource].
///
///   - GET  /notifications/         → `{results: [...], unread_count: n}`
///   - POST /notifications/{id}/read/
///   - POST /notifications/read-all/
class NotificationsDioDataSource implements NotificationsRemoteDataSource {
  NotificationsDioDataSource(this._client);

  final ApiClient _client;
  Dio get _dio => _client.dio;

  @override
  Future<List<AppNotification>> list() async {
    try {
      final res = await _dio.get<Map<String, dynamic>>('/notifications/');
      final results = (res.data?['results'] as List<dynamic>?) ?? const [];
      return results
          .map((n) => _parseNotification(n as Map<String, dynamic>))
          .toList(growable: false);
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }

  @override
  Future<void> markAllRead() async {
    try {
      await _dio.post<void>('/notifications/read-all/');
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }

  @override
  Future<void> markRead(int id) async {
    try {
      await _dio.post<void>('/notifications/$id/read/');
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }

  @override
  Future<void> registerDevice(String token, {String platform = 'android'}) async {
    try {
      await _dio.post<void>(
        '/notifications/devices/register/',
        data: {'token': token, 'platform': platform},
      );
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }

  @override
  Future<void> unregisterDevice(String token) async {
    try {
      await _dio.post<void>(
        '/notifications/devices/unregister/',
        data: {'token': token},
      );
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }

  @override
  Future<Map<String, bool>> getPushPrefs() async {
    try {
      final res =
          await _dio.get<Map<String, dynamic>>('/notifications/preferences/');
      return _parsePush(res.data);
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }

  @override
  Future<Map<String, bool>> setPushPrefs(Map<String, bool> updates) async {
    try {
      final res = await _dio.post<Map<String, dynamic>>(
        '/notifications/preferences/',
        data: {'push': updates},
      );
      return _parsePush(res.data);
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }
}

Map<String, bool> _parsePush(Map<String, dynamic>? data) {
  final push = data?['push'];
  if (push is Map) {
    return {
      for (final entry in push.entries)
        entry.key.toString(): entry.value == true,
    };
  }
  return const {};
}

AppNotification _parseNotification(Map<String, dynamic> json) {
  final type = (json['type'] as String?) ?? '';
  final message = (json['message'] as String?) ?? '';
  // Backend renvoie un seul `message` — on dérive title/body :
  //   - cas général : titre = type formaté lisible, body = message complet ;
  //   - cas `type=="annonce"` : le backend prefixe le corps par le titre
  //     saisi par l'admin (broadcast), au format "TITRE\n\nCORPS" — on extrait
  //     proprement les 2 parties pour les afficher en hiérarchie naturelle.
  String title;
  String body;
  if (type == 'annonce') {
    final split = message.split(RegExp(r'\n\n+'));
    if (split.length >= 2 && split.first.trim().isNotEmpty) {
      title = split.first.trim();
      body = split.sublist(1).join('\n\n').trim();
    } else {
      title = 'Annonce';
      body = message;
    }
  } else {
    title = _titleFromType(type);
    body = message;
  }

  return AppNotification(
    id: (json['id'] as num).toInt(),
    kind: _kindFromType(type),
    title: title,
    body: body,
    createdAt: _date(json['created_at']),
    read: (json['lue'] as bool?) ?? false,
  );
}

NotifKind _kindFromType(String type) {
  if (type == 'annonce' || type.startsWith('annonce.')) {
    return NotifKind.announcement;
  }
  // lender.* couvre tranche engagee / interets percus / etc.
  if (type.startsWith('lender')) {
    return NotifKind.lender;
  }
  if (type.startsWith('savings') || type.startsWith('withdrawal')) {
    return NotifKind.savings;
  }
  // Sollicitation de garantie envoyée à l'AVALISTE désigné → doit ouvrir la
  // page « Mes mandats », pas la page crédit du demandeur. Les autres
  // `loan.avaliste_*` (accepté/refusé) partent au demandeur → restent `loan`.
  if (type == 'loan.avaliste_consent_requested') {
    return NotifKind.avaliste;
  }
  if (type.startsWith('loan') || type.startsWith('repayment')) {
    return NotifKind.loan;
  }
  if (type.startsWith('payment')) return NotifKind.payment;
  if (type.startsWith('support')) return NotifKind.support;
  return NotifKind.system;
}

// Libellés FR par type de notification. Le backend n'envoie que la clé
// technique (ex. `loan.closed`) ; le client l'affiche en français.
const Map<String, String> _kNotifTitlesFr = {
  'booklet.ordered': 'Carnet commandé',
  'campaign.created': 'Nouvelle campagne',
  'collecte.balance_swept_to_savings': 'Collecte versée sur l\'épargne',
  'collecte.eom_choice_reminder': 'Collecte : choix de fin de mois',
  'collecte.monthly_restitution': 'Restitution de collecte',
  'lender.apport_restitution': 'Restitution de votre apport',
  'lender.interest_paid': 'Intérêts de prêteur crédités',
  'lender.interest_paid_at_source': 'Intérêts de prêteur crédités',
  'lender.tranche_engaged': 'Tranche engagée',
  'lender.tranche_released': 'Tranche libérée',
  'loan.approved': 'Crédit approuvé',
  'loan.avaliste_consent_accepted': 'Avaliste : engagement accepté',
  'loan.avaliste_consent_refused': 'Avaliste : engagement refusé',
  'loan.avaliste_consent_requested': 'Demande de garantie (avaliste)',
  'loan.avaliste_gel_released': 'Garantie libérée',
  'loan.biens_seized': 'Saisie de biens',
  'loan.closed': 'Crédit soldé',
  'loan.credit_dossier_ready': 'Dossier de crédit prêt',
  'loan.disbursed': 'Crédit décaissé',
  'loan.installment_due_soon': 'Échéance à venir',
  'loan.installment_overdue': 'Échéance en retard',
  'loan.judicial_escalation_opened': 'Escalade judiciaire ouverte',
  'loan.notice': 'Information crédit',
  'loan.penalite_globale_appliquee': 'Pénalité appliquée',
  'loan.poursuite_engaged': 'Poursuite engagée',
  'loan_renewal.approved': 'Reconduction approuvée',
  'loan_renewal.rejected': 'Reconduction rejetée',
  'loan_renewal.requested': 'Reconduction demandée',
  'loan.repayment_confirmed': 'Remboursement confirmé',
  'loan_request.fees_paid': 'Frais d\'étude payés',
  'loan_request.rejected': 'Demande de crédit rejetée',
  'loan_request.submitted': 'Demande de crédit envoyée',
  'loan.savings_seized': 'Saisie sur épargne',
  'member.activated': 'Compte activé',
  'member.brc_document_uploaded': 'Justificatif BRC reçu',
  'member.brc_rejected': 'Justificatif BRC rejeté',
  'member.brc_validated': 'Justificatif BRC validé',
  'member.reinscription_confirmed': 'Réinscription confirmée',
  'member.reinscription_due': 'Réinscription à échéance',
  'member.reinscription_due_today': 'Réinscription à régler aujourd\'hui',
  'member.reinscription_due_urgent': 'Réinscription urgente',
  'member.reinscription_expired_suspended': 'Compte suspendu (réinscription)',
  'member.rejected': 'Demande d\'adhésion rejetée',
  'membership.archived_for_non_renewal': 'Adhésion archivée',
  'membership.interview_scheduled': 'Entretien programmé',
  'member.welcome': 'Bienvenue',
  'microcampaign.closed': 'Campagne clôturée',
  'placement.matured': 'Placement arrivé à terme',
  'savings.deposit_confirmed': 'Dépôt confirmé',
  'savings.interest_credited': 'Intérêts d\'épargne crédités',
  'savings.maturity_reached': 'Épargne arrivée à maturité',
  'savings.renewed': 'Épargne renouvelée',
  'withdrawal.admin_pending': 'Retrait à traiter',
  'withdrawal.approved': 'Retrait approuvé',
  'withdrawal.completed': 'Retrait effectué',
  'withdrawal.rejected': 'Retrait rejeté',
  'withdrawal.requested': 'Retrait demandé',
};

// Suffixe `payment.<action>.<type_paiement>` → libellé FR du type de paiement.
const Map<String, String> _kPaymentKindFr = {
  'epargne': 'épargne',
  'epargne_classique': 'épargne',
  'frais_inscription': 'frais d\'inscription',
  'frais_adhesion': 'frais d\'adhésion',
  'frais_demande_credit': 'frais de demande de crédit',
  'frais_reconduction': 'frais de reconduction',
  'frais_carnet': 'frais de carnet',
  'remboursement': 'remboursement',
  'decaissement': 'décaissement',
};

String _titleFromType(String type) {
  if (type.isEmpty) return 'Notification';

  // Clés paiement dynamiques : `payment.confirmed.<kind>`, `.rejected.`, `.initiated.`
  if (type.startsWith('payment.')) {
    final segs = type.split('.');
    const actions = {
      'confirmed': 'Paiement confirmé',
      'rejected': 'Paiement rejeté',
      'initiated': 'Paiement initié',
    };
    final action = segs.length > 1 ? actions[segs[1]] : null;
    final kind = segs.length > 2 ? _kPaymentKindFr[segs[2]] : null;
    if (action != null) return kind != null ? '$action — $kind' : action;
  }

  final mapped = _kNotifTitlesFr[type];
  if (mapped != null) return mapped;

  // Repli lisible (type inconnu) : dernier segment humanisé.
  final seg = type.split('.').last;
  final words = seg.split(RegExp(r'[._]'));
  return words
      .map((p) => p.isEmpty ? p : p[0].toUpperCase() + p.substring(1))
      .join(' ');
}

DateTime _date(dynamic value) {
  if (value is String && value.isNotEmpty) {
    return DateTime.tryParse(value) ?? DateTime.now();
  }
  return DateTime.now();
}
