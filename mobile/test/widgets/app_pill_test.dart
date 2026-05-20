import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gathe_finance/app/theme/app_colors.dart';
import 'package:gathe_finance/core/widgets/app_pill.dart';

void main() {
  Future<void> pump(WidgetTester tester, Widget child) async {
    await tester.pumpWidget(MaterialApp(home: Scaffold(body: child)));
  }

  testWidgets('AppPill affiche le label et adopte la palette de la tone',
      (tester) async {
    await pump(
      tester,
      const AppPill(label: 'Validé', tone: PillTone.success),
    );

    expect(find.text('Validé'), findsOneWidget);

    final container = tester.widget<Container>(find.descendant(
      of: find.byType(AppPill),
      matching: find.byType(Container),
    ).first);

    final decoration = container.decoration as BoxDecoration?;
    expect(decoration?.color, AppColors.emeraldSurface);
  });

  testWidgets('AppPill montre l\'icône quand fournie', (tester) async {
    await pump(tester, const AppPill(
      label: 'En retard',
      tone: PillTone.danger,
      icon: Icons.error,
    ));
    expect(find.byIcon(Icons.error), findsOneWidget);
  });
}
