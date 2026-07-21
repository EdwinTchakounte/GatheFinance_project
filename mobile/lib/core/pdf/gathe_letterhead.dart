import 'dart:typed_data';

import 'package:flutter/services.dart' show rootBundle;
import 'package:pdf/pdf.dart';
import 'package:pdf/widgets.dart' as pw;

/// Papier en-tête officiel GATHE Finance pour les PDF générés côté mobile.
///
/// Reproduit fidèlement — mais NET — le papier à en-tête de la coopérative
/// (`docs/papier entête GATHE.docx`) : logo couleur centré, raison sociale en
/// gras, pastille d'immatriculation, filet tricolore PLEINE LARGEUR, et bandeau
/// bleu de contacts PLEINE LARGEUR avec icônes. Miroir du module backend
/// `apps_coop/pdf_letterhead.py` (mêmes couleurs, même layout) pour une seule
/// famille de documents.
///
/// Les bandes vont de bord à bord : header/footer/filigrane sont posés en
/// `buildBackground` d'un `PageTheme` (via `FullPage(ignoreMargins: true)`),
/// et le contenu vit dans les marges réservées. Voir [gatheHeaderMargin] /
/// [gatheFooterMargin] pour les hauteurs à réserver.

// --- Couleurs de marque RÉELLES (relevées PIL sur le papier en-tête) --------
const gatheBlue = PdfColor.fromInt(0xFF004CA4); // bleu du logo + bandeau pied
const gatheGreen = PdfColor.fromInt(0xFF13820E); // vert foncé du logo (plus de vif)
const gatheGreenDark = PdfColor.fromInt(0xFF13820E); // vert foncé (segment central)
const gathePillGreen = PdfColor.fromInt(0xFF13820E); // pastille immatriculation (vert foncé)
const gatheHeaderBg = PdfColor.fromInt(0xFFF0F4F3); // fond très clair en-tête

// Hauteurs à réserver dans les marges de page pour ne pas chevaucher les bandes.
const double gatheHeaderMargin = 128;
const double gatheFooterMargin = 58;

const _coopTitle = "SOCIÉTÉ COOPÉRATIVE D'EPARGNE ET DE CRÉDIT";
const _coopImmat =
    'IMATRICULÉE SOUS LE N°24/046/CMR/LT/01/001/CCA/036004/036 004 000';

// Contacts (un item = icône + texte).
const _phone1 = '+237 233 424 847';
const _phone2 = '+237 676 887 686';
const _email = 'contact@gathe-finance.com';
const _web = 'www.gathe-finance.com';
const _nui = 'NUI : N°M062416925084G';
const _bp = 'B.P. : 7761 - Douala';
const _addr = 'Akwa - Douala Bercy (20m de Santa Lucia)';

/// Charge le logo couleur bundlé (offline).
Future<pw.MemoryImage> loadGatheLogo() async {
  final data = await rootBundle.load('assets/images/logo_clean.png');
  return pw.MemoryImage(data.buffer.asUint8List());
}

