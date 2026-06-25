import 'package:flutter/widgets.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/services/global_nav.dart';

import '../../features/auth/presentation/pages/forgot_password_page.dart';
import '../../features/auth/presentation/pages/login_page.dart';
import '../../features/auth/presentation/state/auth_notifier.dart';
import '../../features/avaliste/presentation/pages/avaliste_mandats_page.dart';
import '../../features/lender/presentation/pages/lender_page.dart';
import '../../features/booklet/presentation/pages/booklet_page.dart';
import '../../features/contributions/presentation/pages/contributions_page.dart';
import '../../features/credit/presentation/pages/credit_page.dart';
import '../../features/home/presentation/pages/home_page.dart';
import '../../features/home_feed/domain/entities/feed_item.dart';
import '../../features/home_feed/presentation/pages/campaign_detail_page.dart';
import '../../features/home_feed/presentation/pages/campaigns_list_page.dart';
import '../../features/home_feed/presentation/pages/news_detail_page.dart';
import '../../features/home_feed/presentation/pages/news_list_page.dart';
import '../../features/help/presentation/pages/help_contact_page.dart';
import '../../features/loans/presentation/pages/my_lender_payouts_page.dart';
import '../../features/notifications/presentation/pages/notifications_page.dart';
import '../../features/preferences/presentation/pages/notifications_preferences_page.dart';
import '../../features/states/presentation/pages/states_page.dart';
import '../../features/onboarding/presentation/pages/onboarding_page.dart';
import '../../features/onboarding/presentation/state/onboarding_notifier.dart';
import '../../features/profile/presentation/pages/profile_page.dart';
import '../../features/savings/presentation/pages/savings_history_page.dart';
import '../../features/security/presentation/pages/pin_change_page.dart';
import '../../features/security/presentation/pages/pin_lock_page.dart';
import '../../features/security/presentation/pages/pin_setup_page.dart';
import '../../features/security/presentation/state/pin_notifier.dart';
import '../../features/shell/presentation/pages/main_shell.dart';
import '../../features/splash/presentation/pages/splash_page.dart';

