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
  /// Heure du dernier passage en arrière-plan. On l'utilise au retour
  /// (resumed) pour décider si on doit verrouiller : un aller-retour court
  /// (file picker, sélecteur de date, partage…) ne doit pas demander le PIN.
  DateTime? _backgroundedAt;

  /// Délai en-deçà duquel un retour au premier plan est considéré comme
  /// "interactif" (file picker, partage Android, etc.) et NE déclenche pas
  /// le verrouillage. Standard banking : 30–60 s. On choisit 30 s.
  static const _lockGrace = Duration(seconds: 30);

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
    // Quand l'app passe en arrière-plan, on note l'heure mais on ne verrouille
    // PAS immédiatement : le verrou réel se décide au retour (resumed).
    if (state == AppLifecycleState.paused ||
        state == AppLifecycleState.hidden) {
      _backgroundedAt = DateTime.now();
      return;
    }
    if (state == AppLifecycleState.resumed) {
      final since = _backgroundedAt;
      _backgroundedAt = null;
      if (since == null) return;
      final elapsed = DateTime.now().difference(since);
      // Plus de 30 s en arrière-plan → on verrouille. Moins → on laisse
      // l'utilisateur reprendre là où il en était (cas typique : file picker
      // pour joindre l'attestation CFP / la carte CGA dans la sheet crédit).
      if (elapsed >= _lockGrace) {
        ref.read(pinProvider.notifier).lock();
      }
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
