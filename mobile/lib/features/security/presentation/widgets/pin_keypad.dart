import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../../../app/theme/paysika/pa_colors.dart';
import '../../../../app/theme/paysika/pa_typography.dart';

/// Pavé numérique PIN — style Paysika (gros chiffres navy sur fond clair).
///
/// Émet [onDigit] à chaque chiffre tapé et [onBackspace] sur la touche effacer.
class PinKeypad extends StatelessWidget {
  const PinKeypad({
    super.key,
    required this.onDigit,
    required this.onBackspace,
    this.onBiometric,
  });

  final ValueChanged<int> onDigit;
  final VoidCallback onBackspace;

  /// Si fourni, affiche une touche empreinte en bas-gauche du pavé.
  final VoidCallback? onBiometric;

  @override
  Widget build(BuildContext context) {
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        for (final row in const [
          [1, 2, 3],
          [4, 5, 6],
          [7, 8, 9],
        ])
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceEvenly,
            children: [for (final d in row) _Key(digit: d, onTap: () => onDigit(d))],
          ),
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceEvenly,
          children: [
            SizedBox(
              width: 84,
              height: 72,
              child: onBiometric == null
                  ? null
                  : InkWell(
                      customBorder: const CircleBorder(),
                      onTap: () {
                        HapticFeedback.selectionClick();
                        onBiometric!();
                      },
                      child: const Icon(
                        Icons.fingerprint_rounded,
                        color: PaColors.teal,
                        size: 30,
                      ),
                    ),
            ),
            _Key(digit: 0, onTap: () => onDigit(0)),
            SizedBox(
              width: 84,
              height: 72,
              child: InkWell(
                customBorder: const CircleBorder(),
                onTap: () {
                  HapticFeedback.selectionClick();
                  onBackspace();
                },
                child: const Icon(
                  Icons.backspace_outlined,
                  color: PaColors.navy,
                  size: 24,
                ),
              ),
            ),
          ],
        ),
      ],
    );
  }
}


class _Key extends StatelessWidget {
  const _Key({required this.digit, required this.onTap});

  final int digit;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: 84,
      height: 72,
      child: InkWell(
        customBorder: const CircleBorder(),
        onTap: () {
          HapticFeedback.selectionClick();
          onTap();
        },
        child: Center(
          child: Text(
            '$digit',
            style: PaText.display(size: 30, weight: FontWeight.w600, color: PaColors.navy),
          ),
        ),
      ),
    );
  }
}


/// Rangée de points indiquant la progression de saisie du PIN.
class PinDots extends StatelessWidget {
  const PinDots({super.key, required this.length, required this.filled, this.error = false});

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
            duration: const Duration(milliseconds: 150),
            margin: const EdgeInsets.symmetric(horizontal: 10),
            width: 14,
            height: 14,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: i < filled ? active : Colors.transparent,
              border: Border.all(
                color: i < filled ? active : PaColors.inkFaint,
                width: 1.6,
              ),
            ),
          ),
      ],
    );
  }
}