/// Routing déclaratif avec go_router.
///
/// Séquence d'entrée :
///   `/splash` → (onboarding pas vu) → `/onboarding`
///             → (onboarding vu, non connecté) → `/login`
///             → (onboarding vu, connecté) → shell `/home` (bottom nav 4 onglets)
final appRouterProvider = Provider<GoRouter>((ref) {
  return GoRouter(
    initialLocation: '/splash',
    debugLogDiagnostics: false,
    refreshListenable: _RouterRefresher(ref),
    // Key racine partagee — permet aux services hors widget (datasource
    // qui ouvre le checkout Tara) de pousser une page sans BuildContext.
    navigatorKey: rootNavigatorKey,
    redirect: (context, state) {
      final onboarding = ref.read(onboardingProvider);
      final auth = ref.read(authProvider);
      final pin = ref.read(pinProvider);

      // Tant que l'un des providers est en cours de résolution, on reste sur splash.
      if (onboarding.isLoading || auth.isLoading || pin.isLoading) {
        return state.matchedLocation == '/splash' ? null : '/splash';
      }

      final seen = onboarding.valueOrNull ?? false;
      final member = auth.valueOrNull;
      final pinState = pin.valueOrNull;
      final hasPin = pinState?.hasPin ?? false;
      final locked = pinState?.locked ?? false;
      final location = state.matchedLocation;

      // L'utilisateur est sur splash → on l'envoie au bon endroit
      if (location == '/splash') {
        if (!seen) return '/onboarding';
        if (member == null) return '/login';
        if (!hasPin) return '/pin/setup';
        if (locked) return '/pin/lock';
        return '/home';
      }

      // Sécurité : pas sur les écrans d'auth si déjà connecté
      if (member != null && (location == '/login' || location == '/onboarding')) {
        if (!hasPin) return '/pin/setup';
        if (locked) return '/pin/lock';
        return '/home';
      }

      // Connecté sans PIN défini → forcer la configuration du PIN.
      if (member != null && !hasPin && location != '/pin/setup') {
        return '/pin/setup';
      }

      // Connecté, PIN défini, app verrouillée → écran de déverrouillage.
      if (member != null && hasPin && locked && location != '/pin/lock') {
        return '/pin/lock';
      }

      // Sécurité : pas dans le shell si pas connecté
      const guarded = ['/home', '/credit', '/booklet', '/profile'];
      if (member == null && guarded.contains(location)) {
        return seen ? '/login' : '/onboarding';
      }

      return null;
    },
    routes: [
      GoRoute(
        path: '/splash',
        name: 'splash',
        builder: (context, state) => const SplashPage(),
      ),
      GoRoute(
        path: '/onboarding',
        name: 'onboarding',
        builder: (context, state) => const OnboardingPage(),
      ),
      GoRoute(
        path: '/login',
        name: 'login',
        builder: (context, state) => const LoginPage(),
      ),
      // Mot de passe oublié — accessible depuis le login, sans auth.
      GoRoute(
        path: '/auth/forgot-password',
        name: 'forgot-password',
        pageBuilder: (context, state) =>
            _paSlideFadePage(state, const ForgotPasswordPage()),
      ),

      // Configuration du PIN (1er login) + déverrouillage (ouverture app).
      GoRoute(
        path: '/pin/setup',
        name: 'pin-setup',
        builder: (context, state) => const PinSetupPage(),
      ),
      GoRoute(
        path: '/pin/lock',
        name: 'pin-lock',
        builder: (context, state) => const PinLockPage(),
      ),
      GoRoute(
        path: '/pin/change',
        name: 'pin-change',
        pageBuilder: (context, state) =>
            _paSlideFadePage(state, const PinChangePage()),
      ),

      // Notifications — pushé par-dessus le shell depuis la cloche.
      GoRoute(
        path: '/notifications',
        name: 'notifications',
        pageBuilder: (context, state) =>
            _paSlideFadePage(state, const NotificationsPage()),
      ),

      // Historique épargne — pushé par-dessus le shell depuis Home.
      GoRoute(
        path: '/savings/history',
        name: 'savings-history',
        pageBuilder: (context, state) =>
            _paSlideFadePage(state, const SavingsHistoryPage()),
      ),

      // Cotisations (chronologie des frais payés) — pushée depuis Profil.
      GoRoute(
        path: '/contributions',
        name: 'contributions',
        pageBuilder: (context, state) =>
            _paSlideFadePage(state, const ContributionsPage()),
      ),

      // Mes états (relevé synthèse) — pushée depuis Profil.
      GoRoute(
        path: '/states',
        name: 'states',
        pageBuilder: (context, state) =>
            _paSlideFadePage(state, const StatesPage()),
      ),

      // Préférences notifications — pushée depuis Profil.
      GoRoute(
        path: '/preferences/notifications',
        name: 'preferences-notifications',
        pageBuilder: (context, state) =>
            _paSlideFadePage(state, const NotificationsPreferencesPage()),
      ),

      // Aide & contact (FAQ + coordonnées) — pushée depuis Profil.
      GoRoute(
        path: '/help',
        name: 'help',
        pageBuilder: (context, state) =>
            _paSlideFadePage(state, const HelpContactPage()),
      ),

      // Liste in-app des campagnes (Voir plus du carousel Home).
      // Pop avec un `campaign_id` (int) → la Home rouvre le sheet crédit
      // pré-rempli sur la voie campagne.
      GoRoute(
        path: '/campaigns',
        name: 'campaigns',
        pageBuilder: (context, state) =>
            _paSlideFadePage(state, const CampaignsListPage()),
      ),

      // Liste in-app des actualités (Voir plus du carousel Home).
      GoRoute(
        path: '/news',
        name: 'news',
        pageBuilder: (context, state) =>
            _paSlideFadePage(state, const NewsListPage()),
      ),

      // Détail d'une actualité — l'article est passé en `extra` pour un
      // rendu instantané ; la page fetch le body Wagtail en arrière-plan.
      GoRoute(
        path: '/news/:id',
        name: 'news-detail',
        pageBuilder: (context, state) {
          final article = state.extra as NewsArticle?;
          if (article == null) {
            return _paSlideFadePage(state, const NewsListPage());
          }
          return _paSlideFadePage(state, NewsDetailPage(article: article));
        },
      ),

      // Détail d'une campagne micro-crédit — like + commentaires.
      // L'objet `CampaignFlyer` est passé en `extra` pour un rendu instantané.
      GoRoute(
        path: '/campaigns/:id',
        name: 'campaign-detail',
        pageBuilder: (context, state) {
          final campaign = state.extra as CampaignFlyer?;
          if (campaign == null) {
            return _paSlideFadePage(state, const CampaignsListPage());
          }
          return _paSlideFadePage(
            state,
            CampaignDetailPage(campaign: campaign),
          );
        },
      ),

      // Mandats d'avaliste — pushée depuis la page Crédit.
      GoRoute(
        path: '/avaliste/mandats',
        name: 'avaliste-mandats',
        pageBuilder: (context, state) =>
            _paSlideFadePage(state, const AvalisteMandatsPage()),
      ),

      // CH-12 — Mes versements prêteur (depuis le profil).
      GoRoute(
        path: '/me/lender-payouts',
        name: 'my-lender-payouts',
        pageBuilder: (context, state) =>
            _paSlideFadePage(state, const MyLenderPayoutsPage()),
      ),

      // LOT 19 — Espace prêteur complet (consent + tranches + funding 24h).
      GoRoute(
        path: '/me/lender',
        name: 'my-lender',
        pageBuilder: (context, state) =>
            _paSlideFadePage(state, const LenderPage()),
      ),

      // Shell racine — 4 branches avec état indépendant.
      StatefulShellRoute.indexedStack(
        builder: (context, state, navigationShell) =>
            MainShell(navigationShell: navigationShell),
        branches: [
          StatefulShellBranch(routes: [
            GoRoute(
              path: '/home',
              name: 'home',
              builder: (context, state) => const HomePage(),
            ),
          ],),
          StatefulShellBranch(routes: [
            GoRoute(
              path: '/credit',
              name: 'credit',
              builder: (context, state) => const CreditPage(),
            ),
          ],),
          StatefulShellBranch(routes: [
            GoRoute(
              path: '/booklet',
              name: 'booklet',
              builder: (context, state) => const BookletPage(),
            ),
          ],),
          StatefulShellBranch(routes: [
            GoRoute(
              path: '/profile',
              name: 'profile',
              builder: (context, state) => const ProfilePage(),
            ),
          ],),
        ],
      ),
    ],
  );
});


