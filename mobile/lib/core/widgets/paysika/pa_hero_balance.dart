import 'package:flutter/material.dart';

import '../../../app/theme/paysika/pa_colors.dart';
import '../../../app/theme/paysika/pa_typography.dart';
import '../../formatters/xaf_formatter.dart';
import 'pa_sparkline.dart';

/// Hero balance Paysika — signature visuelle de la home.
///
/// Card avec **gradient diagonal aurore** (teal bas-gauche → navy haut-droite),
/// halo blanc soft top-right, contenu :
///   - eyebrow "Solde épargne" + icône œil pour show/hide
///   - solde 36pt bold blanc, peut être masqué (••• ••• XAF)
///   - lien sub "Voir les opérations en attente ↓" optionnel
///   - bouton CTA pill cyan vif à droite "+ Verser"
///
/// Reproduction fidèle du hero balance Paysika observé dans capture_paysika/.
class PaHeroBalance extends StatefulWidget {
  const PaHeroBalance({
    super.key,
    required this.amount,
    required this.onDeposit,
    this.label = 'Solde épargne',
    this.ctaLabel = 'Verser',
    this.pendingLabel,
    this.onPendingTap,
    this.onRequestReveal,
    this.trend,
    this.deltaLabel,
    this.deltaPositive = true,
  });

  final num amount;
  final VoidCallback onDeposit;
  final String label;
  final String ctaLabel;

  /// Série de soldes (ancien → récent) pour la mini-courbe de tendance.
  /// `null` ou < 2 points → pas de courbe.
  final List<num>? trend;

  /// Libellé du delta affiché en chip (ex. "+2,3 % ce mois"). `null` = caché.
  final String? deltaLabel;
  final bool deltaPositive;

  /// Sous-ligne optionnelle "Voir les opérations en attente" — null = caché.
  final String? pendingLabel;
  final VoidCallback? onPendingTap;

  /// Appelé quand le membre demande à révéler le solde masqué. Doit retourner
  /// `true` si l'accès est autorisé (PIN correct). Si null, le solde se révèle
  /// directement sans contrôle.
  final Future<bool> Function()? onRequestReveal;

  @override
  State<PaHeroBalance> createState() => _PaHeroBalanceState();
}

class _PaHeroBalanceState extends State<PaHeroBalance> {
  // Solde masqué par défaut (Règlement de confidentialité interne).
  bool _hidden = true;

  // Valeur de départ du count-up : 0 à la révélation, ancien montant après un
  // dépôt. La balance « se stabilise » en montant (sensation premium).
  double _shownValue = 0;

