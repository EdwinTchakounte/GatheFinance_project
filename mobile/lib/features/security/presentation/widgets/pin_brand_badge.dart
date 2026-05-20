import 'package:flutter/material.dart';

import '../../../../app/theme/paysika/pa_colors.dart';
import '../../../../core/widgets/logo_mark.dart';

/// Logo entouré d'un halo dégradé vert→bleu — signature premium des écrans PIN.
class PinBrandBadge extends StatelessWidget {
  const PinBrandBadge({super.key, this.icon});

  /// Icône optionnelle (ex. cadenas) affichée à la place du logo.
  final IconData? icon;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 96,
      height: 96,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        gradient: PaGradients.heroAurore,
        boxShadow: [
          BoxShadow(
            color: PaColors.blue.withValues(alpha: 0.28),
            blurRadius: 28,
            offset: const Offset(0, 12),
            spreadRadius: -6,
          ),
        ],
      ),
      alignment: Alignment.center,
      child: Container(
        width: 76,
        height: 76,
        decoration: const BoxDecoration(
          shape: BoxShape.circle,
          color: PaColors.paper,
        ),
        alignment: Alignment.center,
        child: icon != null
            ? Icon(icon, color: PaColors.teal, size: 34)
            : const LogoMark(size: LogoSize.small),
      ),
    );
  }
}
