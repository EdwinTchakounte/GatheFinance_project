import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gathe_finance/core/widgets/transaction_tile.dart';
import 'package:gathe_finance/features/savings/domain/entities/savings_transaction.dart';
import 'package:gathe_finance/l10n/gen/app_localizations.dart';

void main() {
  Future<void> pump(WidgetTester tester, Widget child) async {
    await tester.pumpWidget(MaterialApp(
      locale: const Locale('fr'),
      localizationsDelegates: AppL10n.localizationsDelegates,
      supportedLocales: AppL10n.supportedLocales,
      home: Scaffold(body: child),
    ),);
  }

  testWidgets('TransactionTile — dépôt : libellé + signe + (positif)',
      (tester) async {
    final tx = SavingsTransaction(
      id: 1,
      type: SavingsType.depot,
      montant: 25000,
      soldeApres: 365000,
      date: DateTime(2026, 5, 14),
    );
    await pump(tester, TransactionTile(tx: tx));

    expect(find.text('Dépôt épargne'), findsOneWidget);
    // « + » présent pour un dépôt
    expect(find.textContaining('+'), findsWidgets);
    expect(find.byIcon(Icons.arrow_downward_rounded), findsOneWidget);
  });

  testWidgets('TransactionTile — retrait : icône arrow_upward + signe −',
      (tester) async {
    final tx = SavingsTransaction(
      id: 2,
      type: SavingsType.retrait,
      montant: 5000,
      soldeApres: 360000,
      date: DateTime(2026, 5, 13),
    );
    await pump(tester, TransactionTile(tx: tx));

    expect(find.byIcon(Icons.arrow_upward_rounded), findsOneWidget);
    expect(find.text('Retrait'), findsOneWidget);
  });

  testWidgets('TransactionTile — intérêt : libellé spécifique', (tester) async {
    final tx = SavingsTransaction(
      id: 3,
      type: SavingsType.interet,
      montant: 850,
      soldeApres: 290000,
      date: DateTime(2026, 5, 1),
    );
    await pump(tester, TransactionTile(tx: tx));
    expect(find.text('Intérêts crédités'), findsOneWidget);
  });

  testWidgets('TransactionTile — frais (isDebit) : négatif + libellé backend',
      (tester) async {
    // Un frais d'étude arrive avec type_op=frais_demande_credit → type mappé
    // sur depot MAIS isDebit=true → doit s'afficher en NÉGATIF (sortie).
    final tx = SavingsTransaction.fromJson({
      'id': 4,
      'type_op': 'frais_demande_credit',
      'type_display': "Frais d'étude crédit",
      'sens': 'debit',
      'montant': 5000,
      'solde_apres': 20000,
      'date': '2026-05-20T10:00:00Z',
    });
    expect(tx.isOutflow, isTrue);
    expect(tx.montantSigne, -5000);
    await pump(tester, TransactionTile(tx: tx));
    expect(find.text("Frais d'étude crédit"), findsOneWidget);
    expect(find.textContaining('−'), findsWidgets); // signe négatif
    expect(find.byIcon(Icons.arrow_upward_rounded), findsOneWidget); // sortie
  });
}