/// Filet tricolore (bande de transition) bleu / vert foncé / vert vif ≈ 40/30/30.
pw.Widget gatheTricolorRule({double height = 3}) => pw.Row(
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

// =========================================================================
//  Icônes vectorielles blanches (footer) — dessinées via CustomPaint, nettes
// =========================================================================
pw.Widget _glyph(void Function(PdfGraphics, double) draw, {double size = 9.5}) =>
    pw.SizedBox(
      width: size,
      height: size,
      child: pw.CustomPaint(
        size: PdfPoint(size, size),
        painter: (canvas, sz) => draw(canvas, sz.x),
      ),
    );

void _paintPhone(PdfGraphics g, double s) {
  final cx = s / 2, cy = s / 2;
  final w = s * 0.60, h = s;
  g
    ..setStrokeColor(PdfColors.white)
    ..setLineWidth(0.9)
    ..setLineCap(PdfLineCap.round)
    ..drawRRect(cx - w / 2, cy - h / 2, w, h, s * 0.12, s * 0.12)
    ..strokePath()
    ..drawLine(cx - w * 0.16, cy + h * 0.33, cx + w * 0.16, cy + h * 0.33)
    ..strokePath()
    ..setFillColor(PdfColors.white)
    ..drawEllipse(cx, cy - h * 0.32, s * 0.055, s * 0.055)
    ..fillPath();
}

void _paintMail(PdfGraphics g, double s) {
  final cx = s / 2, cy = s / 2;
  final w = s * 1.18, h = s * 0.80;
  g
    ..setStrokeColor(PdfColors.white)
    ..setLineWidth(0.9)
    ..setLineCap(PdfLineCap.round)
    ..drawRect(cx - w / 2, cy - h / 2, w, h)
    ..strokePath()
    ..drawLine(cx - w / 2, cy + h / 2, cx, cy - h * 0.04)
    ..strokePath()
    ..drawLine(cx + w / 2, cy + h / 2, cx, cy - h * 0.04)
    ..strokePath();
}

void _paintGlobe(PdfGraphics g, double s) {
  final cx = s / 2, cy = s / 2;
  final r = s * 0.5;
  g
    ..setStrokeColor(PdfColors.white)
    ..setLineWidth(0.9)
    ..setLineCap(PdfLineCap.round)
    ..drawEllipse(cx, cy, r, r)
    ..strokePath()
    ..drawEllipse(cx, cy, r * 0.46, r)
    ..strokePath()
    ..drawLine(cx - r, cy, cx + r, cy)
    ..strokePath();
}

void _paintPin(PdfGraphics g, double s) {
  final cx = s / 2, cy = s / 2;
  final r = s * 0.34;
  final top = cy + s * 0.16;
  g
    ..setFillColor(PdfColors.white)
    ..drawEllipse(cx, top, r, r)
    ..fillPath()
    ..moveTo(cx - r * 0.92, top - r * 0.30)
    ..lineTo(cx + r * 0.92, top - r * 0.30)
    ..lineTo(cx, cy - s * 0.5)
    ..closePath()
    ..fillPath()
    ..setFillColor(gatheBlue)
    ..drawEllipse(cx, top, r * 0.42, r * 0.42)
    ..fillPath();
}

pw.Widget _contactItem(
  void Function(PdfGraphics, double)? icon,
  String text, {
  bool bold = false,
}) =>
    pw.Row(
      mainAxisSize: pw.MainAxisSize.min,
      children: [
        if (icon != null) ...[
          _glyph(icon),
          pw.SizedBox(width: 3.5),
        ],
        pw.Text(
          text,
          style: pw.TextStyle(
            color: PdfColors.white,
            fontSize: 7.6,
            fontWeight: bold ? pw.FontWeight.bold : pw.FontWeight.normal,
          ),
        ),
      ],
    );

/// Intercale un point médian discret entre les items du pied, pour les
/// grouper visuellement (bloc centré) plutôt que de les étirer bord à bord.
List<pw.Widget> _joinWithDots(List<pw.Widget> items) {
  final out = <pw.Widget>[];
  for (var i = 0; i < items.length; i++) {
    if (i > 0) {
      out.add(
        pw.Padding(
          padding: const pw.EdgeInsets.symmetric(horizontal: 6),
          child: pw.Text(
            '•',
            style: const pw.TextStyle(
              color: PdfColor.fromInt(0x99FFFFFF),
              fontSize: 6,
            ),
          ),
        ),
      );
    }
    out.add(items[i]);
  }
  return out;
}

/// En-tête officiel PLEINE LARGEUR : fond gris, logo centré, raison sociale en
/// gras (auto-ajustée), pastille d'immatriculation, filet tricolore.
pw.Widget gatheLetterheadHeader(pw.MemoryImage logo) => pw.Container(
      color: gatheHeaderBg,
      padding: const pw.EdgeInsets.fromLTRB(16, 10, 16, 0),
      child: pw.Column(
        crossAxisAlignment: pw.CrossAxisAlignment.stretch,
        children: [
          pw.Center(child: pw.Image(logo, height: 46)),
          pw.SizedBox(height: 6),
          pw.Center(
            child: pw.FittedBox(
              child: pw.Text(
                _coopTitle,
                style: pw.TextStyle(
                  color: gatheBlue,
                  fontSize: 16,
                  fontWeight: pw.FontWeight.bold,
                ),
              ),
            ),
          ),
          pw.SizedBox(height: 5),
          pw.Center(
            child: pw.Container(
              padding:
                  const pw.EdgeInsets.symmetric(horizontal: 10, vertical: 3),
              decoration: pw.BoxDecoration(
                color: gathePillGreen,
                borderRadius: pw.BorderRadius.circular(9),
              ),
              child: pw.Text(
                _coopImmat,
                style: pw.TextStyle(
                  color: PdfColors.white,
                  fontSize: 7.5,
                  fontWeight: pw.FontWeight.bold,
                ),
              ),
            ),
          ),
          pw.SizedBox(height: 7),
          gatheTricolorRule(),
        ],
      ),
    );

/// Pied officiel PLEINE LARGEUR : filet tricolore + bandeau bleu de contacts
/// (chaque info précédée de son icône), sur 2 lignes justifiées.
pw.Widget gatheLetterheadFooter() => pw.Column(
      mainAxisSize: pw.MainAxisSize.min,
      crossAxisAlignment: pw.CrossAxisAlignment.stretch,
      children: [
        gatheTricolorRule(),
        pw.Container(
          color: gatheBlue,
          padding: const pw.EdgeInsets.fromLTRB(16, 6, 16, 6),
          child: pw.Column(
            children: [
              // Contacts groupés et CENTRÉS (au lieu d'être étirés bord à bord),
              // séparés par un point médian discret : bloc lisible d'un coup d'œil.
              pw.Row(
                mainAxisAlignment: pw.MainAxisAlignment.center,
                children: _joinWithDots([
                  _contactItem(_paintPhone, _phone1, bold: true),
                  _contactItem(_paintPhone, _phone2, bold: true),
                  _contactItem(_paintMail, _email, bold: true),
                  _contactItem(_paintGlobe, _web, bold: true),
                ]),
              ),
              pw.SizedBox(height: 3.5),
              pw.Row(
                mainAxisAlignment: pw.MainAxisAlignment.center,
                children: _joinWithDots([
                  _contactItem(null, _nui),
                  _contactItem(null, _bp),
                  _contactItem(_paintPin, _addr),
                ]),
              ),
            ],
          ),
        ),
      ],
    );

/// Fond de page complet (filigrane + en-tête + pied), PLEINE LARGEUR.
///
/// À passer à `PageTheme(buildBackground: ...)`. Réserver dans la marge de page
/// [gatheHeaderMargin] en haut et [gatheFooterMargin] en bas.
pw.Widget gatheLetterheadBackground(pw.MemoryImage logo) => pw.FullPage(
      ignoreMargins: true,
      child: pw.Stack(
        children: [
          gatheWatermark(logo),
          pw.Positioned(
            top: 0,
            left: 0,
            right: 0,
            child: gatheLetterheadHeader(logo),
          ),
          pw.Positioned(
            bottom: 0,
            left: 0,
            right: 0,
            child: gatheLetterheadFooter(),
          ),
        ],
      ),
    );

/// Filigrane logo centré très atténué (arrière-plan des documents).
pw.Widget gatheWatermark(pw.MemoryImage logo, {double width = 340}) =>
    pw.Positioned.fill(
      child: pw.Center(
        child: pw.Opacity(opacity: 0.05, child: pw.Image(logo, width: width)),
      ),
    );

/// Utilitaire : bytes du logo (si un appelant en a besoin séparément).
Future<Uint8List> gatheLogoBytes() async {
  final data = await rootBundle.load('assets/images/logo_clean.png');
  return data.buffer.asUint8List();
}
