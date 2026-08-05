import 'entities/form_schema.dart';

/// CH-5 — Évalue la visibilité d'un champ selon sa `condition` :
///   equals     → la valeur référée doit être ==
///   not_equals → la valeur référée doit être !=
///   in         → la valeur référée doit appartenir à la liste cible
///
/// Si le champ n'a pas de `condition`, il est visible.
bool isFieldVisible(FormSchemaField field, Map<String, Object?> values) {
  final cond = field.condition;
  if (cond == null) return true;
  final ref = values[cond.field];
  switch (cond.operator) {
    case FormFieldConditionOperator.equals:
      return ref == cond.value;
    case FormFieldConditionOperator.notEquals:
      return ref != cond.value;
    case FormFieldConditionOperator.inList:
      final target = cond.value;
      return target is List && target.contains(ref);
  }
}

/// CH-5 — Validation locale d'un champ : règles `required`, longueur,
/// format e-mail/téléphone/nombre, taille max d'un fichier.
///
/// Renvoie un libellé d'erreur localisé (FR), ou `null` si valide.
/// Le caller doit avoir filtré les champs non-visibles via [isFieldVisible].
String? validateField(FormSchemaField field, Object? value) {
  // Checkbox booléen obligatoire : `false` (décoché) n'est pas « vide » au sens
  // ci-dessous — on le refuse explicitement. (Le checkbox multi tombe dans la
  // règle liste-vide.)
  if (field.type == FormFieldType.checkbox &&
      field.options.isEmpty &&
      field.required &&
      value != true) {
    return 'Ce champ est obligatoire.';
  }
  final isEmpty = value == null ||
      value == '' ||
      (value is List && value.isEmpty);
  if (field.required && isEmpty) {
    return 'Ce champ est obligatoire.';
  }
  if (isEmpty) return null;

  switch (field.type) {
    case FormFieldType.email:
      final s = value.toString();
      final re = RegExp(r'^[^@\s]+@[^@\s]+\.[^@\s]+$');
      if (!re.hasMatch(s)) return 'Adresse e-mail invalide.';
      break;
    case FormFieldType.tel:
      final digits = value.toString().replaceAll(RegExp(r'\D+'), '');
      if (digits.length < 8) return 'Numéro de téléphone trop court.';
      break;
    case FormFieldType.number:
      final n = num.tryParse(value.toString());
      if (n == null) return 'Doit être un nombre.';
      if (field.min != null && n < field.min!) {
        return 'Minimum ${field.min}.';
      }
      if (field.max != null && n > field.max!) {
        return 'Maximum ${field.max}.';
      }
      break;
    case FormFieldType.text:
    case FormFieldType.textarea:
      if (field.maxLength != null &&
          value is String &&
          value.length > field.maxLength!) {
        return 'Maximum ${field.maxLength} caractères.';
      }
      break;
    case FormFieldType.file:
      if (value is PickedFile && field.maxSizeMb != null) {
        if (value.sizeBytes > field.maxSizeMb! * 1024 * 1024) {
          return 'Fichier trop volumineux (max ${field.maxSizeMb} Mo).';
        }
      }
      break;
    case FormFieldType.select:
    case FormFieldType.radio:
    case FormFieldType.checkbox:
    case FormFieldType.date:
      break;
  }
  return null;
}

/// CH-5 — Valide tous les champs visibles d'un schéma en une passe.
/// Renvoie un map `{field.id: erreur}` vide si tout est OK.
Map<String, String> validateSchema(
  FormSchema schema,
  Map<String, Object?> values, {
  Set<String> excludeIds = const {},
}) {
  final errors = <String, String>{};
  for (final f in schema.allFields) {
    if (excludeIds.contains(f.id)) continue;
    if (!isFieldVisible(f, values)) continue;
    final err = validateField(f, values[f.id]);
    if (err != null) errors[f.id] = err;
  }
  return errors;
}

/// CH-5 — Marker pour les champs de type `file` après sélection.
///
/// Le renderer pose un [PickedFile] en valeur ; le submit code retire ces
/// entrées du body JSON et lance un upload multipart séparé à
/// `POST /loans/requests/{id}/attachments/`.
class PickedFile {
  const PickedFile({
    required this.path,
    required this.name,
    required this.sizeBytes,
  });

  final String path;
  final String name;
  final int sizeBytes;
}
