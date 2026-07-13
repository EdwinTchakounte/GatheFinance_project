import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/di/providers.dart';
import '../core/network/session_expiry.dart';
import '../features/auth/presentation/state/auth_notifier.dart';
import '../features/booklet/presentation/state/booklet_notifier.dart';
import '../features/loans/presentation/state/loans_notifier.dart';
import '../features/notifications/presentation/state/notifications_notifier.dart';
import '../features/preferences/presentation/state/locale_notifier.dart';
import '../features/savings/presentation/state/classic_savings_notifier.dart';
import '../features/savings/presentation/state/savings_notifier.dart';
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

  StreamSubscription<void>? _sessionExpirySub;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    // Session expirée (401/403) détectée par l'intercepteur → on route vers le
    // login proprement au lieu de laisser les pollers marteler l'API.
    _sessionExpirySub =
        SessionExpiryBus.instance.stream.listen((_) => _onSessionExpired());
  }

  @override
  void dispose() {
    _sessionExpirySub?.cancel();
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  void _onSessionExpired() {
    if (!mounted) return;
    // Déjà déconnecté ? rien à faire (évite un cycle inutile).
    if (ref.read(authProvider).valueOrNull == null) return;
    // Vide les cookies périmés puis rebascule l'auth : `authProvider.build`
    // ré-appelle `/auth/me/` (→ null sans session) → le router redirige /login.
    unawaited(ref.read(apiClientProvider).clearSession());
    ref.invalidate(authProvider);
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
      // Phase 1B . Resume-refresh des providers live a partir de 3 s en
      // background (gap inferieur = aller-retour rapide file picker, pas
      // utile de re-fetch). Couvre le cas "je quitte l'app, admin change
      // un truc, je reviens" sans attendre le polling 30 s.
      if (elapsed >= _resumeRefreshGrace) {
        _refreshLiveProviders();
      }
    }
  }

  /// Delai minimum en arriere-plan apres lequel on declenche un re-fetch
  /// des providers live au retour foreground. Inferieur a [_lockGrace] :
  /// on veut refresh meme pour un retour rapide, mais pas pour un round-trip
  /// instantane (< 3 s = file picker, retour ecran d'a cote).
  static const _resumeRefreshGrace = Duration(seconds: 3);

  void _refreshLiveProviders() {
    // Refresh SILENCIEUX des providers live au retour foreground (donnees qui
    // peuvent avoir change cote admin pendant l'absence). On appelle
    // `notifier.refresh()` (silentRefresh + dedup par hash) plutot que
    // `invalidate` : invalidate remettrait la page VISIBLE en skeleton et
    // reset le badge notif a chaque resume — exactement le flicker qu'on veut
    // eviter. Best-effort : un provider non-instancie est ignore.
    void safe(void Function() run) {
      try {
        run();
      } catch (_) {/* provider pas instancie : rien a rafraichir */}
    }
    // Providers PERSISTANTS des onglets (StatefulShellRoute.indexedStack : les
    // branches restent montees) → refresh silencieux, pas de flicker.
    safe(() => ref.read(savingsProvider.notifier).refresh());
    safe(() => ref.read(classicSavingsProvider.notifier).refresh());
    safe(() => ref.read(loansProvider.notifier).refresh());
    safe(() => ref.read(loanRequestsProvider.notifier).refresh());
    safe(() => ref.read(notificationsProvider.notifier).refresh());
    safe(() => ref.read(bookletProvider.notifier).refresh());
    // Statut membre : peut avoir bascule (activation/suspension) cote admin
    // pendant l'absence. Pas de refresh() sur AuthNotifier → invalidate leger
    // (n'impacte que 2 petits leaves : greeting + banniere statut).
    safe(() => ref.invalidate(authProvider));
    // Providers AUTODISPOSE (lender / avaliste / homeFeed) : volontairement PAS
    // rafraichis ici. Ils se rechargent frais a la navigation (autoDispose) et
    // chacune de leurs pages a son propre LivePoller. Les forcer ici
    // instancierait + fetcherait des donnees hors ecran → refresh inutile.
  }

  @override
  Widget build(BuildContext context) {
    final router = ref.watch(appRouterProvider);
    final locale = ref.watch(localeProvider).valueOrNull ?? const Locale('fr');

    return MaterialApp.router(
      title: 'GATHE Finance',
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
