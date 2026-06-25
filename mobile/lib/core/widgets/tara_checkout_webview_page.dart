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
      // User-Agent desktop : la page Tara detecte si on est sur Android
      // et tente sinon de pousser un intent:// vers l'app Dikalo (Play
      // Store). En se faisant passer pour Chrome desktop on shunt cette
      // detection et on garde la page web standard de checkout.
      ..setUserAgent(
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/120.0.0.0 Safari/537.36',
      )
      ..setNavigationDelegate(NavigationDelegate(
        onProgress: (p) {
          if (!mounted) return;
          setState(() => _progress = p / 100.0);
        },
        // Filet de sécurité : si Tara essaie quand même de pousser un
        // deep link intent:// ou de rediriger vers le Play Store, on
        // bloque pour rester dans la WebView.
        onNavigationRequest: (req) {
          final u = req.url.toLowerCase();
          if (u.startsWith('intent://') ||
              u.startsWith('market://') ||
              u.contains('play.google.com')) {
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
