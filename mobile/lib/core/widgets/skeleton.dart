import 'package:flutter/material.dart';
import 'package:shimmer/shimmer.dart';

/// Placeholder shimmer pour les états de chargement . préfère ça aux spinners
/// quand la forme du contenu est prévisible.
class Skeleton extends StatelessWidget {
  const Skeleton({
    super.key,
    this.width,
    this.height = 14,
    this.borderRadius = 8,
  });

  final double? width;
  final double height;
  final double borderRadius;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Shimmer.fromColors(
      baseColor: scheme.outline.withValues(alpha: 0.5),
      highlightColor: scheme.surface,
      period: const Duration(milliseconds: 1400),
      child: Container(
        width: width,
        height: height,
        decoration: BoxDecoration(
          color: scheme.outline.withValues(alpha: 0.6),
          borderRadius: BorderRadius.circular(borderRadius),
        ),
      ),
    );
  }
}

/// Bloc skeleton avec plusieurs lignes . pour une « ligne de liste ».
class SkeletonList extends StatelessWidget {
  const SkeletonList({super.key, this.lines = 3, this.spacing = 12});

  final int lines;
  final double spacing;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: List.generate(lines, (i) {
        final widthFactor = i.isEven ? 0.95 : 0.7;
        return Padding(
          padding: EdgeInsets.only(bottom: i == lines - 1 ? 0 : spacing),
          child: FractionallySizedBox(
            widthFactor: widthFactor,
            child: const Skeleton(),
          ),
        );
      }),
    );
  }
}
