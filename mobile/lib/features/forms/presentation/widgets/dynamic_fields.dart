import 'dart:io';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';

import '../../../../app/theme/paysika/pa_colors.dart';
import '../../domain/entities/form_schema.dart';
import '../../domain/form_validation.dart';

/// CH-5 . Renderer générique de FormSchema pour mobile.
///
/// Pattern miroir du renderer portail (`DynamicFields` React) :
/// - controlled : le parent détient `values` + reçoit `onChange`
/// - filtre les champs `excludeIds` (typiquement les hardcoded du sheet)
/// - les valeurs des champs masqués par condition restent dans `values` mais
///   le caller doit les filtrer avant submit via `isFieldVisible`
class DynamicFields extends StatelessWidget {
  const DynamicFields({
    super.key,
    required this.schema,
    required this.values,
    required this.onChange,
    this.excludeIds = const {},
    this.errors = const {},
  });

  final FormSchema schema;
  final Map<String, Object?> values;
  final void Function(Map<String, Object?>) onChange;
  final Set<String> excludeIds;
  final Map<String, String> errors;

  void _setValue(String id, Object? v) {
    onChange({...values, id: v});
  }

  @override
  Widget build(BuildContext context) {
    final filteredSections = schema.sections
        .map((s) => _SectionView(
              section: s,
              fields: s.fields
                  .where((f) => !excludeIds.contains(f.id))
                  .toList(growable: false),
            ),)
        .where((sv) => sv.fields.isNotEmpty)
        .toList(growable: false);
    if (filteredSections.isEmpty) return const SizedBox.shrink();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        for (final sv in filteredSections) ...[
          _SectionHeader(section: sv.section),
          const SizedBox(height: 8),
          for (final field in sv.fields)
            if (isFieldVisible(field, values))
              Padding(
                padding: const EdgeInsets.only(bottom: 14),
                child: _FieldRow(
                  field: field,
                  value: values[field.id],
                  error: errors[field.id],
                  onChange: (v) => _setValue(field.id, v),
                ),
              ),
          const SizedBox(height: 8),
        ],
      ],
    );
  }
}

class _SectionView {
  const _SectionView({required this.section, required this.fields});
  final FormSection section;
  final List<FormSchemaField> fields;
}

class _SectionHeader extends StatelessWidget {
  const _SectionHeader({required this.section});
  final FormSection section;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(top: 8, bottom: 6),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            section.title,
            style: const TextStyle(
              color: PaColors.navy,
              fontSize: 14,
              fontWeight: FontWeight.w800,
              letterSpacing: 0.2,
            ),
          ),
          if (section.description != null && section.description!.isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(top: 2),
              child: Text(
                section.description!,
                style: const TextStyle(
                  color: PaColors.inkSecondary,
                  fontSize: 12,
                  height: 1.4,
                ),
              ),
            ),
        ],
      ),
    );
  }
}

class _FieldRow extends StatelessWidget {
  const _FieldRow({
    required this.field,
    required this.value,
    required this.onChange,
    this.error,
  });

  final FormSchemaField field;
  final Object? value;
  final void Function(Object?) onChange;
  final String? error;

  @override
  Widget build(BuildContext context) {
    final label = field.required ? '${field.label} *' : field.label;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          label,
          style: const TextStyle(
            color: PaColors.inkSecondary,
            fontSize: 12,
            fontWeight: FontWeight.w700,
          ),
        ),
        const SizedBox(height: 6),
        _buildField(context),
        if (error != null) ...[
          const SizedBox(height: 4),
          Text(
            error!,
            style: const TextStyle(
              color: PaColors.danger,
              fontSize: 11,
              fontWeight: FontWeight.w600,
            ),
          ),
        ] else if (field.helpText != null && field.helpText!.isNotEmpty) ...[
          const SizedBox(height: 4),
          Text(
            field.helpText!,
            style: const TextStyle(
              color: PaColors.inkMuted,
              fontSize: 11,
              height: 1.4,
            ),
          ),
        ],
      ],
    );
  }

  Widget _buildField(BuildContext context) {
    switch (field.type) {
      case FormFieldType.text:
      case FormFieldType.email:
      case FormFieldType.tel:
      case FormFieldType.number:
        return _TextInput(field: field, value: value, onChange: onChange);
      case FormFieldType.textarea:
        return _TextInput(
          field: field,
          value: value,
          onChange: onChange,
          multiline: true,
        );
      case FormFieldType.select:
        return _SelectInput(field: field, value: value, onChange: onChange);
      case FormFieldType.radio:
        return _RadioInput(field: field, value: value, onChange: onChange);
      case FormFieldType.checkbox:
        return _CheckboxInput(field: field, value: value, onChange: onChange);
      case FormFieldType.date:
        return _DateInput(field: field, value: value, onChange: onChange);
      case FormFieldType.file:
        return _FileInput(field: field, value: value, onChange: onChange);
    }
  }
}

