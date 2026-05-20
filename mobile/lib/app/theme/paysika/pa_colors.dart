import 'package:flutter/material.dart';

/// Palette mobile premium — direction « luxury fintech » (vert émeraude + bleu).
///
/// Système hybride validé : palette **vert #00B894/#00C896 + bleu #2563EB/
/// #1E3A8A** (façon Wave/Revolut), fond **crème doodle** conservé comme
/// signature. Texte #111827 / #6B7280 (brief). Saturation douce, jamais
/// agressive.
///
/// Les noms historiques (`teal`, `navy`) sont conservés pour éviter de
/// toucher tous les widgets : `teal` = vert primaire, `navy` = bleu profond.
class PaColors {
  PaColors._();

  // ── Bleu profond (ex-"navy") — fin de gradient hero, accents foncés ──────
  /// Bleu nuit #1E3A8A — fin du gradient hero, accents profonds.
  static const navy = Color(0xFF1E3A8A);
  /// Bleu royal #2563EB — accent bleu vif (liens, états).
  static const blue = Color(0xFF2563EB);
  /// Variante plus profonde pour pressed / barriers.
  static const navyDeep = Color(0xFF172554);
  static const navySoft = Color(0xFF3B5BC0);

  // ── Vert émeraude (ex-"teal") — primaire, CTA, gradient ──────────────────
  /// Vert principal #00B894 — CTA, active states, début de gradient.
  static const teal = Color(0xFF00B894);
  /// Vert clair #00C896 — glows, début de gradient lumineux.
  static const tealLight = Color(0xFF00C896);
  /// Vert sombre — pressed states.
  static const tealDark = Color(0xFF009478);
  /// Fond très clair vert — cards icônes / surfaces accent.
  static const tealSurface = Color(0xFFE6F7F1);

  // ── Surfaces neutres ────────────────────────────────────────────────────
  /// Fond app neutre premium (brief #F7F8FA) — utilisé hors pages doodle.
  static const appBg = Color(0xFFF7F8FA);
  /// Canvas crème chaud — base du fond doodle texturé (signature conservée).
  static const canvas = Color(0xFFF2EFE8);
  /// Fond des cards soft.
  static const cardBg = Color(0xFFF4F6F9);
  /// Fond paper (cards primaires / modales) — blanc pur (brief #FFFFFF).
  static const paper = Color(0xFFFFFFFF);
  /// Séparateurs très subtils.
  static const line = Color(0xFFEAEDF1);

  // ── Texte (brief) ─────────────────────────────────────────────────────────
  static const inkPrimary = Color(0xFF111827); // titres / montants
  static const inkSecondary = Color(0xFF6B7280); // corps secondaire
  static const inkMuted = Color(0xFF9CA3AF);
  static const inkFaint = Color(0xFFC7CCD4);
  static const onTeal = Color(0xFFFFFFFF); // texte/icône blanc sur formes vertes
  static const onNavy = Color(0xFFE9EEFB); // texte sur fond bleu

  // ── États (tons doux, jamais saturés) ────────────────────────────────────
  static const success = Color(0xFF0E9F6E); // dépôts, intérêts crédités
  static const successSurface = Color(0xFFE3F5EE);
  static const danger = Color(0xFFE05252); // retraits, échecs (rouge doux)
  static const dangerSurface = Color(0xFFFCEAEA);
  static const warning = Color(0xFFE08A1E); // frais, alertes douces
  static const warningSurface = Color(0xFFFDF2E2);

  // ── Catégoriels (avatars de transaction) ────────────────────────────────
  static const catSuccess = Color(0xFF0E9F6E);
  static const catWarning = Color(0xFFE08A1E);
  static const catInfo = blue;
  static const catNeutral = Color(0xFF6B7280);
  static const catDanger = Color(0xFFE05252);
}


/// Gradients premium.
///
/// **heroAurore** : signature du hero balance — vert émeraude → bleu profond,
/// diagonale (façon carte bancaire haut-de-gamme).
class PaGradients {
  PaGradients._();

  /// Gradient hero balance — diagonal vert → bleu (bas-gauche → haut-droite).
  static const heroAurore = LinearGradient(
    begin: Alignment(-0.9, 0.9),
    end: Alignment(0.9, -0.9),
    colors: [
      PaColors.tealLight, // #00C896 vert lumineux
      PaColors.blue,      // #2563EB bleu royal
      PaColors.navy,      // #1E3A8A bleu nuit
    ],
    stops: [0.0, 0.55, 1.0],
  );

  /// CTA pill — gradient vert lumineux.
  static const ctaPill = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [PaColors.tealLight, PaColors.teal],
  );

  /// Surface card — **dégradé vert très bas + légèrement translucide**.
  /// Blanc (90 %) → vert pâle (86 %) : casse le « tout-blanc classique »,
  /// apporte une coloration verte et laisse le doodle crème respirer dessous.
  static final cardSoft = LinearGradient(
    begin: Alignment.topCenter,
    end: Alignment.bottomCenter,
    colors: [
      const Color(0xFFFFFFFF).withValues(alpha: 0.90),
      const Color(0xFFEAF7F1).withValues(alpha: 0.88), // vert pâle translucide
    ],
  );

  /// Variante plus marquée pour panneaux accent (toujours douce).
  static const surfaceMint = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [
      Color(0xFFF1FBF7),
      Color(0xFFE3F5EE),
    ],
  );
}
