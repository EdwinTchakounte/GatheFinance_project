import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gathe_finance/features/loans/domain/entities/loan_installment.dart';
import 'package:gathe_finance/features/loans/presentation/widgets/installment_tile.dart';
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

  testWidgets('InstallmentTile — payée affiche le pill success', (tester) async {
    final inst = LoanInstallment(
      id: 1,
      numero: 1,
      dateEcheance: DateTime(2026, 5, 12),
      montantCapital: 39667,
      montantInterets: 7000,
      montantTotal: 46667,
      montantPaye: 46667,
      statut: InstallmentStatus.payee,
    );
    await pump(tester, InstallmentTile(installment: inst));
    expect(find.text('Payée'), findsOneWidget);
    expect(find.byIcon(Icons.check_circle_rounded), findsOneWidget);
  });

  testWidgets('InstallmentTile — en retard affiche le pill danger',
      (tester) async {
    final inst = LoanInstallment(
      id: 2,
      numero: 2,
      dateEcheance: DateTime(2026, 4, 1),
      montantCapital: 39667,
      montantInterets: 7000,
      montantTotal: 46667,
      montantPaye: 0,
      statut: InstallmentStatus.enRetard,
    );
    await pump(tester, InstallmentTile(installment: inst));
    expect(find.text('En retard'), findsOneWidget);
  });

  testWidgets('InstallmentTile — partielle affiche le pill warning',
      (tester) async {
    final inst = LoanInstallment(
      id: 3,
      numero: 3,
      dateEcheance: DateTime(2026, 6, 12),
      montantCapital: 39667,
      montantInterets: 7000,
      montantTotal: 46667,
      montantPaye: 20000,
      statut: InstallmentStatus.partielle,
    );
    await pump(tester, InstallmentTile(installment: inst));
    expect(find.text('Partielle'), findsOneWidget);
  });
}