/// Page transition Paysika — slide léger depuis la droite + fade-in.
///
/// Durée 320ms, courbe `easeOutCubic` pour la décélération premium.
/// Appliquée uniquement aux push (notifications, history, contributions, etc.)
/// — pas aux onglets bottom nav qui gardent le cross-fade Material.
CustomTransitionPage<void> _paSlideFadePage(
  GoRouterState state,
  Widget child,
) {
  return CustomTransitionPage<void>(
    key: state.pageKey,
    child: child,
    transitionDuration: const Duration(milliseconds: 320),
    reverseTransitionDuration: const Duration(milliseconds: 240),
    transitionsBuilder: (context, animation, secondaryAnimation, child) {
      final curved = CurvedAnimation(
        parent: animation,
        curve: Curves.easeOutCubic,
        reverseCurve: Curves.easeInCubic,
      );
      return FadeTransition(
        opacity: curved,
        child: SlideTransition(
          position: Tween<Offset>(
            begin: const Offset(0.06, 0),
            end: Offset.zero,
          ).animate(curved),
          child: child,
        ),
      );
    },
  );
}


/// Bridge entre les providers Riverpod et `go_router.refreshListenable`.
class _RouterRefresher extends ChangeNotifier {
  _RouterRefresher(Ref ref) {
    ref.listen(onboardingProvider, (_, __) => notifyListeners());
    ref.listen(authProvider, (_, __) => notifyListeners());
    ref.listen(pinProvider, (_, __) => notifyListeners());
  }
}
