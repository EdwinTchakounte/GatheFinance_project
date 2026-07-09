import 'package:flutter/material.dart';

import '../../app/theme/app_colors.dart';
import '../../app/theme/app_radii.dart';

enum LogoSize { tiny, small, medium, large, hero }

/// Affichage du wordmark officiel GATHE Finance.
///
/// Utilise `logo_clean.png` (version détourée, fond blanc retiré) pour que le
/// logo **flotte** sur le fond de l'écran sans rectangle blanc visible . bien
/// plus doux qu'un JPG cru.
class LogoMark extends StatelessWidget {
  const LogoMark({super.key, this.size = LogoSize.medium, this.semanticsLabel});

  final LogoSize size;
  final String? semanticsLabel;

  double get _height {
    switch (size) {
      case LogoSize.tiny:
        return 20;
      case LogoSize.small:
        return 28;
      case LogoSize.medium:
        return 40;
      case LogoSize.large:
        return 56;
      case LogoSize.hero:
        return 80;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Semantics(
      label: semanticsLabel ?? 'GATHE Finance',
      image: true,
      child: Image.asset(
        'assets/images/logo_clean.png',
        height: _height,
        fit: BoxFit.contain,
        filterQuality: FilterQuality.high,
      ),
    );
  }
}


/// Variante « pastille » : logo détouré dans une pastille soft cream/paper
/// arrondie avec ombre cobalt légère. Utilisée dans les headers (Home,
/// Login). Désormais sans rectangle blanc visible . fond paper-bordé
/// pour donner du contraste sans dureté.
class LogoBadge extends StatelessWidget {
  const LogoBadge({super.key, this.size = LogoSize.small});

  final LogoSize size;

  @override
  Widget build(BuildContext context) {
    final outer = switch (size) {
      LogoSize.tiny => 32.0,
      LogoSize.small => 44.0,
      LogoSize.medium => 56.0,
      LogoSize.large => 72.0,
      LogoSize.hero => 96.0,
    };
    final padding = outer * 0.18;
    return Container(
      width: outer,
      height: outer,
      decoration: BoxDecoration(
        color: AppColors.paper,
        borderRadius: BorderRadius.all(Radius.circular(outer * 0.32)),
        border: Border.all(
          color: AppColors.cobalt.withValues(alpha: 0.06),
          width: 1,
        ),
        boxShadow: [
          BoxShadow(
            color: AppColors.cobalt.withValues(alpha: 0.10),
            blurRadius: 16,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      padding: EdgeInsets.all(padding),
      child: ClipRRect(
        borderRadius: const BorderRadius.all(AppRadii.r8),
        child: Image.asset(
          'assets/images/logo_clean.png',
          fit: BoxFit.contain,
        ),
      ),
    );
  }
}
