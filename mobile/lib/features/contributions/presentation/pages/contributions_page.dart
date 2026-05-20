import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_radii.dart';
import '../../../../app/theme/app_spacing.dart';
import '../../../../app/theme/app_typography.dart';
import '../../../../core/formatters/date_formatter.dart';
import '../../../../core/formatters/xaf_formatter.dart';
import '../../../../core/widgets/app_card.dart';
import '../../../../core/widgets/brand_background.dart';
import '../../../../core/widgets/skeleton.dart';
import '../../../../core/widgets/static_page_header.dart';
import '../../../../l10n/gen/app_localizations.dart';
import '../../domain/entities/contribution.dart';
import '../state/contributions_notifier.dart';

class ContributionsPage extends ConsumerWidget {
  const ContributionsPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(contributionsProvider);
    final total = ref.watch(totalContributionsValideesProvider);
    final l = AppL10n.of(context);
    final scheme = Theme.of(context).colorScheme;

    return Scaffold(
      body: BrandBackground(
        intensity: 0.55,
        child: SafeArea(
          bottom: false,
          child: Column(
            children: [
              StaticPageHeader(
                eyebrow: l.contrib_eyebrow,
                title: l.contrib_title,
              ),
              Expanded(
                child: RefreshIndicator.adaptive(
                  color: scheme.primary,
                  onRefresh: () =>
                      ref.read(contributionsProvider.notifier).refresh(),
                  child: CustomScrollView(
                    physics: const AlwaysScrollableScrollPhysics(),
                    slivers: [
                SliverPadding(
                  padding: const EdgeInsets.fromLTRB(
                    AppSpacing.screenH,
                    AppSpacing.m,
                    AppSpacing.screenH,
                    AppSpacing.xl,
                  ),
                  sliver: SliverToBoxAdapter(child: _TotalCard(total: total)),
                ),
                async.when(
                  data: (items) {
                    if (items.isEmpty) {
                      return const SliverFillRemaining(
                        hasScrollBody: false,
                        child: _EmptyState(),
                      );
                    }
                    final sorted = [...items]
                      ..sort((a, b) => b.date.compareTo(a.date));
                    return SliverPadding(
                      padding: const EdgeInsets.fromLTRB(
                        AppSpacing.screenH,
                        0,
                        AppSpacing.screenH,
                        AppSpacing.huge,
                      ),
                      sliver: SliverList.builder(
                        itemCount: sorted.length,
                        itemBuilder: (context, i) => _TimelineRow(
                          contribution: sorted[i],
                          isFirst: i == 0,
                          isLast: i == sorted.length - 1,
                        ),
                      ),
                    );
                  },
                  loading: () => const SliverToBoxAdapter(
                    child: Padding(
                      padding: EdgeInsets.symmetric(
                          horizontal: AppSpacing.screenH, vertical: 20),
                      child: SkeletonList(lines: 5),
                    ),
                  ),
                  error: (e, _) => SliverFillRemaining(
                    hasScrollBody: false,
                    child: _ErrorState(message: e.toString()),
                  ),
                ),
                    ],
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}


class _TotalCard extends StatelessWidget {
  const _TotalCard({required this.total});
  final num total;

  @override
  Widget build(BuildContext context) {
    final l = AppL10n.of(context);
    final scheme = Theme.of(context).colorScheme;
    return AppCard(
      hero: true,
      padding: const EdgeInsets.all(20),
      child: Row(
        children: [
          Container(
            width: 56,
            height: 56,
            decoration: BoxDecoration(
              color: scheme.primary.withValues(alpha: 0.12),
              borderRadius: const BorderRadius.all(AppRadii.r16),
            ),
            child: Icon(
              Icons.account_balance_wallet_outlined,
              color: scheme.primary,
              size: 26,
            ),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  l.contrib_total_label,
                  style: AppTypography.bodySmall.copyWith(
                    color: scheme.onSurface.withValues(alpha: 0.7),
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  XAFFormatter.format(total),
                  style: AppTypography.headingMedium.copyWith(
                    color: scheme.primary,
                    fontFeatures: const [FontFeature.tabularFigures()],
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}


class _TimelineRow extends StatelessWidget {
  const _TimelineRow({
    required this.contribution,
    required this.isFirst,
    required this.isLast,
  });

  final Contribution contribution;
  final bool isFirst;
  final bool isLast;

  @override
  Widget build(BuildContext context) {
    final l = AppL10n.of(context);
    final scheme = Theme.of(context).colorScheme;
    final meta = _metaFor(contribution.type, l);

    return IntrinsicHeight(
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          SizedBox(
            width: 32,
            child: Stack(
              alignment: Alignment.topCenter,
              children: [
                Positioned(
                  top: 0,
                  bottom: 0,
                  child: Container(
                    width: 2,
                    color: scheme.outline,
                  ),
                ),
                if (isFirst)
                  Positioned(
                    top: 0,
                    height: 18,
                    child: Container(width: 2, color: Colors.transparent),
                  ),
                if (isLast)
                  Positioned(
                    bottom: 0,
                    height: 18,
                    child: Container(width: 2, color: Colors.transparent),
                  ),
                Positioned(
                  top: 22,
                  child: Container(
                    width: 14,
                    height: 14,
                    decoration: BoxDecoration(
                      color: meta.tint,
                      shape: BoxShape.circle,
                      border: Border.all(color: scheme.surface, width: 3),
                    ),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(width: 6),
          Expanded(
            child: Padding(
              padding: const EdgeInsets.only(bottom: AppSpacing.m),
              child: AppCard(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Icon(meta.icon, size: 18, color: meta.tint),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Text(
                            meta.label,
                            style: AppTypography.labelLarge
                                .copyWith(color: scheme.onSurface),
                          ),
                        ),
                        _StatusBadge(status: contribution.statut),
                      ],
                    ),
                    const SizedBox(height: 10),
                    Row(
                      children: [
                        Text(
                          XAFFormatter.format(contribution.montant),
                          style: AppTypography.headingSmall.copyWith(
                            color: scheme.onSurface,
                            fontFeatures: const [FontFeature.tabularFigures()],
                          ),
                        ),
                        const Spacer(),
                        Text(
                          AppDateFormatter.long(contribution.date),
                          style: AppTypography.bodySmall.copyWith(
                            color: scheme.onSurface.withValues(alpha: 0.55),
                          ),
                        ),
                      ],
                    ),
                    if (contribution.reference != null) ...[
                      const SizedBox(height: 6),
                      Row(
                        children: [
                          Icon(
                            Icons.confirmation_number_outlined,
                            size: 13,
                            color: scheme.onSurface.withValues(alpha: 0.55),
                          ),
                          const SizedBox(width: 4),
                          Text(
                            l.contrib_ref(contribution.reference!),
                            style: AppTypography.monoSmall.copyWith(
                              color: scheme.onSurface.withValues(alpha: 0.55),
                              fontSize: 11.5,
                            ),
                          ),
                        ],
                      ),
                    ],
                  ],
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  ({IconData icon, Color tint, String label}) _metaFor(
      ContributionType t, AppL10n l) {
    switch (t) {
      case ContributionType.fraisInscription:
        return (
          icon: Icons.how_to_reg_outlined,
          tint: AppColors.emerald,
          label: l.contrib_type_inscription,
        );
      case ContributionType.fraisAdhesion:
        return (
          icon: Icons.diversity_3_rounded,
          tint: AppColors.cobalt,
          label: l.contrib_type_adhesion,
        );
      case ContributionType.fraisDemandeCredit:
        return (
          icon: Icons.account_balance_outlined,
          tint: AppColors.cobaltLight,
          label: l.contrib_type_credit_request,
        );
      case ContributionType.fraisReconduction:
        return (
          icon: Icons.refresh_rounded,
          tint: AppColors.terra,
          label: l.contrib_type_renewal,
        );
      case ContributionType.fraisCarnet:
        return (
          icon: Icons.menu_book_outlined,
          tint: AppColors.terraDark,
          label: l.contrib_type_booklet,
        );
    }
  }
}


class _StatusBadge extends StatelessWidget {
  const _StatusBadge({required this.status});
  final ContributionStatus status;

  @override
  Widget build(BuildContext context) {
    final l = AppL10n.of(context);
    final (label, bg, fg) = switch (status) {
      ContributionStatus.valide => (
          l.contrib_status_validated,
          AppColors.emeraldSurface,
          AppColors.emeraldDark,
        ),
      ContributionStatus.enAttente => (
          l.contrib_status_pending,
          AppColors.cobaltSurface,
          AppColors.cobalt,
        ),
      ContributionStatus.echec => (
          l.contrib_status_failed,
          AppColors.dangerSurface,
          AppColors.danger,
        ),
    };
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(20),
      ),
      child: Text(
        label,
        style: TextStyle(
          color: fg,
          fontSize: 11,
          fontWeight: FontWeight.w700,
          letterSpacing: 0.2,
        ),
      ),
    );
  }
}


class _EmptyState extends StatelessWidget {
  const _EmptyState();

  @override
  Widget build(BuildContext context) {
    final l = AppL10n.of(context);
    final scheme = Theme.of(context).colorScheme;
    return Padding(
      padding: const EdgeInsets.fromLTRB(
        AppSpacing.screenH,
        AppSpacing.huge,
        AppSpacing.screenH,
        AppSpacing.huge,
      ),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Container(
            width: 72,
            height: 72,
            decoration: BoxDecoration(
              color: scheme.surfaceContainerHighest,
              borderRadius: const BorderRadius.all(AppRadii.r24),
            ),
            alignment: Alignment.center,
            child: Icon(
              Icons.receipt_long_outlined,
              color: scheme.primary,
              size: 32,
            ),
          ),
          const SizedBox(height: 18),
          Text(
            l.contrib_empty_title,
            style: AppTypography.headingSmall.copyWith(color: scheme.onSurface),
          ),
          const SizedBox(height: 6),
          Text(
            l.contrib_empty_sub,
            textAlign: TextAlign.center,
            style: AppTypography.bodyMedium.copyWith(
              color: scheme.onSurface.withValues(alpha: 0.7),
            ),
          ),
        ],
      ),
    );
  }
}


class _ErrorState extends StatelessWidget {
  const _ErrorState({required this.message});
  final String message;

  @override
  Widget build(BuildContext context) {
    final l = AppL10n.of(context);
    final scheme = Theme.of(context).colorScheme;
    return Padding(
      padding: const EdgeInsets.fromLTRB(
        AppSpacing.screenH,
        AppSpacing.huge,
        AppSpacing.screenH,
        AppSpacing.huge,
      ),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const Icon(
            Icons.cloud_off_outlined,
            color: AppColors.terraDark,
            size: 36,
          ),
          const SizedBox(height: 10),
          Text(
            l.contrib_error_title,
            textAlign: TextAlign.center,
            style: AppTypography.headingSmall.copyWith(
              color: AppColors.terraDark,
            ),
          ),
          const SizedBox(height: 6),
          Text(
            message,
            textAlign: TextAlign.center,
            style: AppTypography.bodySmall.copyWith(
              color: scheme.onSurface.withValues(alpha: 0.55),
            ),
          ),
        ],
      ),
    );
  }
}
