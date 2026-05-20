import 'package:flutter/material.dart';

import '../../app/theme/app_typography.dart';

/// Sur-titre uppercase tracking large — emprunté au design web institutionnel.
class Eyebrow extends StatelessWidget {
  const Eyebrow(this.text, {super.key, this.color});

  final String text;
  final Color? color;

  @override
  Widget build(BuildContext context) {
    return Text(
      text.toUpperCase(),
      style: AppTypography.eyebrow.copyWith(color: color),
    );
  }
}
