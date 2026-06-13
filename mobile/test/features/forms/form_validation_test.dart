import 'package:flutter_test/flutter_test.dart';
import 'package:gathe_finance/features/forms/domain/entities/form_schema.dart';
import 'package:gathe_finance/features/forms/domain/form_validation.dart';

void main() {
  group('isFieldVisible — conditions', () {
    test('pas de condition → visible', () {
      const f = FormSchemaField(
        id: 'x',
        type: FormFieldType.text,
        label: 'X',
      );
      expect(isFieldVisible(f, const {}), isTrue);
    });

    test('equals → visible si la valeur référée matche', () {
      const f = FormSchemaField(
        id: 'doc',
        type: FormFieldType.file,
        label: 'Doc',
        condition: FormFieldCondition(
          field: 'statut',
          operator: FormFieldConditionOperator.equals,
          value: 'independant',
        ),
      );
      expect(isFieldVisible(f, {'statut': 'independant'}), isTrue);
      expect(isFieldVisible(f, {'statut': 'salarie'}), isFalse);
    });

    test('not_equals → visible si la valeur référée diffère', () {
      const f = FormSchemaField(
        id: 'x',
        type: FormFieldType.text,
        label: 'X',
        condition: FormFieldCondition(
          field: 'statut',
          operator: FormFieldConditionOperator.notEquals,
          value: 'salarie',
        ),
      );
      expect(isFieldVisible(f, {'statut': 'independant'}), isTrue);
      expect(isFieldVisible(f, {'statut': 'salarie'}), isFalse);
    });

    test('in → visible si la valeur référée est dans la liste', () {
      const f = FormSchemaField(
        id: 'x',
        type: FormFieldType.text,
        label: 'X',
        condition: FormFieldCondition(
          field: 'pays',
          operator: FormFieldConditionOperator.inList,
          value: ['CMR', 'TCD'],
        ),
      );
      expect(isFieldVisible(f, {'pays': 'CMR'}), isTrue);
      expect(isFieldVisible(f, {'pays': 'FRA'}), isFalse);
    });
  });

  group('validateField — règles métier', () {
    test('required vide → erreur', () {
      const f = FormSchemaField(
        id: 'x',
        type: FormFieldType.text,
        label: 'X',
        required: true,
      );
      expect(validateField(f, null), isNotNull);
      expect(validateField(f, ''), isNotNull);
      expect(validateField(f, 'ok'), isNull);
    });

    test('email format', () {
      const f = FormSchemaField(
        id: 'e',
        type: FormFieldType.email,
        label: 'Email',
      );
      expect(validateField(f, 'not-an-email'), isNotNull);
      expect(validateField(f, 'a@b.co'), isNull);
    });

    test('number bornes min/max', () {
      const f = FormSchemaField(
        id: 'n',
        type: FormFieldType.number,
        label: 'N',
        min: 10,
        max: 50,
      );
      expect(validateField(f, '5'), isNotNull);
      expect(validateField(f, '60'), isNotNull);
      expect(validateField(f, '30'), isNull);
      expect(validateField(f, 'abc'), isNotNull);
    });

    test('text maxLength', () {
      const f = FormSchemaField(
        id: 't',
        type: FormFieldType.text,
        label: 'T',
        maxLength: 5,
      );
      expect(validateField(f, '123456'), isNotNull);
      expect(validateField(f, 'ok'), isNull);
    });

    test('file size cap (max_size_mb)', () {
      const f = FormSchemaField(
        id: 'f',
        type: FormFieldType.file,
        label: 'F',
        maxSizeMb: 1,
      );
      const tooBig = PickedFile(
        path: '/tmp/a.pdf',
        name: 'a.pdf',
        sizeBytes: 2 * 1024 * 1024,
      );
      const ok = PickedFile(
        path: '/tmp/b.pdf',
        name: 'b.pdf',
        sizeBytes: 500 * 1024,
      );
      expect(validateField(f, tooBig), isNotNull);
      expect(validateField(f, ok), isNull);
    });
  });

  group('validateSchema — passe complète', () {
    const schema = FormSchema(
      id: 1,
      kind: 'loan_request',
      version: 1,
      title: 'Demande',
      sections: [
        FormSection(
          id: 's1',
          title: 'Identité',
          fields: [
            FormSchemaField(
              id: 'nom',
              type: FormFieldType.text,
              label: 'Nom',
              required: true,
            ),
            FormSchemaField(
              id: 'duree_mois', // hardcoded → doit être exclu
              type: FormFieldType.number,
              label: 'Durée',
              required: true,
            ),
            FormSchemaField(
              id: 'doc',
              type: FormFieldType.file,
              label: 'Doc',
              required: true,
              condition: FormFieldCondition(
                field: 'statut',
                operator: FormFieldConditionOperator.equals,
                value: 'indep',
              ),
            ),
            FormSchemaField(
              id: 'statut',
              type: FormFieldType.select,
              label: 'Statut',
              required: true,
            ),
          ],
        ),
      ],
    );

    test('exclut les hardcoded même si manquants', () {
      final errs = validateSchema(
        schema,
        const {'nom': 'Jean', 'statut': 'salarie'},
        excludeIds: const {'duree_mois'},
      );
      expect(errs, isEmpty);
    });

    test('détecte les champs requis vides', () {
      final errs = validateSchema(
        schema,
        const {'statut': 'salarie'},
        excludeIds: const {'duree_mois'},
      );
      expect(errs.keys, contains('nom'));
    });

    test('respecte la visibilité conditionnelle', () {
      // statut=salarie → doc invisible → pas d'erreur dessus.
      var errs = validateSchema(
        schema,
        const {'nom': 'X', 'statut': 'salarie'},
        excludeIds: const {'duree_mois'},
      );
      expect(errs.keys, isNot(contains('doc')));

      // statut=indep → doc visible et requis → erreur.
      errs = validateSchema(
        schema,
        const {'nom': 'X', 'statut': 'indep'},
        excludeIds: const {'duree_mois'},
      );
      expect(errs.keys, contains('doc'));
    });
  });
}
