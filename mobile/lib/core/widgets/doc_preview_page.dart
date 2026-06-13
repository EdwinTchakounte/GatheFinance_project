import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../app/theme/paysika/pa_colors.dart';
import 'paysika/pa_card.dart';

/// CH-1 — Aperçu inline réutilisable d'une pièce jointe (image ou PDF).
///
/// Décisions :
/// - **Images** (jpg/jpeg/png/webp/gif) rendues inline avec [InteractiveViewer]
///   pour le zoom/pan, hostable depuis n'importe quelle URL HTTPS.
/// - **PDF** ouvert dans le viewer système via `url_launcher` (évite
///   d'ajouter un package PDF natif lourd ~5 Mo APK). Une carte d'action
///   est affichée pour ne pas laisser l'écran vide.
/// - Si le type n'est pas reconnu, on tente d'ouvrir en externe.
///
/// Usage :
/// ```dart
/// Navigator.push(context, MaterialPageRoute(builder: (_) =>
///   DocPreviewPage(url: doc.url, title: 'BRC – ${member.fullName}')));
/// ```
class DocPreviewPage extends StatelessWidget {
  const DocPreviewPage({
    super.key,
    required this.url,
    required this.title,
    this.subtitle,
  });

  final String url;
  final String title;
  final String? subtitle;

  bool get _isImage {
    final lower = url.toLowerCase().split('?').first;
    return lower.endsWith('.jpg') ||
        lower.endsWith('.jpeg') ||
        lower.endsWith('.png') ||
        lower.endsWith('.webp') ||
        lower.endsWith('.gif');
  }

  bool get _isPdf {
    final lower = url.toLowerCase().split('?').first;
    return lower.endsWith('.pdf');
  }

  Future<void> _openExternal(BuildContext context) async {
    final uri = Uri.tryParse(url);
    if (uri == null) return;
    final ok = await launchUrl(uri, mode: LaunchMode.externalApplication);
    if (!ok && context.mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Aucune application disponible pour ouvrir le fichier.')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: PaColors.paper,
      appBar: AppBar(
        backgroundColor: PaColors.paper,
        elevation: 0,
        title: Text(
          title,
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
          style: const TextStyle(
            color: PaColors.inkPrimary,
            fontSize: 16,
            fontWeight: FontWeight.w700,
          ),
        ),
        iconTheme: const IconThemeData(color: PaColors.inkPrimary),
        actions: [
          IconButton(
            tooltip: 'Ouvrir en externe',
            icon: const Icon(Icons.open_in_new_rounded),
            onPressed: () => _openExternal(context),
          ),
        ],
      ),
      body: SafeArea(
        child: _isImage
            ? _ImageView(url: url)
            : _PdfOrUnknownView(
                url: url,
                title: title,
                subtitle: subtitle,
                isPdf: _isPdf,
                onOpen: () => _openExternal(context),
              ),
      ),
    );
  }
}

class _ImageView extends StatelessWidget {
  const _ImageView({required this.url});
  final String url;

  @override
  Widget build(BuildContext context) {
    return InteractiveViewer(
      minScale: 1.0,
      maxScale: 4.0,
      child: Center(
        child: Image.network(
          url,
          loadingBuilder: (context, child, progress) {
            if (progress == null) return child;
            return const Center(
              child: SizedBox(
                width: 28,
                height: 28,
                child: CircularProgressIndicator(strokeWidth: 2),
              ),
            );
          },
          errorBuilder: (context, error, _) => _ErrorPanel(
            message: 'Impossible de charger l’image.',
            detail: error.toString(),
          ),
        ),
      ),
    );
  }
}

class _PdfOrUnknownView extends StatelessWidget {
  const _PdfOrUnknownView({
    required this.url,
    required this.title,
    required this.subtitle,
    required this.isPdf,
    required this.onOpen,
  });

  final String url;
  final String title;
  final String? subtitle;
  final bool isPdf;
  final VoidCallback onOpen;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: PaCard(
          padding: const EdgeInsets.all(20),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                width: 52,
                height: 52,
                decoration: BoxDecoration(
                  color: PaColors.tealSurface,
                  borderRadius: BorderRadius.circular(14),
                ),
                child: Icon(
                  isPdf ? Icons.picture_as_pdf_rounded : Icons.description_outlined,
                  color: PaColors.teal,
                  size: 28,
                ),
              ),
              const SizedBox(height: 14),
              Text(
                title,
                style: const TextStyle(
                  color: PaColors.inkPrimary,
                  fontSize: 16,
                  fontWeight: FontWeight.w700,
                ),
              ),
              if (subtitle != null && subtitle!.isNotEmpty) ...[
                const SizedBox(height: 4),
                Text(
                  subtitle!,
                  style: const TextStyle(
                    color: PaColors.inkSecondary,
                    fontSize: 13,
                    height: 1.4,
                  ),
                ),
              ],
              const SizedBox(height: 14),
              Text(
                isPdf
                    ? 'L’aperçu PDF utilise le lecteur système de ton téléphone.'
                    : 'Format non pris en charge directement — on tente une ouverture externe.',
                style: const TextStyle(
                  color: PaColors.inkMuted,
                  fontSize: 12.5,
                  height: 1.4,
                ),
              ),
              const SizedBox(height: 16),
              SizedBox(
                width: double.infinity,
                child: FilledButton.icon(
                  onPressed: onOpen,
                  icon: const Icon(Icons.open_in_new_rounded, size: 18),
                  label: const Text('Ouvrir'),
                  style: FilledButton.styleFrom(
                    backgroundColor: PaColors.teal,
                    foregroundColor: PaColors.onTeal,
                    padding: const EdgeInsets.symmetric(vertical: 13),
                    shape: const RoundedRectangleBorder(
                      borderRadius: BorderRadius.all(Radius.circular(14)),
                    ),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _ErrorPanel extends StatelessWidget {
  const _ErrorPanel({required this.message, required this.detail});
  final String message;
  final String detail;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(20),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const Icon(Icons.error_outline, color: PaColors.danger, size: 32),
          const SizedBox(height: 8),
          Text(
            message,
            style: const TextStyle(
              color: PaColors.danger,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            detail,
            textAlign: TextAlign.center,
            style: const TextStyle(color: PaColors.inkMuted, fontSize: 12),
          ),
        ],
      ),
    );
  }
}
