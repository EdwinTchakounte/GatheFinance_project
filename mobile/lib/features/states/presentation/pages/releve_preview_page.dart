import 'package:flutter/material.dart';
import 'package:printing/printing.dart';

import '../../../../app/theme/paysika/pa_colors.dart';
import '../../../../app/theme/paysika/pa_typography.dart';
import '../../data/releve_pdf_service.dart';

/// Aperçu plein écran du relevé PDF avant partage/impression.
///
/// `PdfPreview` (package printing) rend le document et expose nativement les
/// actions **Partager** et **Imprimer** dans sa barre d'outils.
class RelevePreviewPage extends StatelessWidget {
  const RelevePreviewPage({super.key, required this.data, required this.title});

  final RelevePdfData data;
  final String title;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: PaColors.appBg,
      appBar: AppBar(
        backgroundColor: PaColors.paper,
        surfaceTintColor: PaColors.paper,
        elevation: 0,
        title: Text(title, style: PaText.heading(size: 18)),
        iconTheme: const IconThemeData(color: PaColors.inkPrimary),
      ),
      body: PdfPreview(
        build: (format) => buildRelevePdf(data),
        pdfFileName: '${data.fileName}.pdf',
        canChangePageFormat: false,
        canChangeOrientation: false,
        canDebug: false,
        loadingWidget: const Center(
          child: CircularProgressIndicator(color: PaColors.teal),
        ),
      ),
    );
  }
}
