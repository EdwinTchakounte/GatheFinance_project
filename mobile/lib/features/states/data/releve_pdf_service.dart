import 'dart:typed_data';

import 'package:flutter/services.dart' show rootBundle;
import 'package:pdf/pdf.dart';
import 'package:pdf/widgets.dart' as pw;
import 'package:printing/printing.dart';

/// Données déjà localisées + formatées par la couche présentation.
/// Le service ne fait que la mise en page — aucune dépendance métier/i18n.
class RelevePdfData {
  const RelevePdfData({
    required this.docTitle,
    required this.issuedOn,
    required this.memberLabel,
    required this.memberName,
    required this.numberLabel,
    required this.memberNumber,
    required this.balanceLabel,
    required this.balanceValue,
    required this.rateLabel,
    required this.rateValue,
    required this.totalLabel,
    required this.totalValue,
    required this.txHeader,
    required this.colDate,
    required this.colLabel,
    required this.colAmount,
    required this.rows,
    required this.footer,
    required this.fileName,
  });

  final String docTitle;
  final String issuedOn;
  final String memberLabel;
  final String memberName;
  final String numberLabel;
  final String memberNumber;
  final String balanceLabel;
  final String balanceValue;
  final String rateLabel;
  final String rateValue;
  final String totalLabel;
  final String totalValue;
  final String txHeader;
  final String colDate;
  final String colLabel;
  final String colAmount;

  /// Lignes du tableau : [date, libellé, montant].
  final List<List<String>> rows;
  final String footer;
  final String fileName;
}

/// Couleurs sobres alignées sur la charte (encre + gris).
const _ink = PdfColor.fromInt(0xFF111827);
const _muted = PdfColor.fromInt(0xFF6B7280);
const _line = PdfColor.fromInt(0xFFE5E7EB);

/// Construit le relevé PDF (épuré) et renvoie les octets — réutilisé par la
/// preview ET le partage. Le **logo GATHE est joint** en en-tête.
Future<Uint8List> buildRelevePdf(RelevePdfData d) async {
  // Police bundlée (offline) — pas de fetch réseau (PdfGoogleFonts est proscrit).
  final interData = await rootBundle.load('assets/fonts/Inter.ttf');
  final soraData = await rootBundle.load('assets/fonts/Sora.ttf');
  final base = pw.Font.ttf(interData);
  final bold = pw.Font.ttf(soraData); // Sora pour l'emphase (gras visuel)
  final theme = pw.ThemeData.withFont(base: base, bold: bold);

  // Logo joint au document (offline, asset bundlé).
  final logo = pw.MemoryImage(
    (await rootBundle.load('assets/images/logo_clean.png')).buffer.asUint8List(),
  );

  final doc = pw.Document(theme: theme);

  pw.Widget summaryRow(String label, String value) => pw.Padding(
        padding: const pw.EdgeInsets.symmetric(vertical: 4),
        child: pw.Row(
          mainAxisAlignment: pw.MainAxisAlignment.spaceBetween,
          children: [
            pw.Text(label,
                style: const pw.TextStyle(color: _muted, fontSize: 10),),
            pw.Text(value,
                style: pw.TextStyle(
                    color: _ink, fontSize: 11, fontWeight: pw.FontWeight.bold,),),
          ],
        ),
      );

  doc.addPage(
    pw.MultiPage(
      pageFormat: PdfPageFormat.a4,
      margin: const pw.EdgeInsets.fromLTRB(36, 40, 36, 36),
      build: (context) => [
        // ── En-tête ──────────────────────────────────────────────
        pw.Row(
          crossAxisAlignment: pw.CrossAxisAlignment.start,
          mainAxisAlignment: pw.MainAxisAlignment.spaceBetween,
          children: [
            pw.Column(
              crossAxisAlignment: pw.CrossAxisAlignment.start,
              children: [
                pw.Image(logo, height: 42),
                pw.SizedBox(height: 8),
                pw.Text(d.docTitle,
                    style: const pw.TextStyle(color: _ink, fontSize: 13),),
              ],
            ),
            pw.Text(d.issuedOn,
                style: const pw.TextStyle(color: _muted, fontSize: 9),),
          ],
        ),
        pw.SizedBox(height: 6),
        pw.Divider(color: _line, thickness: 1),
        pw.SizedBox(height: 14),

        // ── Membre + résumé ──────────────────────────────────────
        summaryRow(d.memberLabel, d.memberName),
        summaryRow(d.numberLabel, d.memberNumber),
        pw.SizedBox(height: 8),
        summaryRow(d.balanceLabel, d.balanceValue),
        summaryRow(d.rateLabel, d.rateValue),
        summaryRow(d.totalLabel, d.totalValue),
        pw.SizedBox(height: 22),

        // ── Tableau des opérations ───────────────────────────────
        pw.Text(d.txHeader,
            style: pw.TextStyle(
                color: _ink, fontSize: 12, fontWeight: pw.FontWeight.bold,),),
        pw.SizedBox(height: 8),
        pw.TableHelper.fromTextArray(
          headers: [d.colDate, d.colLabel, d.colAmount],
          data: d.rows,
          border: null,
          headerStyle: pw.TextStyle(
              color: _muted, fontSize: 9, fontWeight: pw.FontWeight.bold,),
          headerDecoration: const pw.BoxDecoration(
            border: pw.Border(bottom: pw.BorderSide(color: _line, width: 1)),
          ),
          cellStyle: const pw.TextStyle(color: _ink, fontSize: 10),
          cellHeight: 24,
          cellAlignments: {
            0: pw.Alignment.centerLeft,
            1: pw.Alignment.centerLeft,
            2: pw.Alignment.centerRight,
          },
          oddRowDecoration: const pw.BoxDecoration(
            border: pw.Border(bottom: pw.BorderSide(color: _line, width: 0.5)),
          ),
          rowDecoration: const pw.BoxDecoration(
            border: pw.Border(bottom: pw.BorderSide(color: _line, width: 0.5)),
          ),
        ),
      ],
      footer: (context) => pw.Padding(
        padding: const pw.EdgeInsets.only(top: 12),
        child: pw.Text(d.footer,
            style: const pw.TextStyle(color: _muted, fontSize: 8),),
      ),
    ),
  );

  return doc.save();
}

/// Partage direct (feuille système) — réutilise [buildRelevePdf].
Future<void> shareRelevePdf(RelevePdfData d) async {
  await Printing.sharePdf(bytes: await buildRelevePdf(d), filename: '${d.fileName}.pdf');
}
