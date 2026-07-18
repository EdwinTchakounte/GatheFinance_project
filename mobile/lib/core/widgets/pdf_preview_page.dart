/// Page de pre-visualisation inline d'un PDF distant.
///
/// Telecharge le binaire via Dio (cookies session inclus pour les media
/// derriere /audit/) et l'affiche avec ``PdfPreview`` du package
/// ``printing``. Le user peut zoomer, parcourir les pages et choisir
/// d'ouvrir le PDF en plein ecran via le menu systeme.
library;

import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:printing/printing.dart';

import '../../app/theme/paysika/pa_colors.dart';
import '../di/providers.dart';
import '../error/error_message.dart';

class PdfPreviewPage extends ConsumerStatefulWidget {
  const PdfPreviewPage({
    required this.url,
    required this.title,
    super.key,
  });

  /// URL absolue du PDF a afficher (ex. /media/coop/assets/reglement.pdf).
  final String url;

  /// Titre affiche en AppBar.
  final String title;

  static Future<void> open(
    BuildContext context, {
    required String url,
    required String title,
  }) {
    return Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => PdfPreviewPage(url: url, title: title),
      ),
    );
  }

  @override
  ConsumerState<PdfPreviewPage> createState() => _PdfPreviewPageState();
}

class _PdfPreviewPageState extends ConsumerState<PdfPreviewPage> {
  Uint8List? _bytes;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final dio = ref.read(apiClientProvider).dio;
      final res = await dio.get<List<int>>(
        widget.url,
        options: Options(
          responseType: ResponseType.bytes,
          // L'allowlist /media/coop/assets/ etend public . pas besoin d'auth.
          // Mais on reste sur le client Dio pour beneficier du cookies jar
          // et de la base URL standardisee.
          followRedirects: true,
          validateStatus: (s) => s != null && s < 500,
        ),
      );
      final code = res.statusCode ?? 0;
      if (code >= 400) {
        throw Exception('HTTP $code');
      }
      final bytes = Uint8List.fromList(res.data ?? const []);
      if (!mounted) return;
      setState(() {
        _bytes = bytes;
        _error = null;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = friendlyError(e);
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: PaColors.canvas,
      appBar: AppBar(
        backgroundColor: PaColors.paper,
        foregroundColor: PaColors.inkPrimary,
        elevation: 0,
        title: Text(
          widget.title,
          style: const TextStyle(
            fontSize: 16,
            fontWeight: FontWeight.w700,
            color: PaColors.inkPrimary,
          ),
        ),
      ),
      body: _error != null
          ? _ErrorPanel(message: _error!, onRetry: _load)
          : _bytes == null
              ? const Center(
                  child: CircularProgressIndicator(color: PaColors.teal),
                )
              : PdfPreview(
                  build: (_) async => _bytes!,
                  allowPrinting: true,
                  allowSharing: true,
                  canChangeOrientation: false,
                  canChangePageFormat: false,
                  canDebug: false,
                  loadingWidget: const Center(
                    child:
                        CircularProgressIndicator(color: PaColors.teal),
                  ),
                  // Couleurs douces aligne sur Paysika.
                  pdfPreviewPageDecoration: const BoxDecoration(
                    color: Colors.white,
                  ),
                ),
    );
  }
}

class _ErrorPanel extends StatelessWidget {
  const _ErrorPanel({required this.message, required this.onRetry});

  final String message;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.cloud_off_rounded,
                size: 48, color: PaColors.inkMuted,),
            const SizedBox(height: 12),
            const Text(
              'Impossible de charger l\'aperçu.',
              style: TextStyle(
                fontSize: 15,
                fontWeight: FontWeight.w700,
                color: PaColors.inkPrimary,
              ),
            ),
            const SizedBox(height: 4),
            Text(
              message,
              textAlign: TextAlign.center,
              style: const TextStyle(
                color: PaColors.inkMuted,
                fontSize: 12.5,
              ),
            ),
            const SizedBox(height: 16),
            FilledButton.tonal(
              onPressed: onRetry,
              child: const Text('Réessayer'),
            ),
          ],
        ),
      ),
    );
  }
}