  Future<void> _toggle() async {
    if (!_hidden) {
      setState(() => _hidden = true);
      return;
    }
    // Demande de révélation → contrôle PIN si fourni.
    if (widget.onRequestReveal != null) {
      final ok = await widget.onRequestReveal!();
      if (ok && mounted) setState(() { _shownValue = 0; _hidden = false; });
    } else {
      setState(() { _shownValue = 0; _hidden = false; });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        gradient: PaGradients.heroAurore,
        borderRadius: BorderRadius.circular(14),
        // Ombre colorée profonde — donne le « flotte sur la page » premium.
        boxShadow: [
          BoxShadow(
            color: PaColors.blue.withValues(alpha: 0.22),
            blurRadius: 32,
            offset: const Offset(0, 14),
            spreadRadius: -6,
          ),
          BoxShadow(
            color: PaColors.navy.withValues(alpha: 0.18),
            blurRadius: 18,
            offset: const Offset(0, 6),
            spreadRadius: -4,
          ),
        ],
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(14),
        child: Stack(
          children: [
            // Halo blanc top-right — profondeur premium signature.
            Positioned(
              top: -50,
              right: -40,
              child: IgnorePointer(
                child: Container(
                  width: 220,
                  height: 220,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    gradient: RadialGradient(
                      colors: [
                        Colors.white.withValues(alpha: 0.22),
                        Colors.white.withValues(alpha: 0),
                      ],
                    ),
                  ),
                ),
              ),
            ),
            // Highlight diagonal top-left — touche glassmorphism subtile.
            Positioned(
              top: -20,
              left: -30,
              child: IgnorePointer(
                child: Container(
                  width: 140,
                  height: 140,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    gradient: RadialGradient(
                      colors: [
                        Colors.white.withValues(alpha: 0.12),
                        Colors.white.withValues(alpha: 0),
                      ],
                    ),
                  ),
                ),
              ),
            ),
            // Filet horizontal subtil — séparation visuelle premium.
            Positioned(
              left: 0,
              right: 0,
              bottom: 60,
              child: IgnorePointer(
                child: Container(
                  height: 1,
                  decoration: BoxDecoration(
                    gradient: LinearGradient(
                      colors: [
                        Colors.white.withValues(alpha: 0),
                        Colors.white.withValues(alpha: 0.15),
                        Colors.white.withValues(alpha: 0),
                      ],
                    ),
                  ),
                ),
              ),
            ),

            // Courbe de tendance — bande basse subtile derrière le contenu.
            if (!_hidden && (widget.trend?.length ?? 0) >= 2)
              Positioned(
                left: 0,
                right: 0,
                bottom: 0,
                height: 66,
                child: IgnorePointer(
                  child: PaSparkline(values: widget.trend!),
                ),
              ),

            Padding(
              padding: const EdgeInsets.fromLTRB(20, 18, 20, 18),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Eyebrow + œil + CTA
                  Row(
                    children: [
                      Expanded(
                        child: Row(
                          children: [
                            Text(
                              widget.label,
                              style: const TextStyle(
                                color: Colors.white,
                                fontSize: 13,
                                fontWeight: FontWeight.w500,
                              ),
                            ),
                            const SizedBox(width: 8),
                            InkWell(
                              customBorder: const CircleBorder(),
                              onTap: _toggle,
                              child: Padding(
                                padding: const EdgeInsets.all(4),
                                child: Icon(
                                  _hidden
                                      ? Icons.visibility_off_outlined
                                      : Icons.visibility_outlined,
                                  color: Colors.white.withValues(alpha: 0.9),
                                  size: 18,
                                ),
                              ),
                            ),
                          ],
                        ),
                      ),
                      // CTA pill cyan vif
                      _DepositPill(
                        label: widget.ctaLabel,
                        onTap: widget.onDeposit,
                      ),
                    ],
                  ),
                  const SizedBox(height: 14),

                  // Solde principal — Sora bold, count-up animé à la révélation.
                  _hidden
                      ? Text(
                          '… … XAF',
                          style: PaText.amount(
                            size: 34,
                            weight: FontWeight.w700,
                            color: Colors.white,
                            height: 1.05,
                          ),
                        )
                      : TweenAnimationBuilder<double>(
                          tween: Tween<double>(
                            begin: _shownValue,
                            end: widget.amount.toDouble(),
                          ),
                          duration: const Duration(milliseconds: 800),
                          curve: Curves.easeOutCubic,
                          onEnd: () => _shownValue = widget.amount.toDouble(),
                          builder: (context, value, _) => Text(
                            XAFFormatter.format(value.round()),
                            style: PaText.amount(
                              size: 34,
                              weight: FontWeight.w700,
                              color: Colors.white,
                              height: 1.05,
                            ),
                          ),
                        ),

                  // Delta du mois — petit chip translucide (craft premium).
                  if (!_hidden && widget.deltaLabel != null) ...[
                    const SizedBox(height: 10),
                    _DeltaChip(
                      label: widget.deltaLabel!,
                      positive: widget.deltaPositive,
                    ),
                  ],

                  // Pending optional
                  if (widget.pendingLabel != null) ...[
                    const SizedBox(height: 8),
                    InkWell(
                      onTap: widget.onPendingTap,
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Text(
                            widget.pendingLabel!,
                            style: TextStyle(
                              color: Colors.white.withValues(alpha: 0.85),
                              fontSize: 13,
                              fontWeight: FontWeight.w500,
                            ),
                          ),
                          const SizedBox(width: 4),
                          Icon(
                            Icons.keyboard_arrow_down_rounded,
                            size: 18,
                            color: Colors.white.withValues(alpha: 0.85),
                          ),
                        ],
                      ),
                    ),
                  ],
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}


/// Petit chip de variation mensuelle, posé sur le gradient hero.
class _DeltaChip extends StatelessWidget {
  const _DeltaChip({required this.label, required this.positive});

  final String label;
  final bool positive;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 4),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.16),
        borderRadius: BorderRadius.circular(999),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(
            positive
                ? Icons.trending_up_rounded
                : Icons.trending_down_rounded,
            size: 14,
            color: Colors.white,
          ),
          const SizedBox(width: 5),
          Text(
            label,
            style: const TextStyle(
              color: Colors.white,
              fontSize: 12,
              fontWeight: FontWeight.w700,
            ),
          ),
        ],
      ),
    );
  }
}


class _DepositPill extends StatelessWidget {
  const _DepositPill({required this.label, required this.onTap});

  final String label;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(999),
        child: Container(
          decoration: BoxDecoration(
            gradient: PaGradients.ctaPill,
            borderRadius: BorderRadius.circular(999),
          ),
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 9),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.add_rounded, color: PaColors.onTeal, size: 16),
              const SizedBox(width: 4),
              Text(
                label,
                style: const TextStyle(
                  color: PaColors.onTeal,
                  fontSize: 13.5,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
