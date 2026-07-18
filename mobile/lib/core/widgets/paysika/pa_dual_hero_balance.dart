import 'package:flutter/material.dart';

import '../../../app/theme/paysika/pa_colors.dart';
import '../../../app/theme/paysika/pa_typography.dart';
import '../../formatters/xaf_formatter.dart';
import 'pa_sparkline.dart';

/// Slot d'un solde présenté dans le hero (épargne ou cotisation).
class PaHeroSlot {
  const PaHeroSlot({
    required this.amount,
    required this.label,
    required this.ctaLabel,
    required this.onDeposit,
    this.trend,
    this.deltaLabel,
    this.deltaPositive = true,
  });

  final num amount;
  final String label;
  final String ctaLabel;
  final VoidCallback onDeposit;
  final List<num>? trend;
  final String? deltaLabel;
  final bool deltaPositive;
}

/// Hero balance **dual** . gradient aurore signature, contient un toggle
/// segmenté en haut (Épargne / Cotisations) qui switch l'affichage du
/// montant, du delta, du CTA et de la courbe.
///
/// Pensé pour être **pinned** au-dessus du scroll de la Home.
class PaDualHeroBalance extends StatefulWidget {
  const PaDualHeroBalance({
    super.key,
    required this.savings,
    required this.cotisation,
    this.savingsLabel = 'Épargne',
    this.cotisationLabel = 'Collectes',
    this.onRequestReveal,
  });

  final PaHeroSlot savings;
  final PaHeroSlot cotisation;
  final String savingsLabel;
  final String cotisationLabel;

  /// PIN gate optionnel avant révélation du solde masqué.
  final Future<bool> Function()? onRequestReveal;

  @override
  State<PaDualHeroBalance> createState() => _PaDualHeroBalanceState();
}

class _PaDualHeroBalanceState extends State<PaDualHeroBalance> {
  /// 0 = épargne, 1 = cotisation.
  int _index = 0;
  bool _hidden = true;
  double _shownValue = 0;

  PaHeroSlot get _current => _index == 0 ? widget.savings : widget.cotisation;

  Future<void> _toggleHidden() async {
    if (!_hidden) {
      setState(() => _hidden = true);
      return;
    }
    if (widget.onRequestReveal != null) {
      final ok = await widget.onRequestReveal!();
      if (ok && mounted) setState(() { _shownValue = 0; _hidden = false; });
    } else {
      setState(() { _shownValue = 0; _hidden = false; });
    }
  }

  void _selectTab(int i) {
    if (i == _index) return;
    setState(() {
      _index = i;
      _shownValue = 0; // re-anime le count-up quand on switch
    });
  }

