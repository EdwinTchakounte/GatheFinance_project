import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../../../app/theme/paysika/pa_colors.dart';
import '../../../../app/theme/paysika/pa_typography.dart';

/// Pavé numérique PIN — refonte soft 2026-06-18.
///
/// - Chaque touche est un cercle fond `paper` avec hairline subtil, ombre
///   très douce. Au tap : background teal 12% + scale 0.94 (animation
///   200 ms), puis retour. Pas de splash agressif.
/// - Chiffres en Sora w500 (allégés vs ancien w700).
/// - Empreinte + backspace : touches discrètes sans bordure pour ne pas
///   concurrencer les chiffres.
class PinKeypad extends StatelessWidget {
  const PinKeypad({
    super.key,
    required this.onDigit,
    required this.onBackspace,
    this.onBiometric,
  });

  final ValueChanged<int> onDigit;
  final VoidCallback onBackspace;
  final VoidCallback? onBiometric;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 32),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          for (final row in const [
            [1, 2, 3],
            [4, 5, 6],
            [7, 8, 9],
          ]) ...[
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                for (final d in row)
                  _DigitKey(digit: d, onTap: () => onDigit(d)),
              ],
            ),
            const SizedBox(height: 14),
          ],
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              _IconKey(
                icon: onBiometric == null ? null : Icons.fingerprint_rounded,
                tint: PaColors.teal,
                onTap: onBiometric,
                highlight: true, // bouton signature → fond teint teal
              ),
              _DigitKey(digit: 0, onTap: () => onDigit(0)),
              _IconKey(
                icon: Icons.backspace_outlined,
                tint: PaColors.inkSecondary,
                onTap: () {
                  HapticFeedback.selectionClick();
                  onBackspace();
                },
              ),
            ],
          ),
        ],
      ),
    );
  }
}


/// Touche chiffre : cercle paper + hairline + scale au tap.
class _DigitKey extends StatefulWidget {
  const _DigitKey({required this.digit, required this.onTap});

  final int digit;
  final VoidCallback onTap;

  @override
  State<_DigitKey> createState() => _DigitKeyState();
}

class _DigitKeyState extends State<_DigitKey> {
  bool _pressed = false;

  void _setPressed(bool v) => setState(() => _pressed = v);

  void _handleTap() {
    HapticFeedback.selectionClick();
    widget.onTap();
  }

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      behavior: HitTestBehavior.opaque,
      onTapDown: (_) => _setPressed(true),
      onTapUp: (_) {
        _setPressed(false);
        _handleTap();
      },
      onTapCancel: () => _setPressed(false),
      child: AnimatedScale(
        scale: _pressed ? 0.94 : 1.0,
        duration: const Duration(milliseconds: 120),
        curve: Curves.easeOutCubic,
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 180),
          width: 72,
          height: 72,
          decoration: BoxDecoration(
            color: _pressed
                ? PaColors.teal.withValues(alpha: 0.10)
                : PaColors.paper,
            shape: BoxShape.circle,
            border: Border.all(
              color: _pressed
                  ? PaColors.teal.withValues(alpha: 0.30)
                  : PaColors.line,
              width: 1,
            ),
            boxShadow: [
              BoxShadow(
                color: Colors.black.withValues(alpha: 0.04),
                blurRadius: 10,
                offset: const Offset(0, 4),
              ),
            ],
          ),
          alignment: Alignment.center,
          child: Text(
            '${widget.digit}',
            style: PaText.display(
              size: 26,
              weight: FontWeight.w500,
              color: PaColors.navy,
            ),
          ),
        ),
      ),
    );
  }
}


/// Touche icône (empreinte / backspace) — même DNA cercle que les chiffres
/// pour rester cohérent, mais icône teintée [tint]. `highlight: true`
/// rend la touche signature (fond teint soft, ombre teal) pour attirer
/// l'œil sur le bouton empreinte.
class _IconKey extends StatefulWidget {
  const _IconKey({
    required this.icon,
    required this.tint,
    required this.onTap,
    this.highlight = false,
  });

  final IconData? icon;
  final Color tint;
  final VoidCallback? onTap;
  final bool highlight;

  @override
  State<_IconKey> createState() => _IconKeyState();
}

class _IconKeyState extends State<_IconKey> {
  bool _pressed = false;

  void _setPressed(bool v) => setState(() => _pressed = v);

  @override
  Widget build(BuildContext context) {
    final disabled = widget.onTap == null || widget.icon == null;
    if (disabled) {
      return const SizedBox(width: 72, height: 72);
    }
    final baseBg = widget.highlight
        ? widget.tint.withValues(alpha: 0.10)
        : PaColors.paper;
    final pressedBg = widget.tint.withValues(alpha: 0.18);
    final baseBorder = widget.highlight
        ? widget.tint.withValues(alpha: 0.25)
        : PaColors.line;
    final pressedBorder = widget.tint.withValues(alpha: 0.45);

    return GestureDetector(
      behavior: HitTestBehavior.opaque,
      onTapDown: (_) => _setPressed(true),
      onTapUp: (_) {
        _setPressed(false);
        widget.onTap!();
      },
      onTapCancel: () => _setPressed(false),
      child: AnimatedScale(
        scale: _pressed ? 0.94 : 1.0,
        duration: const Duration(milliseconds: 120),
        curve: Curves.easeOutCubic,
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 180),
          width: 72,
          height: 72,
          decoration: BoxDecoration(
            color: _pressed ? pressedBg : baseBg,
            shape: BoxShape.circle,
            border: Border.all(
              color: _pressed ? pressedBorder : baseBorder,
              width: 1,
            ),
            boxShadow: widget.highlight
                ? [
                    BoxShadow(
                      color: widget.tint.withValues(alpha: 0.18),
                      blurRadius: 14,
                      offset: const Offset(0, 4),
                    ),
                  ]
                : [
                    BoxShadow(
                      color: Colors.black.withValues(alpha: 0.04),
                      blurRadius: 10,
                      offset: const Offset(0, 4),
                    ),
                  ],
          ),
          alignment: Alignment.center,
          child: Icon(widget.icon, color: widget.tint, size: 26),
        ),
      ),
    );
  }
}


/// Rangée de dots PIN — version soft 2026-06-18 : remplis = pastille teal
/// pleine, vides = cercle hairline, transitions douces.
class PinDots extends StatelessWidget {
  const PinDots({
    super.key,
    required this.length,
    required this.filled,
    this.error = false,
  });

  final int length;
  final int filled;
  final bool error;

  @override
  Widget build(BuildContext context) {
    final active = error ? PaColors.danger : PaColors.teal;
    return Row(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        for (var i = 0; i < length; i++)
          AnimatedContainer(
            duration: const Duration(milliseconds: 200),
            curve: Curves.easeOutCubic,
            margin: const EdgeInsets.symmetric(horizontal: 10),
            width: 12,
            height: 12,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: i < filled ? active : Colors.transparent,
              border: Border.all(
                color: i < filled
                    ? active
                    : PaColors.inkFaint.withValues(alpha: 0.8),
                width: 1.4,
              ),
              boxShadow: i < filled
                  ? [
                      BoxShadow(
                        color: active.withValues(alpha: 0.25),
                        blurRadius: 8,
                        offset: const Offset(0, 2),
                      ),
                    ]
                  : null,
            ),
          ),
      ],
    );
  }
}
