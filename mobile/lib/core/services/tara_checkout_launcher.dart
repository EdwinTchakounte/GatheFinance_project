import 'dart:developer' as developer;

import 'package:url_launcher/url_launcher.dart';

/// Service partagé pour lancer la page de checkout Tara dans le navigateur
/// externe quand le backend répond à `POST /api/v1/payments/init/` avec
/// un champ `paymentUrl`.
///
/// Tara héberge une page web où le membre choisit son opérateur (MTN /
/// Orange / Wave) et valide la transaction avec son PIN Mobile Money.
/// Le webhook backend reçoit la confirmation et passe le Payment en
/// `valide` — le mobile met à jour son solde au prochain `fetchMine()`.
class TaraCheckoutLauncher {
  TaraCheckoutLauncher._();

  /// Tente d'extraire `paymentUrl` de la réponse `POST /payments/init/` et
  /// d'ouvrir cette URL via le navigateur externe.
  /// Retourne `true` si l'URL a été lancée, `false` sinon (mock_mode côté
  /// backend, ou URL absente). Ne throw jamais — les erreurs de launch
  /// sont loggées et ignorées (le membre peut toujours rafraîchir).
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
    final uri = Uri.tryParse(url);
    if (uri == null) {
      developer.log('[TaraCheckout] invalid url: $url', name: 'tara');
      return false;
    }
    try {
      // PRIORITÉ : Chrome Custom Tab / SFSafariViewController in-app.
      // Évite que Android dispatche vers l'app Dikalo (deep link sur dklo.co)
      // et garde l'utilisateur dans Gathé Finance (overlay navigateur, pas un
      // saut hors-app). Fallback `externalApplication` si le device n'a pas
      // de Custom Tab disponible.
      var ok = false;
      try {
        ok = await launchUrl(uri, mode: LaunchMode.inAppBrowserView);
      } catch (_) {
        ok = false;
      }
      if (!ok) {
        ok = await launchUrl(uri, mode: LaunchMode.externalApplication);
      }
      developer.log('[TaraCheckout] launched $url → $ok', name: 'tara');
      return ok;
    } catch (e, st) {
      developer.log(
        '[TaraCheckout] launchUrl failed: $e',
        name: 'tara',
        error: e,
        stackTrace: st,
      );
      return false;
    }
  }
}
