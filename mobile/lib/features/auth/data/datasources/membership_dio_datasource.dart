import 'package:dio/dio.dart';

import '../../../../core/network/api_client.dart';
import '../../../../core/network/api_config.dart';
import '../../../../core/network/api_exceptions.dart';
import '../../../forms/domain/entities/form_schema.dart';

/// Source distante pour la demande d'adhésion publique (sans auth).
///
/// Endpoints :
///   - GET  /api/v1/forms/schemas/adhesion/active/ → schema dynamique
///   - GET  /api/forms/captcha/                    → challenge math signé
///   - POST /api/forms/adhesion/                   → soumission de la demande
///
/// Note : l'endpoint de soumission n'est PAS sous `/api/v1/`. On utilise
/// donc une URL absolue pour court-circuiter le baseUrl du client Dio.
class MembershipDioDataSource {
  MembershipDioDataSource(this._client);

  final ApiClient _client;
  Dio get _dio => _client.dio;

  /// CH-5 — Schéma actif du formulaire d'adhésion (peut être null si admin
  /// n'a pas défini de version active → mode legacy hardcoded uniquement).
  Future<FormSchema?> getActiveAdhesionSchema() async {
    try {
      final res = await _dio.get<Map<String, dynamic>>(
        '/forms/schemas/adhesion/active/',
      );
      final data = res.data;
      if (data == null) return null;
      return _parseFormSchema(data);
    } on DioException catch (e) {
      if (e.response?.statusCode == 404) return null;
      throw mapDioError(e);
    }
  }

  /// URL absolue de l'endpoint CMS forms : `{baseUrl}/api/forms/...`. Le client
  /// Dio est configuré avec `baseUrl = .../api/v1/`, donc on contourne en
  /// passant l'URL absolue directement.
  String _formsRoot(String path) => '${ApiConfig.baseUrl}/api/forms$path';

  /// Récupère un challenge math signé : `{question: "3 + 4", token: "..."}`.
  /// Le sheet calcule la réponse automatiquement (anti-spam invisible côté
  /// mobile, où l'app est déjà installée — pas besoin d'imposer une saisie).
  Future<MembershipCaptchaChallenge> getCaptcha() async {
    try {
      final res = await _dio.get<Map<String, dynamic>>(_formsRoot('/captcha/'));
      final data = res.data ?? const {};
      return MembershipCaptchaChallenge(
        question: (data['question'] as String?) ?? '',
        token: (data['token'] as String?) ?? '',
      );
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }

  /// Soumet la demande d'adhésion avec captcha déjà résolu.
  /// Retourne `null` en succès, un message d'erreur sinon.
  Future<String?> submit({
    required Map<String, Object?> body,
  }) async {
    try {
      await _dio.post<Map<String, dynamic>>(
        _formsRoot('/adhesion/'),
        data: body,
      );
      return null;
    } on DioException catch (e) {
      final status = e.response?.statusCode;
      if (status == 400) {
        final data = e.response?.data;
        if (data is Map<String, dynamic>) {
          for (final entry in data.entries) {
            final v = entry.value;
            if (v is List && v.isNotEmpty) return v.first.toString();
            if (v is String && v.isNotEmpty) return v;
          }
        }
        return 'Demande refusée — vérifie les informations saisies.';
      }
      throw mapDioError(e);
    }
  }
}

class MembershipCaptchaChallenge {
  const MembershipCaptchaChallenge({
    required this.question,
    required this.token,
  });

  final String question;
  final String token;

  /// Tente de résoudre une expression "a + b" (le seul format émis par
  /// `apps_cms.forms.captcha.new_challenge`). Renvoie null si format inconnu.
  int? solve() {
    final parts = question.split('+').map((s) => s.trim()).toList();
    if (parts.length != 2) return null;
    final a = int.tryParse(parts[0]);
    final b = int.tryParse(parts[1]);
    if (a == null || b == null) return null;
    return a + b;
  }
}

// -- Parsing helpers --------------------------------------------------------

FormSchema _parseFormSchema(Map<String, dynamic> json) {
  final schemaJson = (json['schema'] as Map<String, dynamic>?) ?? const {};
  final rawSections = (schemaJson['sections'] as List<dynamic>?) ?? const [];
  return FormSchema(
    id: (json['id'] as num?)?.toInt() ?? 0,
    kind: (json['kind'] as String?) ?? 'adhesion',
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
        .map(_parseFormSchemaField)
        .toList(growable: false),
  );
}

FormSchemaField _parseFormSchemaField(Map<String, dynamic> json) {
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
            ))
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
