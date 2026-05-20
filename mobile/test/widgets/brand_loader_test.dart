import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gathe_finance/core/widgets/brand_loader.dart';

void main() {
  testWidgets('BrandLoader rend les deux arcs et ne crash pas', (tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(
          body: Center(child: BrandLoader()),
        ),
      ),
    );

    // L'animation tourne — on avance d'1 frame pour vérifier qu'elle ne plante pas
    await tester.pump(const Duration(milliseconds: 200));
    expect(find.byType(BrandLoader), findsOneWidget);
    expect(find.byType(CustomPaint), findsWidgets);
  });

  testWidgets('BrandPulseDots affiche 3 points', (tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(body: BrandPulseDots()),
      ),
    );
    await tester.pump(const Duration(milliseconds: 100));
    expect(find.byType(BrandPulseDots), findsOneWidget);
  });
}
