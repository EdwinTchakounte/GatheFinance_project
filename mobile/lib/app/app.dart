import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../features/preferences/presentation/state/locale_notifier.dart';
import '../features/security/presentation/state/pin_notifier.dart';
import '../l10n/gen/app_localizations.dart';
import 'router/app_router.dart';
import 'theme/app_theme.dart';

class GatheApp extends ConsumerStatefulWidget {
  const GatheApp({super.key});

  @override
  ConsumerState<GatheApp> createState() => _GatheAppState();
}

class _GatheAppState extends ConsumerState<GatheApp>
    with WidgetsBindingObserver {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    // Reverrouille l'app dès qu'elle passe en arrière-plan / est masquée.
    // Au retour au premier plan, le router redirige vers /pin/lock.
    if (state == AppLifecycleState.paused ||
        state == AppLifecycleState.hidden) {
      ref.read(pinProvider.notifier).lock();
    }
  }

  @override
  Widget build(BuildContext context) {
    final router = ref.watch(appRouterProvider);
    final locale = ref.watch(localeProvider).valueOrNull ?? const Locale('fr');

    return MaterialApp.router(
      title: 'Gathe Finance',
      debugShowCheckedModeBanner: false,
      // Identité premium pensée en clair uniquement (crème + doodle) :
      // pas de thème sombre proposé.
      theme: AppTheme.light,
      themeMode: ThemeMode.light,
      routerConfig: router,
      // Borne le grossissement de police système : au-delà de 1.15 les layouts
      // denses (hero, montants 44pt, sheets) débordent. Accessibilité préservée
      // (jusqu'à +15 %) sans casser le rendu.
      builder: (context, child) => MediaQuery.withClampedTextScaling(
        minScaleFactor: 0.9,
        maxScaleFactor: 1.15,
        child: child!,
      ),
      locale: locale,
      supportedLocales: AppL10n.supportedLocales,
      localizationsDelegates: const [
        AppL10n.delegate,
        GlobalMaterialLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
      ],
    );
  }
}
