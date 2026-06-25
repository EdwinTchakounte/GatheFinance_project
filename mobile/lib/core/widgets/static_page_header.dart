import 'package:flutter/material.dart';

import '../../app/theme/app_spacing.dart';
import '../../app/theme/app_typography.dart';
import 'eyebrow.dart';

/// Header de page **fixe** (non scrollable) . capsule glass.
///
/// Composition :
///   1. Pastille circulaire 40×40 pour le bouton retour (surface teintée
///      cobalt très douce) . plus tactile et premium que l'icône brute.
///   2. Eyebrow petit + titre `headingMedium` 22pt, `maxLines: 2` .
///      le titre ne se tronque plus brutalement, il s'enroule.
///   3. Filet doux cobalt 8 % en bas . sépare visuellement le header
///      du contenu scrollable sans peser.
///
/// S'utilise comme premier enfant d'une `Column`, le contenu scrollable
/// allant ensuite dans un `Expanded`.
class StaticPageHeader extends StatelessWidget {
  const StaticPageHeader({
    super.key,
    required this.eyebrow,
    required this.title,
    this.showBack = true,
    this.actions,
  });

  final String eyebrow;
  final String title;
  final bool showBack;
  final List<Widget>? actions;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return DecoratedBox(
      decoration: BoxDecoration(
        border: Border(
          bottom: BorderSide(
            color: scheme.primary.withValues(alpha: 0.08),
            width: 1,
          ),
        ),
      ),
      child: Padding(
        padding: const EdgeInsets.fromLTRB(
          AppSpacing.l,
          12,
          AppSpacing.l,
          14,
        ),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.center,
          children: [
            if (showBack) ...[
              const _CapsuleBackButton(),
              const SizedBox(width: 14),
            ],
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  Eyebrow(eyebrow),
                  const SizedBox(height: 6),
                  Text(
                    title,
                    maxLines: 2,
                    softWrap: true,
                    overflow: TextOverflow.ellipsis,
                    style: AppTypography.headingMedium.copyWith(
                      color: scheme.onSurface,
                      fontSize: 20,
                      fontWeight: FontWeight.w600,
                      height: 1.25,
                      letterSpacing: -0.2,
                    ),
                  ),
                ],
              ),
            ),
            if (actions != null) ...actions!,
          ],
        ),
      ),
    );
  }
}


/// Pastille circulaire 40×40 avec icône retour . surface très douce
/// (cobalt 8 %), ripple cobalt à l'appui. Plus tactile que l'IconButton
/// standard de Material.
class _CapsuleBackButton extends StatelessWidget {
  const _CapsuleBackButton();

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Material(
      color: scheme.primary.withValues(alpha: 0.08),
      shape: const CircleBorder(),
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        customBorder: const CircleBorder(),
        onTap: () => Navigator.of(context).maybePop(),
        splashColor: scheme.primary.withValues(alpha: 0.18),
        highlightColor: scheme.primary.withValues(alpha: 0.10),
        child: SizedBox(
          width: 40,
          height: 40,
          child: Icon(
            Icons.arrow_back_rounded,
            size: 20,
            color: scheme.onSurface.withValues(alpha: 0.85),
          ),
        ),
      ),
    );
  }
}


/// En-tête de page **racine** (onglet de bottom-nav) . sans bouton retour.
/// Même typographie que [StaticPageHeader] + filet doux en bas.
/// À utiliser sur les pages Home, Crédit, Carnet, Profil pour cohérence visuelle.
class RootPageHeader extends StatelessWidget {
  const RootPageHeader({
    super.key,
    required this.eyebrow,
    required this.title,
    this.actions,
  });

  final String eyebrow;
  final String title;
  final List<Widget>? actions;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return DecoratedBox(
      decoration: BoxDecoration(
        border: Border(
          bottom: BorderSide(
            color: scheme.primary.withValues(alpha: 0.08),
            width: 1,
          ),
        ),
      ),
      child: Padding(
        padding: const EdgeInsets.fromLTRB(
          AppSpacing.l,
          AppSpacing.m,
          AppSpacing.l,
          14,
        ),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.center,
          children: [
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  Eyebrow(eyebrow),
                  const SizedBox(height: 6),
                  Text(
                    title,
                    maxLines: 2,
                    softWrap: true,
                    overflow: TextOverflow.ellipsis,
                    style: AppTypography.headingMedium.copyWith(
                      color: scheme.onSurface,
                      fontSize: 24,
                      fontWeight: FontWeight.w600,
                      height: 1.2,
                      letterSpacing: -0.3,
                    ),
                  ),
                ],
              ),
            ),
            if (actions != null) ...actions!,
          ],
        ),
      ),
    );
  }
}

