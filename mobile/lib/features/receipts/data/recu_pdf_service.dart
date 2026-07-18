import 'dart:typed_data';

import 'package:flutter/services.dart' show rootBundle;
import 'package:pdf/pdf.dart';
import 'package:pdf/widgets.dart' as pw;
import 'package:printing/printing.dart';

import '../../../core/pdf/gathe_letterhead.dart';

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

// Palette OFFICIELLE GATHE — vraies couleurs du logo, identiques aux PDF
// backend (papier à en-tête) pour une seule famille de documents.
const _blue = gatheBlue;
const _ink = PdfColor.fromInt(0xFF1A2230);
const _muted = PdfColor.fromInt(0xFF5B6472);
const _panelBorder = PdfColor.fromInt(0xFFD7E0EC);
const _panelBg = PdfColor.fromInt(0xFFEFF4FA);

/// Construit le reçu de versement (A4) au STYLE OFFICIEL GATHE : en-tête
/// « GATHE FINANCE », filet bicolore bleu+vert, titre centré, sections, panneau
/// montant mis en valeur, filigrane logo, footer. Polices bundlées (offline).
Future<Uint8List> buildRecuVersementPdf(RecuData d) async {
  final interData = await rootBundle.load('assets/fonts/Inter.ttf');
  final soraData = await rootBundle.load('assets/fonts/Sora.ttf');
  final base = pw.Font.ttf(interData);
  final bold = pw.Font.ttf(soraData);
  final theme = pw.ThemeData.withFont(base: base, bold: bold);

  final logo = await loadGatheLogo();

  final doc = pw.Document(theme: theme);

  pw.Widget sectionHeader(String label) => pw.Padding(
        padding: const pw.EdgeInsets.only(top: 16, bottom: 5),
        child: pw.Column(
          crossAxisAlignment: pw.CrossAxisAlignment.start,
          children: [
            pw.Text(
              label.toUpperCase(),
              style: pw.TextStyle(
                color: _blue,
                fontSize: 10.5,
                fontWeight: pw.FontWeight.bold,
                letterSpacing: 0.3,
              ),
            ),
            pw.SizedBox(height: 3),
            pw.Container(height: 0.5, color: _panelBorder),
          ],
        ),
      );

  pw.Widget row(RecuLine l) => pw.Padding(
        padding: const pw.EdgeInsets.symmetric(vertical: 4.5),
        child: pw.Row(
          mainAxisAlignment: pw.MainAxisAlignment.spaceBetween,
          crossAxisAlignment: pw.CrossAxisAlignment.start,
          children: [
            pw.Expanded(
              child: pw.Text(
                l.label,
                style: const pw.TextStyle(color: _muted, fontSize: 9.5),
              ),
            ),
            pw.SizedBox(width: 16),
            pw.Text(
              l.value,
              style: pw.TextStyle(
                color: _ink,
                fontSize: l.emphasize ? 11.5 : 10.5,
                fontWeight:
                    l.emphasize ? pw.FontWeight.bold : pw.FontWeight.normal,
              ),
            ),
          ],
        ),
      );

  doc.addPage(
    pw.Page(
      pageTheme: pw.PageTheme(
        pageFormat: PdfPageFormat.a4,
        margin: const pw.EdgeInsets.only(
          left: 40,
          right: 40,
          top: gatheHeaderMargin + 14,
          bottom: gatheFooterMargin + 14,
        ),
        buildBackground: (context) => gatheLetterheadBackground(logo),
      ),
      build: (context) => pw.Column(
        crossAxisAlignment: pw.CrossAxisAlignment.start,
        children: [
          // Titre centré + référence.
          pw.Center(
            child: pw.Text(
              d.title.toUpperCase(),
              style: pw.TextStyle(
                color: _ink,
                fontSize: 14,
                fontWeight: pw.FontWeight.bold,
              ),
            ),
          ),
          pw.SizedBox(height: 3),
          pw.Center(
            child: pw.Text(
              '${d.receiptRef} · ${d.issuedOn}',
              style: const pw.TextStyle(color: _muted, fontSize: 9.5),
            ),
          ),
          pw.SizedBox(height: 6),
          // Bloc MEMBRE.
          sectionHeader('Membre'),
          row(RecuLine('Nom complet', d.memberName, emphasize: true)),
          row(RecuLine('N° membre', d.memberNumber)),
          pw.SizedBox(height: 14),
          // Panneau MONTANT mis en valeur.
          pw.Container(
            width: double.infinity,
            padding:
                const pw.EdgeInsets.symmetric(horizontal: 16, vertical: 14),
            decoration: pw.BoxDecoration(
              color: _panelBg,
              borderRadius: pw.BorderRadius.circular(8),
              border: pw.Border.all(color: _blue, width: 0.8),
            ),
            child: pw.Row(
              mainAxisAlignment: pw.MainAxisAlignment.spaceBetween,
              crossAxisAlignment: pw.CrossAxisAlignment.start,
              children: [
                pw.Column(
                  crossAxisAlignment: pw.CrossAxisAlignment.start,
                  children: [
                    pw.Text(
                      d.operationLabel.toUpperCase(),
                      style: pw.TextStyle(
                        color: _blue,
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
                        fontSize: 23,
                        fontWeight: pw.FontWeight.bold,
                      ),
                    ),
                  ],
                ),
                pw.Text(
                  'Statut : ${d.statusLabel}',
                  style: const pw.TextStyle(color: _muted, fontSize: 9.5),
                ),
              ],
            ),
          ),
          // Bloc DÉTAILS.
          sectionHeader('Détails de l\'opération'),
          ...d.lines.map(row),
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
