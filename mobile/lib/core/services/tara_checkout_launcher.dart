import 'dart:developer' as developer;

import 'package:flutter/material.dart';

import '../widgets/tara_checkout_webview_page.dart';
import 'global_nav.dart';

/// Service partagé pour ouvrir la page de checkout Tara dans une WebView
/// in-app quand le backend répond à `POST /api/v1/payments/init/` avec
/// un champ `paymentUrl`.
///
/// On utilise une WebView Flutter (et NON `url_launcher`) car :
///  - Android dispatche automatiquement les URLs `dklo.co` vers l'app
///    native Dikalo si elle est installée (intent filter système).
///  - Même `LaunchMode.inAppBrowserView` (Chrome Custom Tab) est sujet
///    à ce dispatch sur certains Android.
///  - WebView rend l'HTML directement dans Flutter → pas d'intent
///    système → impossible pour Dikalo de hijacker.
class TaraCheckoutLauncher {
  TaraCheckoutLauncher._();

  /// Extrait `paymentUrl` de la réponse `POST /payments/init/` et pousse
  /// la WebView Tara via le navigateur racine de l'app. Retourne `true`
  /// si la page a été poussée, `false` sinon (mock_mode côté backend ou
  /// URL absente).
  static Future<bool> launchFromInitResponse(Map<String, dynamic>? data) async {
    if (data == null) return false;
    final url = (data['paymentUrl'] ?? data['payment_url']) as String?;
    if (url == null || url.isEmpty) {
      developer.log(
        '[TaraCheckout] no paymentUrl in response (mock_mode or backend error)',
        name: 'tara',
      );
      return false;
    }
    final nav = rootNavigatorKey.currentState;
    if (nav == null) {
      developer.log(
        '[TaraCheckout] rootNavigatorKey not yet attached — skip launch',
        name: 'tara',
      );
      return false;
    }
    developer.log('[TaraCheckout] pushing WebView for $url', name: 'tara');
    nav.push<void>(
      MaterialPageRoute<void>(
        builder: (_) => TaraCheckoutWebViewPage(url: url),
        fullscreenDialog: true,
      ),
    );
    return true;
  }
}
