import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gathe_finance/core/di/providers.dart';
import 'package:gathe_finance/features/auth/data/datasources/auth_remote_datasource.dart';
import 'package:gathe_finance/features/auth/domain/entities/member.dart';
import 'package:gathe_finance/features/auth/presentation/pages/login_page.dart';
import 'package:gathe_finance/l10n/gen/app_localizations.dart';
import 'package:go_router/go_router.dart';

import '../helpers/fixtures.dart';

/// Datasource d'auth contrôlable depuis le test.
class _ScriptedAuthDs implements AuthRemoteDataSource {
  Member? session;
  Object? throwOnSignIn;
  int signInCalls = 0;

  @override
  Future<Member> signIn({required String email, required String password}) async {
    signInCalls += 1;
    final ex = throwOnSignIn;
    if (ex != null) throw ex;
    session = Fixtures.member();
    return session!;
  }

  @override
  Future<Member?> currentMember() async => session;

  @override
  Future<void> signOut() async => session = null;
}

void main() {
  Widget app(Widget child, _ScriptedAuthDs ds) {
    final router = GoRouter(
      initialLocation: '/login',
      routes: [
        GoRoute(path: '/login', builder: (_, __) => child),
        GoRoute(
          path: '/home',
          builder: (_, __) => const Scaffold(body: Text('HOME-REACHED')),
        ),
      ],
    );
    return ProviderScope(
      overrides: [authDataSourceProvider.overrideWithValue(ds)],
      child: MaterialApp.router(
        routerConfig: router,
        locale: const Locale('fr'),
        localizationsDelegates: AppL10n.localizationsDelegates,
        supportedLocales: AppL10n.supportedLocales,
      ),
    );
  }

  testWidgets('Login — email vide → message de validation', (tester) async {
    final ds = _ScriptedAuthDs();
    await tester.pumpWidget(app(const LoginPage(), ds));
    await tester.pumpAndSettle();

    // Vide le champ email pré-rempli
    final fields = find.byType(TextFormField);
    await tester.enterText(fields.first, '');
    await tester.tap(find.text('Se connecter'));
    await tester.pumpAndSettle();

    expect(find.textContaining('Adresse email requise'), findsOneWidget);
    expect(ds.signInCalls, 0);
  });

  testWidgets('Login — email mal formé → message de validation', (tester) async {
    final ds = _ScriptedAuthDs();
    await tester.pumpWidget(app(const LoginPage(), ds));
    await tester.pumpAndSettle();

    final fields = find.byType(TextFormField);
    await tester.enterText(fields.first, 'pasdemail');
    await tester.tap(find.text('Se connecter'));
    await tester.pumpAndSettle();

    expect(find.textContaining('Format invalide'), findsOneWidget);
    expect(ds.signInCalls, 0);
  });

  testWidgets('Login — credentials OK → datasource appelée 1 fois',
      (tester) async {
    final ds = _ScriptedAuthDs();
    await tester.pumpWidget(app(const LoginPage(), ds));
    await tester.pumpAndSettle();

    // Les champs sont pré-remplis avec jean.kamga@test.local / test1234
    await tester.tap(find.text('Se connecter'));
    await tester.pumpAndSettle();

    expect(ds.signInCalls, 1);
  });
}
