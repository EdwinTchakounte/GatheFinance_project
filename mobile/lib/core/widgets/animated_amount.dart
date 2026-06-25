import 'package:flutter/material.dart';

import 'amount_text.dart';

/// Variante d'`AmountText` qui **anime le passage** d'une valeur à l'autre
/// (count-up classique). Idéal pour les hero numbers (solde épargne après
/// dépôt, solde restant après remboursement).
///
/// Tween linéaire sur la valeur numérique, courbe `easeOutCubic` pour rendre
/// le mouvement décéléré (sensation premium « la balance se stabilise »).
class AnimatedAmount extends StatefulWidget {
  const AnimatedAmount(
    this.amount, {
    super.key,
    this.size = AmountSize.medium,
    this.color,
    this.unitColor,
    this.showUnit = true,
    this.duration = const Duration(milliseconds: 800),
    this.curve = Curves.easeOutCubic,
  });

  final num amount;
  final AmountSize size;
  final Color? color;
  final Color? unitColor;
  final bool showUnit;
  final Duration duration;
  final Curve curve;

  @override
  State<AnimatedAmount> createState() => _AnimatedAmountState();
}

class _AnimatedAmountState extends State<AnimatedAmount> {
  // Valeur de départ pour le prochain tween . la valeur courante affichée.
  late num _displayed = widget.amount;

  @override
  void didUpdateWidget(covariant AnimatedAmount old) {
    super.didUpdateWidget(old);
    if (widget.amount != old.amount) {
      // Le `TweenAnimationBuilder` redémarre depuis `_displayed` (ancien) vers
      // `widget.amount` (nouveau) grâce à `tween: Tween(begin: _displayed, ...)`.
    }
  }

  @override
  Widget build(BuildContext context) {
    return TweenAnimationBuilder<double>(
      tween: Tween<double>(
        begin: _displayed.toDouble(),
        end: widget.amount.toDouble(),
      ),
      duration: widget.duration,
      curve: widget.curve,
      onEnd: () => _displayed = widget.amount,
      builder: (context, value, _) {
        return AmountText(
          value,
          size: widget.size,
          color: widget.color,
          unitColor: widget.unitColor,
          showUnit: widget.showUnit,
        );
      },
    );
  }
}
