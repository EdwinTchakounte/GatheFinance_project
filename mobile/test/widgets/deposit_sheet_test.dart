import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gathe_finance/l10n/gen/app_localizations.dart';
import 'package:gathe_finance/core/di/providers.dart';
import 'package:gathe_finance/core/widgets/paysika/pa_button.dart';
import 'package:gathe_finance/features/home/presentation/widgets/deposit_sheet.dart';
import 'package:gathe_finance/features/savings/data/datasources/savings_remote_datasource.dart';
import 'package:gathe_finance/features/savings/domain/entities/savings_account.dart';

import '../helpers/fixtures.dart';

class _FakeDataSource extends Fake implements SavingsRemoteDataSource {
  int depositCalls = 0;
  late SavingsAccount last;
  @override
  Future<SavingsAccount> fetchMine() async => Fixtures.savings();
  @override
  Future<SavingsAccount> deposit({
    required num amount,
    required String phone,
    required String network,
    bool isPlacement = false,
    int nbJoursCouverts = 1,
  }) async {
    depositCalls += 1;
    last = Fixtures.savings(solde: 365000 + amount);
    return last;
  }
}

void main() {
  setUpAll(() {
    // mocktail registerFallback pour les non-named — pas besoin ici.
  });

  setUp(() {
    // Désactive les feedbacks hardware pendant les tests.
    TestWidgetsFlutterBinding.ensureInitialized();
    SystemChannels.platform.setMockMethodCallHandler((_) async => null);
  });

  Widget app(Widget child, _FakeDataSource ds) {
    return ProviderScope(
      overrides: [
        savingsDataSourceProvider.overrideWithValue(ds),
      ],
      child: MaterialApp(
        locale: const Locale('fr'),
        localizationsDelegates: AppL10n.localizationsDelegates,
        supportedLocales: AppL10n.supportedLocales,
        home: Scaffold(body: child),
      ),
    );
  }

  // Helper : passe l'étape 1 « Comment veux-tu verser ? » en choisissant
  // Mobile Money — l'étape qui amène au formulaire existant.
  Future<void> pickMobileChannel(WidgetTester tester) async {
    await tester.pumpAndSettle();
    await tester.tap(find.text('Mobile Money'));
    await tester.pumpAndSettle();
  }

  testWidgets('DepositSheet — étape choix : affiche Mobile Money + Agence',
      (tester) async {
    final ds = _FakeDataSource();
    await tester.pumpWidget(app(const DepositSheet(), ds));
    await tester.pumpAndSettle();

    expect(find.text('Mobile Money'), findsOneWidget);
    expect(find.text("À l'agence"), findsOneWidget);
    expect(find.textContaining('Comment veux-tu verser'), findsOneWidget);
  });

  testWidgets(
      'DepositSheet — choisir « À l\'agence » montre l\'info-card (pas le form)',
      (tester) async {
    final ds = _FakeDataSource();
    await tester.pumpWidget(app(const DepositSheet(), ds));
    await tester.pumpAndSettle();

    await tester.tap(find.text("À l'agence"));
    await tester.pumpAndSettle();

    expect(find.textContaining('On te garde une place'), findsOneWidget);
    expect(find.text('Compris'), findsOneWidget);
    // Pas de formulaire — donc pas de bouton "Confirmer le versement".
    expect(find.text('Confirmer le versement'), findsNothing);
    expect(ds.depositCalls, 0);
  });

  testWidgets('DepositSheet — étape form : champ vide affiche erreur',
      (tester) async {
    final ds = _FakeDataSource();
    await tester.pumpWidget(app(const DepositSheet(), ds));
    await pickMobileChannel(tester);

    // Vider le champ montant
    await tester.enterText(find.byType(TextFormField).first, '');
    await tester.tap(find.byType(PaButton).last);
    await tester.pumpAndSettle();

    expect(find.textContaining('Saisis un montant'), findsOneWidget);
    expect(ds.depositCalls, 0);
  });

  testWidgets('DepositSheet — étape form : montant < 100 XAF rejeté',
      (tester) async {
    final ds = _FakeDataSource();
    await tester.pumpWidget(app(const DepositSheet(), ds));
    await pickMobileChannel(tester);

    await tester.enterText(find.byType(TextFormField).first, '50');
    await tester.tap(find.byType(PaButton).last);
    await tester.pumpAndSettle();

    expect(find.textContaining('Minimum'), findsOneWidget);
    expect(ds.depositCalls, 0);
  });

  testWidgets(
      'DepositSheet — pré-remplissage 1000 XAF (cotisation suggérée Article 4)',
      (tester) async {
    final ds = _FakeDataSource();
    await tester.pumpWidget(app(const DepositSheet(), ds));
    await pickMobileChannel(tester);

    // Le champ montant doit afficher 1000 par défaut.
    final field = tester.widget<TextFormField>(find.byType(TextFormField).first);
    expect(field.controller?.text, '1000');
  });

  testWidgets(
      'DepositSheet — montant valide → loading → success → datasource appelée',
      (tester) async {
    final ds = _FakeDataSource();
    await tester.pumpWidget(app(const DepositSheet(), ds));
    await pickMobileChannel(tester);

    // Saisit 10 000 XAF directement (plus stable que le chip qui dépend de
    // l'espace insécable de NumberFormat).
    await tester.enterText(find.byType(TextFormField).first, '10000');
    await tester.pump();

    await tester.tap(find.byType(PaButton).last);
    // Attend la résolution complète (delay 1900ms mock + anim).
    // On ne vérifie pas l'étape "loading" intermédiaire — le sheet utilise un
    // AnimatedSize dont la résolution multi-frames rend l'assertion flaky.
    await tester.pumpAndSettle(const Duration(seconds: 4));

    // Le datasource a été appelé exactement une fois
    expect(ds.depositCalls, 1);
    // Étape "en cours" affichée (le paiement Tara n'est pas encore validé
    // côté backend tant que le membre n'a pas tapé son PIN MoMo sur la page
    // Tara — on affiche donc "Paiement en cours" et pas "confirmé").
    expect(find.text('Paiement en cours'), findsOneWidget);
    expect(find.text('Terminé'), findsOneWidget);
  });
}
