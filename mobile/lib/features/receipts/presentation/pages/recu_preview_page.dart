import 'package:flutter/material.dart';
import 'package:printing/printing.dart';

import '../../../../app/theme/paysika/pa_colors.dart';
import '../../../../app/theme/paysika/pa_typography.dart';
import '../../data/recu_pdf_service.dart';

/// Aperçu plein écran du reçu de versement avant partage/impression.
/// `PdfPreview` (package printing) expose nativement Partager + Imprimer.
class RecuPreviewPage extends StatelessWidget {
  const RecuPreviewPage({super.key, required this.data});

  final RecuData data;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: PaColors.appBg,
      appBar: AppBar(
        backgroundColor: PaColors.paper,
        surfaceTintColor: PaColors.paper,
        elevation: 0,
        title: Text(data.title, style: PaText.heading(size: 18)),
        iconTheme: const IconThemeData(color: PaColors.inkPrimary),
      ),
      body: PdfPreview(
        build: (format) => buildRecuVersementPdf(data),
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
