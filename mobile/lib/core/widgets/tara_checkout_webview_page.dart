import 'dart:developer' as developer;

import 'package:flutter/material.dart';
import 'package:webview_flutter/webview_flutter.dart';

import '../../app/theme/paysika/pa_colors.dart';

/// Page plein écran qui rend la page de checkout Tara dans une WebView
/// in-app. On choisit cette approche (vs `url_launcher.LaunchMode.inAppBrowserView`)
/// car Android dispatche automatiquement les URLs `dklo.co` vers l'app
/// Dikalo si elle est installée — même Chrome Custom Tab n'y échappe pas.
/// La WebView rend l'HTML directement dans Flutter, pas d'Intent.ACTION_VIEW.
class TaraCheckoutWebViewPage extends StatefulWidget {
  const TaraCheckoutWebViewPage({super.key, required this.url});

  final String url;

  @override
  State<TaraCheckoutWebViewPage> createState() =>
      _TaraCheckoutWebViewPageState();
}

class _TaraCheckoutWebViewPageState extends State<TaraCheckoutWebViewPage> {
  late final WebViewController _controller;
  double _progress = 0;

  @override
  void initState() {
    super.initState();
    _controller = WebViewController()
      ..setJavaScriptMode(JavaScriptMode.unrestricted)
      ..setBackgroundColor(PaColors.canvas)
      // User-Agent Chrome Android standard : la version desktop forcait
      // Tara a servir une version ExtJS qui plantait dans la WebView
      // (Onerror sur /pays/assets/ext-new/ext-all.js). On laisse Tara
      // detecter Android et servir sa version mobile -- la redirection
      // intent:// vers Dikalo qui pourrait suivre est bloquee par
      // onNavigationRequest plus bas.
      ..setUserAgent(
        'Mozilla/5.0 (Linux; Android 13; Mobile) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/120.0.0.0 Mobile Safari/537.36',
      )
      ..setNavigationDelegate(NavigationDelegate(
        onProgress: (p) {
          if (!mounted) return;
          setState(() => _progress = p / 100.0);
        },
        onPageStarted: (u) =>
            developer.log('[Tara] page started: $u', name: 'tara'),
        onPageFinished: (u) =>
            developer.log('[Tara] page finished: $u', name: 'tara'),
        onWebResourceError: (err) {
          developer.log(
            '[Tara] resource error: ${err.errorCode} ${err.description} '
            'isMain=${err.isForMainFrame} url=${err.url}',
            name: 'tara',
          );
        },
        onHttpError: (err) {
          developer.log(
            '[Tara] http error ${err.response?.statusCode} on ${err.request?.uri}',
            name: 'tara',
          );
        },
        // On laisse passer TOUT ce qui est http(s) (Tara redirige souvent
        // entre ses sous-domaines pendant le checkout). On bloque
        // uniquement les vrais deep links Android qui sortent de la
        // WebView : intent:// (vers app Dikalo) et market:// (Play Store).
        onNavigationRequest: (req) {
          final u = req.url.toLowerCase();
          if (u.startsWith('intent://') || u.startsWith('market://')) {
            developer.log(
              '[Tara] blocked deep link: ${req.url}',
              name: 'tara',
            );
            return NavigationDecision.prevent;
          }
          return NavigationDecision.navigate;
        },
      ))
      ..loadRequest(Uri.parse(widget.url));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: PaColors.canvas,
      appBar: AppBar(
        backgroundColor: PaColors.canvas,
        surfaceTintColor: PaColors.canvas,
        elevation: 0,
        scrolledUnderElevation: 0,
        iconTheme: const IconThemeData(color: PaColors.inkPrimary),
        title: const Text(
          'Paiement Mobile Money',
          style: TextStyle(
            color: PaColors.inkPrimary,
            fontSize: 16,
            fontWeight: FontWeight.w700,
          ),
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh_rounded),
            tooltip: 'Recharger',
            onPressed: () => _controller.reload(),
          ),
        ],
        bottom: _progress < 1.0
            ? PreferredSize(
                preferredSize: const Size.fromHeight(2),
                child: LinearProgressIndicator(
                  value: _progress,
                  minHeight: 2,
                  backgroundColor: PaColors.tealSurface,
                  valueColor:
                      const AlwaysStoppedAnimation<Color>(PaColors.teal),
                ),
              )
            : null,
      ),
      body: WebViewWidget(controller: _controller),
    );
  }
}