class _TextInput extends StatelessWidget {
  const _TextInput({
    required this.field,
    required this.value,
    required this.onChange,
    this.multiline = false,
  });

  final FormSchemaField field;
  final Object? value;
  final void Function(Object?) onChange;
  final bool multiline;

  TextInputType get _keyboard {
    switch (field.type) {
      case FormFieldType.email:
        return TextInputType.emailAddress;
      case FormFieldType.tel:
        return TextInputType.phone;
      case FormFieldType.number:
        return const TextInputType.numberWithOptions(decimal: false);
      default:
        return multiline ? TextInputType.multiline : TextInputType.text;
    }
  }

  @override
  Widget build(BuildContext context) {
    return TextFormField(
      initialValue: value?.toString() ?? '',
      keyboardType: _keyboard,
      maxLines: multiline ? 4 : 1,
      maxLength: field.maxLength,
      onChanged: onChange,
      decoration: InputDecoration(
        hintText: field.placeholder,
        contentPadding:
            const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
        counterText: '',
      ),
    );
  }
}

class _SelectInput extends StatelessWidget {
  const _SelectInput({
    required this.field,
    required this.value,
    required this.onChange,
  });
  final FormSchemaField field;
  final Object? value;
  final void Function(Object?) onChange;

  @override
  Widget build(BuildContext context) {
    final current = value?.toString();
    return DropdownButtonFormField<String>(
      initialValue: field.options.any((o) => o.value == current) ? current : null,
      isExpanded: true,
      hint: Text(field.placeholder ?? 'Choisir…'),
      items: [
        for (final o in field.options)
          DropdownMenuItem(value: o.value, child: Text(o.label)),
      ],
      onChanged: onChange,
      decoration: const InputDecoration(
        contentPadding:
            EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      ),
    );
  }
}

class _RadioInput extends StatelessWidget {
  const _RadioInput({
    required this.field,
    required this.value,
    required this.onChange,
  });
  final FormSchemaField field;
  final Object? value;
  final void Function(Object?) onChange;

  @override
  Widget build(BuildContext context) {
    final current = value?.toString();
    return RadioGroup<String>(
      groupValue: current,
      onChanged: onChange,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          for (final o in field.options)
            RadioListTile<String>(
              dense: true,
              contentPadding: EdgeInsets.zero,
              value: o.value,
              title: Text(o.label,
                  style: const TextStyle(fontSize: 13, color: PaColors.inkPrimary),),
            ),
        ],
      ),
    );
  }
}

class _CheckboxInput extends StatelessWidget {
  const _CheckboxInput({
    required this.field,
    required this.value,
    required this.onChange,
  });
  final FormSchemaField field;
  final Object? value;
  final void Function(Object?) onChange;

