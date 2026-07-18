import 'package:flutter/material.dart';

import '../../../../app/theme/paysika/pa_colors.dart';
import '../../../../core/widgets/doc_preview_page.dart';
import '../../domain/entities/announcement.dart';

/// Lecture détaillée d'une annonce : titre, date, texte complet, pièce jointe.
class AnnouncementDetailPage extends StatelessWidget {
  const AnnouncementDetailPage({super.key, required this.announcement});

  final Announcement announcement;

  String get _dateLabel {
    final d = announcement.publishedAt;
    if (d == null) return '';
    String two(int n) => n.toString().padLeft(2, '0');
    return '${two(d.day)}/${two(d.month)}/${d.year}';
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
        leading: IconButton(
          onPressed: () => Navigator.maybePop(context),
          icon:
              const Icon(Icons.arrow_back_rounded, color: PaColors.inkPrimary),
        ),
        title: const Text(
          'Annonce',
          style: TextStyle(
            color: PaColors.inkPrimary,
            fontSize: 16,
            fontWeight: FontWeight.w700,
          ),
        ),
      ),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(20, 8, 20, 32),
        children: [
          Text(
            announcement.titre,
            style: const TextStyle(
              color: PaColors.inkPrimary,
              fontSize: 22,
              fontWeight: FontWeight.w800,
              height: 1.25,
            ),
          ),
          if (_dateLabel.isNotEmpty) ...[
            const SizedBox(height: 6),
            Text(
              _dateLabel,
              style: const TextStyle(
                color: PaColors.inkMuted,
                fontSize: 13,
                fontWeight: FontWeight.w500,
              ),
            ),
          ],
          if (announcement.hasImage) ...[
            const SizedBox(height: 16),
            _Attachment(url: announcement.imageUrl!, title: announcement.titre),
          ],
          const SizedBox(height: 18),
          Text(
            announcement.corps,
            style: const TextStyle(
              color: PaColors.inkSecondary,
              fontSize: 16,
              height: 1.55,
            ),
          ),
        ],
      ),
    );
  }
}

class _Attachment extends StatelessWidget {
  const _Attachment({required this.url, required this.title});

  final String url;
  final String title;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: () => Navigator.of(context).push(
        MaterialPageRoute<void>(
          builder: (_) => DocPreviewPage(
            url: url,
            title: title,
            subtitle: 'Pièce jointe',
          ),
        ),
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(18),
        child: Image.network(
          url,
          width: double.infinity,
          fit: BoxFit.cover,
          loadingBuilder: (context, child, progress) {
            if (progress == null) return child;
            return Container(
              height: 180,
              alignment: Alignment.center,
              color: PaColors.tealSurface,
              child: const CircularProgressIndicator(
                strokeWidth: 2,
                color: PaColors.teal,
              ),
            );
          },
          errorBuilder: (_, __, ___) => Container(
            height: 120,
            alignment: Alignment.center,
            color: PaColors.tealSurface,
            child: const Icon(Icons.broken_image_outlined,
                color: PaColors.inkMuted,),
          ),
        ),
      ),
    );
  }
}
