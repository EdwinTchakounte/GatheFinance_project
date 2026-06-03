import 'package:flutter/material.dart';

import '../../../app/theme/paysika/pa_colors.dart';

/// Variante visuelle d'un [PaButton].
enum PaButtonVariant {
  /// Pill plein, gradient teal lumineux — action principale.
  primary,

  /// Pill contour, fond paper — action secondaire.
  outline,
}

/// Bouton pill premium unifié (Paysika).
///
/// Remplace les `FilledButton` cobalt (système institutionnel) et les
/// `_PrimaryActionButton` / `_OutlineActionButton` redéfinis localement page
/// par page. Hauteur 52 par défaut (cible tactile ≥48dp), radius pleine pille,
/// `Semantics(button:)` natif via `InkWell`.
class PaButton extends StatelessWidget {
  const PaButton({
    super.key,
    required this.label,
    required this.onPressed,
    this.variant = PaButtonVariant.primary,
    this.icon,
    this.fullWidth = true,
    this.loading = false,
    this.height = 52,
  });

  final String label;

  /// `null` ⇒ bouton désactivé (atténué, non tappable).
  final VoidCallback? onPressed;
  final PaButtonVariant variant;
  final IconData? icon;
  final bool fullWidth;
  final bool loading;
  final double height;

  @override
  Widget build(BuildContext context) {
    final disabled = onPressed == null || loading;
    final isPrimary = variant == PaButtonVariant.primary;
    final radius = BorderRadius.circular(999);

    final fg = isPrimary ? PaColors.onTeal : PaColors.inkPrimary;

    final content = loading
        ? SizedBox(
            width: 20,
            height: 20,
            child: CircularProgressIndicator(
              strokeWidth: 2.2,
              valueColor: AlwaysStoppedAnimation<Color>(fg),
            ),
          )
        : Row(
            mainAxisSize: fullWidth ? MainAxisSize.max : MainAxisSize.min,
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              if (icon != null) ...[
                Icon(icon, size: 19, color: fg),
                const SizedBox(width: 8),
              ],
              Flexible(
                child: Text(
                  label,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  textAlign: TextAlign.center,
                  style: TextStyle(
                    color: fg,
                    fontSize: 14.5,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ),
            ],
          );

    final decoration = isPrimary
        ? BoxDecoration(
            gradient: disabled ? null : PaGradients.ctaPill,
            color: disabled ? PaColors.inkFaint : null,
            borderRadius: radius,
          )
        : BoxDecoration(
            color: PaColors.paper,
            borderRadius: radius,
            border: Border.all(
              color: disabled ? PaColors.line : PaColors.teal,
              width: 1.4,
            ),
          );

    final button = Opacity(
      opacity: disabled && !loading ? 0.7 : 1,
      child: Material(
        color: Colors.transparent,
        borderRadius: radius,
        clipBehavior: Clip.antiAlias,
        child: Ink(
          decoration: decoration,
          child: InkWell(
            onTap: disabled ? null : onPressed,
            borderRadius: radius,
            child: Container(
              height: height,
              alignment: Alignment.center,
              padding: const EdgeInsets.symmetric(horizontal: 22),
              child: content,
            ),
          ),
        ),
      ),
    );

    return fullWidth ? SizedBox(width: double.infinity, child: button) : button;
  }
}