  @override
  Widget build(BuildContext context) {
    final checked = value == true;
    return InkWell(
      onTap: () => onChange(!checked),
      borderRadius: BorderRadius.circular(8),
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 4),
        child: Row(
          children: [
            SizedBox(
              width: 22,
              height: 22,
              child: Checkbox(
                value: checked,
                onChanged: (v) => onChange(v ?? false),
              ),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: Text(
                field.label,
                style: const TextStyle(
                  fontSize: 13,
                  color: PaColors.inkPrimary,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _DateInput extends StatelessWidget {
  const _DateInput({
    required this.field,
    required this.value,
    required this.onChange,
  });
  final FormSchemaField field;
  final Object? value;
  final void Function(Object?) onChange;

  @override
  Widget build(BuildContext context) {
    final raw = value?.toString();
    final parsed = raw == null ? null : DateTime.tryParse(raw);
    return InkWell(
      onTap: () async {
        final picked = await showDatePicker(
          context: context,
          initialDate: parsed ?? DateTime.now(),
          firstDate: DateTime(1900),
          lastDate: DateTime(2100),
        );
        if (picked != null) {
          // ISO YYYY-MM-DD pour cohérence avec backend / portail.
          onChange(
            '${picked.year.toString().padLeft(4, '0')}-'
            '${picked.month.toString().padLeft(2, '0')}-'
            '${picked.day.toString().padLeft(2, '0')}',
          );
        }
      },
      borderRadius: BorderRadius.circular(10),
      child: Container(
        height: 48,
        padding: const EdgeInsets.symmetric(horizontal: 14),
        decoration: BoxDecoration(
          color: PaColors.cardBg,
          borderRadius: BorderRadius.circular(10),
          border: Border.all(color: PaColors.line),
        ),
        alignment: Alignment.centerLeft,
        child: Row(
          children: [
            const Icon(Icons.calendar_today_outlined,
                size: 18, color: PaColors.teal,),
            const SizedBox(width: 10),
            Expanded(
              child: Text(
                raw == null || raw.isEmpty
                    ? (field.placeholder ?? 'Sélectionner une date')
                    : raw,
                style: TextStyle(
                  color: raw == null || raw.isEmpty
                      ? PaColors.inkMuted
                      : PaColors.inkPrimary,
                  fontSize: 14,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _FileInput extends StatelessWidget {
  const _FileInput({
    required this.field,
    required this.value,
    required this.onChange,
  });
  final FormSchemaField field;
  final Object? value;
  final void Function(Object?) onChange;

  Future<void> _pick(BuildContext context) async {
    final allowedExts = _parseAcceptToExtensions(field.accept);
    try {
      // file_picker 11+ : appel statique direct (plus de `.platform` singleton).
      final result = await FilePicker.pickFiles(
        type: allowedExts == null ? FileType.any : FileType.custom,
        allowedExtensions: allowedExts,
        withData: false,
        withReadStream: false,
      );
      final picked = result?.files.single;
      if (picked == null) return;
      final path = picked.path;
      if (path == null) {
        if (context.mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Fichier inaccessible.')),
          );
        }
        return;
      }
      final size = File(path).lengthSync();
      onChange(PickedFile(path: path, name: picked.name, sizeBytes: size));
    } catch (_) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Sélection du fichier impossible.')),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final picked = value is PickedFile ? value as PickedFile : null;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        InkWell(
          onTap: () => _pick(context),
          borderRadius: BorderRadius.circular(10),
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
            decoration: BoxDecoration(
              color: PaColors.cardBg,
              borderRadius: BorderRadius.circular(10),
              border: Border.all(
                color: picked != null ? PaColors.teal : PaColors.line,
                width: picked != null ? 1.4 : 1,
              ),
            ),
            child: Row(
              children: [
                Icon(
                  picked != null
                      ? Icons.attach_file_rounded
                      : Icons.upload_file_outlined,
                  color: picked != null ? PaColors.teal : PaColors.inkSecondary,
                  size: 20,
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: Text(
                    picked != null
                        ? picked.name
                        : (field.placeholder ?? 'Choisir un fichier'),
                    style: TextStyle(
                      color: picked != null
                          ? PaColors.inkPrimary
                          : PaColors.inkMuted,
                      fontSize: 13,
                      fontWeight: FontWeight.w600,
                    ),
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
                if (picked != null)
                  IconButton(
                    icon: const Icon(Icons.close_rounded, size: 18),
                    color: PaColors.inkMuted,
                    onPressed: () => onChange(null),
                    tooltip: 'Retirer',
                  ),
              ],
            ),
          ),
        ),
        if (field.maxSizeMb != null)
          Padding(
            padding: const EdgeInsets.only(top: 4),
            child: Text(
              'Taille max : ${field.maxSizeMb} Mo',
              style: const TextStyle(
                color: PaColors.inkMuted,
                fontSize: 11,
              ),
            ),
          ),
      ],
    );
  }

  /// Convertit un `accept` MIME en liste d'extensions exploitable par
  /// `file_picker` (FileType.custom). Renvoie `null` si pas de filtre clair
  /// → on bascule sur FileType.any.
  List<String>? _parseAcceptToExtensions(String? accept) {
    if (accept == null || accept.trim().isEmpty) return null;
    final out = <String>{};
    for (final token in accept.split(',')) {
      final t = token.trim().toLowerCase();
      if (t.isEmpty) continue;
      if (t.startsWith('.')) {
        out.add(t.substring(1));
      } else if (t == 'image/*') {
        out.addAll(['jpg', 'jpeg', 'png', 'gif', 'webp', 'heic']);
      } else if (t == 'application/pdf') {
        out.add('pdf');
      } else if (t.contains('/')) {
        final sub = t.split('/').last;
        if (sub != '*' && sub.isNotEmpty) out.add(sub);
      }
    }
    return out.isEmpty ? null : out.toList();
  }
}
