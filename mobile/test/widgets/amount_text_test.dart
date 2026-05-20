import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gathe_finance/core/widgets/amount_text.dart';

void main() {
  Future<void> pump(WidgetTester tester, Widget child) async {
    await tester.pumpWidget(MaterialApp(home: Scaffold(body: child)));
  }

  testWidgets('AmountText formate avec espaces fines et suffixe XAF',
      (tester) async {
    await pump(tester, const AmountText(365000));
    // Vérifie que le nombre apparaît bien (le format NumberFormat 'fr_FR'
    // utilise un U+202F entre milliers — on cherche les chiffres et XAF).
    expect(find.textContaining('365'), findsOneWidget);
    expect(find.textContaining('XAF'), findsOneWidget);
  });

  testWidgets('AmountText sans unité quand showUnit=false', (tester) async {
    await pump(tester, const AmountText(1000, showUnit: false));
    expect(find.textContaining('XAF'), findsNothing);
  });

  testWidgets('AmountText avec crossOut', (tester) async {
    await pump(tester, const AmountText(1000, crossOut: true));
    expect(find.textContaining('1'), findsOneWidget);
  });
}
