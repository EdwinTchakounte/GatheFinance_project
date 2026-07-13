import 'dart:typed_data';

import 'package:flutter/services.dart' show rootBundle;
import 'package:pdf/pdf.dart';
import 'package:pdf/widgets.dart' as pw;
import 'package:printing/printing.dart';

/// Une ligne de détail du reçu : libellé + valeur (déjà formatés/localisés par
/// la couche présentation — le service ne fait que la mise en page).
class RecuLine {
  const RecuLine(this.label, this.value, {this.emphasize = false});
  final String label;
  final String value;

  /// Ligne mise en avant (ex. « Total débité »).
  final bool emphasize;
}

/// Données d'un **reçu de versement** GATHE (mini-facture d'une transaction).
class RecuData {
  const RecuData({
    required this.title,
    required this.receiptRef,
    required this.issuedOn,
    required this.memberName,
    required this.memberNumber,
    required this.operationLabel,
    required this.amountValue,
    required this.statusLabel,
    required this.lines,
    required this.footer,
    required this.fileName,
  });

  final String title; // « Reçu de versement »
  final String receiptRef; // « Reçu N° 000123 »
  final String issuedOn; // « Émis le 13/07/2026 »
  final String memberName;
  final String memberNumber;
  final String operationLabel; // type de versement (type_display)
  final String amountValue; // montant principal, formaté
  final String statusLabel; // « Validé », « En attente »…
  final List<RecuLine> lines; // détails (montant, frais, taux, dates, réf…)
  final String footer;
  final String fileName;
}

const _ink = PdfColor.fromInt(0xFF111827);
const _muted = PdfColor.fromInt(0xFF6B7280);
const _line = PdfColor.fromInt(0xFFE5E7EB);
const _teal = PdfColor.fromInt(0xFF0E7C7B);
const _tealSurface = PdfColor.fromInt(0xFFEAF5F5);

/// Construit le reçu de versement (A4, épuré) et renvoie les octets. Logo GATHE
/// joint en en-tête, polices bundlées (offline, jamais de fetch réseau).
Future<Uint8List> buildRecuVersementPdf(RecuData d) async {
  final interData = await rootBundle.load('assets/fonts/Inter.ttf');
  final soraData = await rootBundle.load('assets/fonts/Sora.ttf');
  final base = pw.Font.ttf(interData);
  final bold = pw.Font.ttf(soraData);
  final theme = pw.ThemeData.withFont(base: base, bold: bold);

  final logo = pw.MemoryImage(
    (await rootBundle.load('assets/images/logo_clean.png'))
        .buffer
        .asUint8List(),
  );

  final doc = pw.Document(theme: theme);

  pw.Widget detailRow(RecuLine l) => pw.Padding(
        padding: const pw.EdgeInsets.symmetric(vertical: 5),
        child: pw.Row(
          mainAxisAlignment: pw.MainAxisAlignment.spaceBetween,
          crossAxisAlignment: pw.CrossAxisAlignment.start,
          children: [
            pw.Expanded(
              child: pw.Text(
                l.label,
                style: const pw.TextStyle(color: _muted, fontSize: 10),
              ),
            ),
            pw.SizedBox(width: 16),
            pw.Text(
              l.value,
              style: pw.TextStyle(
                color: _ink,
                fontSize: l.emphasize ? 12 : 10.5,
                fontWeight:
                    l.emphasize ? pw.FontWeight.bold : pw.FontWeight.normal,
              ),
            ),
          ],
        ),
      );

  doc.addPage(
    pw.Page(
      pageFormat: PdfPageFormat.a4,
      margin: const pw.EdgeInsets.fromLTRB(40, 44, 40, 40),
      build: (context) => pw.Column(
        crossAxisAlignment: pw.CrossAxisAlignment.start,
        children: [
          // En-tête : logo + titre + réf/date.
          pw.Row(
            crossAxisAlignment: pw.CrossAxisAlignment.start,
            mainAxisAlignment: pw.MainAxisAlignment.spaceBetween,
            children: [
              pw.Column(
                crossAxisAlignment: pw.CrossAxisAlignment.start,
                children: [
                  pw.Image(logo, height: 40),
                  pw.SizedBox(height: 10),
                  pw.Text(
                    d.title,
                    style: pw.TextStyle(
                      color: _ink,
                      fontSize: 18,
                      fontWeight: pw.FontWeight.bold,
                    ),
                  ),
                ],
              ),
              pw.Column(
                crossAxisAlignment: pw.CrossAxisAlignment.end,
                children: [
                  pw.Text(
                    d.receiptRef,
                    style: const pw.TextStyle(color: _ink, fontSize: 10),
                  ),
                  pw.SizedBox(height: 3),
                  pw.Text(
                    d.issuedOn,
                    style: const pw.TextStyle(color: _muted, fontSize: 9),
                  ),
                ],
              ),
            ],
          ),
          pw.SizedBox(height: 8),
          pw.Divider(color: _line, thickness: 1),
          pw.SizedBox(height: 14),

          // Membre.
          detailRow(RecuLine('Membre', d.memberName)),
          detailRow(RecuLine('N° membre', d.memberNumber)),
          pw.SizedBox(height: 16),

          // Bloc montant mis en avant.
          pw.Container(
            width: double.infinity,
            padding: const pw.EdgeInsets.all(16),
            decoration: pw.BoxDecoration(
              color: _tealSurface,
              borderRadius: pw.BorderRadius.circular(10),
              border: pw.Border.all(color: _teal, width: 0.6),
            ),
            child: pw.Column(
              crossAxisAlignment: pw.CrossAxisAlignment.start,
              children: [
                pw.Text(
                  d.operationLabel.toUpperCase(),
                  style: pw.TextStyle(
                    color: _teal,
                    fontSize: 9,
                    fontWeight: pw.FontWeight.bold,
                    letterSpacing: 0.5,
                  ),
                ),
                pw.SizedBox(height: 6),
                pw.Text(
                  d.amountValue,
                  style: pw.TextStyle(
                    color: _ink,
                    fontSize: 26,
                    fontWeight: pw.FontWeight.bold,
                  ),
                ),
                pw.SizedBox(height: 4),
                pw.Text(
                  'Statut : ${d.statusLabel}',
                  style: const pw.TextStyle(color: _muted, fontSize: 9.5),
                ),
              ],
            ),
          ),
          pw.SizedBox(height: 20),

          // Détails de l'opération.
          pw.Text(
            'Détails de l\'opération',
            style: pw.TextStyle(
              color: _ink,
              fontSize: 12,
              fontWeight: pw.FontWeight.bold,
            ),
          ),
          pw.SizedBox(height: 4),
          pw.Divider(color: _line, thickness: 0.5),
          ...d.lines.map(detailRow),

          pw.Spacer(),
          pw.Divider(color: _line, thickness: 0.5),
          pw.SizedBox(height: 8),
          pw.Text(
            d.footer,
            style: const pw.TextStyle(color: _muted, fontSize: 8),
          ),
        ],
      ),
    ),
  );

  return doc.save();
}

/// Partage direct (feuille système) — réutilise [buildRecuVersementPdf].
Future<void> shareRecuVersementPdf(RecuData d) async {
  await Printing.sharePdf(
    bytes: await buildRecuVersementPdf(d),
    filename: '${d.fileName}.pdf',
  );
}
