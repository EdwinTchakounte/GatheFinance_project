import 'dart:typed_data';

import 'package:flutter/services.dart' show rootBundle;
import 'package:pdf/pdf.dart';
import 'package:pdf/widgets.dart' as pw;

/// Papier en-tête officiel GATHE Finance pour les PDF générés côté mobile.
///
/// Reproduit fidèlement le papier à en-tête de la coopérative (logo couleur,
/// raison sociale, immatriculation, filet tricolore, bandeau bleu de contacts)
/// aux VRAIES couleurs du logo. Miroir du module backend
/// `apps_coop/pdf_letterhead.py` pour une seule famille de documents.

// --- Couleurs de marque réelles (relevées sur le logo/papier en-tête) ------
const gatheBlue = PdfColor.fromInt(0xFF0747FF); // bleu vif du logo + bandeau
const gatheGreen = PdfColor.fromInt(0xFF33CC00); // vert vif (filet droit)
const gatheGreenDark = PdfColor.fromInt(0xFF14820E); // vert foncé (filet, texte)
const gatheHeaderBg = PdfColor.fromInt(0xFFF0F4F3); // fond très clair en-tête

const _coopTitle = "SOCIÉTÉ COOPÉRATIVE D'EPARGNE ET DE CRÉDIT";
const _coopImmat =
    'Immatriculée sous le N°24/046/CMR/LT/01/001/CCA/036004/036 004 000';
const _contactLine1 =
    'Tél : +237 233 424 847     Mob : +237 676 887 686     '
    'Email : contact@gathe-finance.com     Web : www.gathe-finance.com';
const _contactLine2 =
    'NUI : N°M062416925084G     B.P. : 7761 - Douala     '
    'Akwa - Douala Bercy (20m de Santa Lucia)';

/// Charge le logo couleur bundlé (offline).
Future<pw.MemoryImage> loadGatheLogo() async {
  final data = await rootBundle.load('assets/images/logo_clean.png');
  return pw.MemoryImage(data.buffer.asUint8List());
}

/// Filet tricolore bleu / vert foncé / vert vif (comme le papier en-tête).
pw.Widget gatheTricolorRule({double height = 2.4}) => pw.Row(
      children: [
        pw.Expanded(
          flex: 40,
          child: pw.Container(height: height, color: gatheBlue),
        ),
        pw.Expanded(
          flex: 30,
          child: pw.Container(height: height, color: gatheGreenDark),
        ),
        pw.Expanded(
          flex: 30,
          child: pw.Container(height: height, color: gatheGreen),
        ),
      ],
    );

/// En-tête officiel : logo centré, raison sociale, pilule d'immatriculation,
/// filet tricolore.
pw.Widget gatheLetterheadHeader(pw.MemoryImage logo) => pw.Container(
      color: gatheHeaderBg,
      padding: const pw.EdgeInsets.fromLTRB(8, 10, 8, 0),
      child: pw.Column(
        crossAxisAlignment: pw.CrossAxisAlignment.stretch,
        children: [
          pw.Center(child: pw.Image(logo, height: 46)),
          pw.SizedBox(height: 6),
          pw.Center(
            child: pw.Text(
              _coopTitle,
              style: pw.TextStyle(
                color: gatheBlue,
                fontSize: 13,
                fontWeight: pw.FontWeight.bold,
              ),
            ),
          ),
          pw.SizedBox(height: 4),
          pw.Center(
            child: pw.Container(
              padding: const pw.EdgeInsets.symmetric(horizontal: 8, vertical: 2.5),
              decoration: pw.BoxDecoration(
                color: gatheGreenDark,
                borderRadius: pw.BorderRadius.circular(8),
              ),
              child: pw.Text(
                _coopImmat,
                style: const pw.TextStyle(color: PdfColors.white, fontSize: 7.5),
              ),
            ),
          ),
          pw.SizedBox(height: 6),
          gatheTricolorRule(),
        ],
      ),
    );

/// Pied officiel : filet tricolore + bandeau bleu pleine largeur de contacts.
pw.Widget gatheLetterheadFooter() => pw.Column(
      mainAxisSize: pw.MainAxisSize.min,
      crossAxisAlignment: pw.CrossAxisAlignment.stretch,
      children: [
        gatheTricolorRule(),
        pw.Container(
          color: gatheBlue,
          padding: const pw.EdgeInsets.symmetric(horizontal: 10, vertical: 6),
          child: pw.Column(
            children: [
              pw.Text(
                _contactLine1,
                textAlign: pw.TextAlign.center,
                style: pw.TextStyle(
                  color: PdfColors.white,
                  fontSize: 7.4,
                  fontWeight: pw.FontWeight.bold,
                ),
              ),
              pw.SizedBox(height: 3),
              pw.Text(
                _contactLine2,
                textAlign: pw.TextAlign.center,
                style: const pw.TextStyle(color: PdfColors.white, fontSize: 7.4),
              ),
            ],
          ),
        ),
      ],
    );

/// Filigrane logo centré très atténué (arrière-plan des documents).
pw.Widget gatheWatermark(pw.MemoryImage logo, {double width = 340}) =>
    pw.Positioned.fill(
      child: pw.Center(
        child: pw.Opacity(opacity: 0.06, child: pw.Image(logo, width: width)),
      ),
    );

/// Utilitaire : bytes du logo (si un appelant en a besoin séparément).
Future<Uint8List> gatheLogoBytes() async {
  final data = await rootBundle.load('assets/images/logo_clean.png');
  return data.buffer.asUint8List();
}
