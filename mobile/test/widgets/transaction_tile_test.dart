import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gathe_finance/core/widgets/transaction_tile.dart';
import 'package:gathe_finance/features/savings/domain/entities/savings_transaction.dart';

void main() {
  Future<void> pump(WidgetTester tester, Widget child) async {
    await tester.pumpWidget(MaterialApp(home: Scaffold(body: child)));
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
}