  @override
  Widget build(BuildContext context) {
    final slot = _current;
    return Container(
      decoration: BoxDecoration(
        gradient: PaGradients.heroAurore,
        borderRadius: BorderRadius.circular(14),
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
            // Halo top-right
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
            // Highlight top-left
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
            // Sparkline subtle bottom band . bande plus fine pour alléger.
            if (!_hidden && (slot.trend?.length ?? 0) >= 2)
              Positioned(
                left: 0,
                right: 0,
                bottom: 0,
                height: 52,
                child: IgnorePointer(
                  child: PaSparkline(values: slot.trend!),
                ),
              ),
            Padding(
              padding: const EdgeInsets.fromLTRB(14, 12, 14, 12),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  // ── Toggle segmenté Épargne / Cotisations ──
                  Row(
                    children: [
                      Expanded(
                        child: _SegmentedToggle(
                          left: widget.savingsLabel,
                          right: widget.cotisationLabel,
                          index: _index,
                          onChanged: _selectTab,
                        ),
                      ),
                      const SizedBox(width: 8),
                      _EyeButton(
                        hidden: _hidden,
                        onTap: _toggleHidden,
                      ),
                    ],
                  ),
                  const SizedBox(height: 10),
                  // ── Label de slot + delta inline (hauteur constante) ──
                  // Le delta est sur la même ligne que le label pour ne pas
                  // faire varier la hauteur du hero selon le slot actif.
                  SizedBox(
                    height: 18,
                    child: Row(
                      children: [
                        Expanded(
                          child: Text(
                            slot.label,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: TextStyle(
                              color: Colors.white.withValues(alpha: 0.78),
                              fontSize: 11,
                              fontWeight: FontWeight.w500,
                              letterSpacing: 0.4,
                            ),
                          ),
                        ),
                        if (!_hidden && slot.deltaLabel != null)
                          _DeltaChip(
                            label: slot.deltaLabel!,
                            positive: slot.deltaPositive,
                          ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 4),
                  _hidden
                      ? Text(
                          '… … XAF',
                          style: PaText.amount(
                            size: 21,
                            weight: FontWeight.w700,
                            color: Colors.white,
                            height: 1.05,
                          ),
                        )
                      : TweenAnimationBuilder<double>(
                          tween: Tween<double>(
                            begin: _shownValue,
                            end: slot.amount.toDouble(),
                          ),
                          duration: const Duration(milliseconds: 700),
                          curve: Curves.easeOutCubic,
                          onEnd: () => _shownValue = slot.amount.toDouble(),
                          builder: (context, value, _) => Text(
                            XAFFormatter.format(value.round()),
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: PaText.amount(
                              size: 21,
                              weight: FontWeight.w700,
                              color: Colors.white,
                              height: 1.05,
                            ),
                          ),
                        ),
                  const SizedBox(height: 10),
                  // ── CTA pleine largeur (s'adapte au slot actif) ──
                  _CtaButton(label: slot.ctaLabel, onTap: slot.onDeposit),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _SegmentedToggle extends StatelessWidget {
  const _SegmentedToggle({
    required this.left,
    required this.right,
    required this.index,
    required this.onChanged,
  });

  final String left;
  final String right;
  final int index;
  final ValueChanged<int> onChanged;

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 28,
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.14),
        borderRadius: BorderRadius.circular(9),
      ),
      padding: const EdgeInsets.all(2.5),
      child: Row(
        children: [
          Expanded(child: _Pill(label: left, selected: index == 0, onTap: () => onChanged(0))),
          Expanded(child: _Pill(label: right, selected: index == 1, onTap: () => onChanged(1))),
        ],
      ),
    );
  }
}

class _Pill extends StatelessWidget {
  const _Pill({required this.label, required this.selected, required this.onTap});
  final String label;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 180),
        curve: Curves.easeOutCubic,
        decoration: BoxDecoration(
          color: selected ? Colors.white.withValues(alpha: 0.95) : Colors.transparent,
          borderRadius: BorderRadius.circular(7),
        ),
        alignment: Alignment.center,
        child: Text(
          label,
          style: TextStyle(
            color: selected ? PaColors.navy : Colors.white.withValues(alpha: 0.9),
            fontSize: 11,
            fontWeight: FontWeight.w700,
          ),
        ),
      ),
    );
  }
}

class _EyeButton extends StatelessWidget {
  const _EyeButton({required this.hidden, required this.onTap});
  final bool hidden;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      customBorder: const CircleBorder(),
      onTap: onTap,
      child: Container(
        width: 28,
        height: 28,
        decoration: BoxDecoration(
          color: Colors.white.withValues(alpha: 0.14),
          shape: BoxShape.circle,
        ),
        alignment: Alignment.center,
        child: Icon(
          hidden ? Icons.visibility_off_outlined : Icons.visibility_outlined,
          color: Colors.white.withValues(alpha: 0.95),
          size: 14,
        ),
      ),
    );
  }
}

class _DeltaChip extends StatelessWidget {
  const _DeltaChip({required this.label, required this.positive});
  final String label;
  final bool positive;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.16),
        borderRadius: BorderRadius.circular(7),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(
            positive ? Icons.trending_up_rounded : Icons.trending_down_rounded,
            size: 12,
            color: Colors.white,
          ),
          const SizedBox(width: 4),
          Text(
            label,
            style: const TextStyle(
              color: Colors.white,
              fontSize: 11,
              fontWeight: FontWeight.w700,
            ),
          ),
        ],
      ),
    );
  }
}

class _CtaButton extends StatelessWidget {
  const _CtaButton({required this.label, required this.onTap});
  final String label;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.transparent,
      borderRadius: BorderRadius.circular(10),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(10),
        child: Container(
          width: double.infinity,
          decoration: BoxDecoration(
            gradient: PaGradients.ctaPill,
            borderRadius: BorderRadius.circular(10),
          ),
          padding: const EdgeInsets.symmetric(vertical: 10, horizontal: 14),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.center,
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.add_rounded, color: PaColors.onTeal, size: 16),
              const SizedBox(width: 5),
              Text(
                label,
                style: const TextStyle(
                  color: PaColors.onTeal,
                  fontSize: 13,
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
