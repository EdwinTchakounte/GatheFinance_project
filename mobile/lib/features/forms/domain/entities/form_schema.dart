import 'package:flutter/foundation.dart';

/// CH-5 — Types de champs supportés par le renderer FormSchema mobile.
///
/// Miroir des types côté backend (`apps_coop/forms/models.py`) et du renderer
/// portail (`frontend/apps/portal/src/components/form-renderer.tsx`).
enum FormFieldType {
  text,
  email,
  tel,
  number,
  textarea,
  select,
  radio,
  checkbox,
  file,
  date,
}

/// Opérateurs de condition de visibilité d'un champ.
enum FormFieldConditionOperator { equals, notEquals, inList }

@immutable
class FormFieldOption {
  const FormFieldOption({required this.value, required this.label});

  /// Valeur stockée dans `extra_payload` quand l'option est sélectionnée.
  final String value;

  /// Libellé affiché à l'utilisateur.
  final String label;
}

/// Condition de visibilité : champ visible ssi la valeur du `field` référencé
/// satisfait l'opérateur avec la `value` cible.
@immutable
class FormFieldCondition {
  const FormFieldCondition({
    required this.field,
    required this.operator,
    required this.value,
  });

  final String field;
  final FormFieldConditionOperator operator;
  final Object? value;
}

@immutable
class FormSchemaField {
  const FormSchemaField({
    required this.id,
    required this.type,
    required this.label,
    this.required = false,
    this.placeholder,
    this.helpText,
    this.maxLength,
    this.min,
    this.max,
    this.accept,
    this.maxSizeMb,
    this.options = const [],
    this.condition,
    this.isLocked = false,
  });

  final String id;
  final FormFieldType type;
  final String label;
  final bool required;
  final String? placeholder;
  final String? helpText;
  final int? maxLength;
  final num? min;
  final num? max;

  /// Filtre MIME pour les champs `file` (ex: `image/*,application/pdf`).
  final String? accept;
  final int? maxSizeMb;

  /// Options pour `select` et `radio`.
  final List<FormFieldOption> options;
  final FormFieldCondition? condition;

  /// Si `true`, ce champ est câblé en dur dans le code (mappé vers une colonne).
  /// L'éditeur admin protège son `id`/`type` — le renderer mobile l'ignore
  /// (le widget hardcoded du sheet de demande s'en charge).
  final bool isLocked;
}

@immutable
class FormSection {
  const FormSection({
    required this.id,
    required this.title,
    this.description,
    this.fields = const [],
  });

  final String id;
  final String title;
  final String? description;
  final List<FormSchemaField> fields;
}

/// CH-5 — Schéma de formulaire actif servi par
/// `GET /api/v1/forms/schemas/{kind}/active/`.
///
/// `null` côté API (404) → mode legacy : on rend uniquement les champs
/// hardcoded du sheet, pas de section dynamique.
@immutable
class FormSchema {
  const FormSchema({
    required this.id,
    required this.kind,
    required this.version,
    required this.title,
    this.description,
    required this.sections,
  });

  final int id;
  final String kind;
  final int version;
  final String title;
  final String? description;
  final List<FormSection> sections;

  Iterable<FormSchemaField> get allFields sync* {
    for (final s in sections) {
      yield* s.fields;
    }
  }
}
