import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../app/theme/paysika/pa_colors.dart';
import '../../../../app/theme/paysika/pa_typography.dart';
import '../../../../core/formatters/date_formatter.dart';
import '../../../../core/formatters/xaf_formatter.dart';
import '../../../../core/widgets/paysika/pa_card.dart';
import '../../../../core/widgets/paysika/pa_error_state.dart';
import '../../../../core/widgets/paysika/pa_pattern_background.dart';
import '../../../../core/widgets/skeleton.dart';
import '../../../../l10n/gen/app_localizations.dart';
import '../../domain/entities/contribution.dart';
import '../state/contributions_notifier.dart';

/// Page « Mes cotisations » . style **Paysika** (palette teal/navy, cards soft,
/// fond doodle). Timeline chronologique des frais payés.
class ContributionsPage extends ConsumerWidget {
  const ContributionsPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(contributionsProvider);
    final total = ref.watch(totalContributionsValideesProvider);
    final l = AppL10n.of(context);

    return Scaffold(
      backgroundColor: PaColors.canvas,
      body: PaPatternBackground(
        child: SafeArea(
          bottom: false,
          child: Column(
            children: [
              // Header inline Paysika (back + eyebrow + titre)
              Padding(
                padding: const EdgeInsets.fromLTRB(8, 8, 16, 12),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    IconButton(
                      onPressed: () => Navigator.of(context).maybePop(),
                      icon: const Icon(Icons.arrow_back_rounded,
                          color: PaColors.inkPrimary,),
                      tooltip: l.common_back,
                    ),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(l.contrib_eyebrow.toUpperCase(),
                              style: PaText.eyebrow(),),
                          const SizedBox(height: 3),
                          Text(l.contrib_title,
                              style: PaText.heading(size: 22),),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
              Expanded(
                child: RefreshIndicator.adaptive(
                  color: PaColors.teal,
                  onRefresh: () =>
                      ref.read(contributionsProvider.notifier).refresh(),
                  child: CustomScrollView(
                    physics: const AlwaysScrollableScrollPhysics(),
                    slivers: [
                      SliverPadding(
                        padding: const EdgeInsets.fromLTRB(16, 4, 16, 20),
                        sliver:
                            SliverToBoxAdapter(child: _TotalCard(total: total)),
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
                            padding: const EdgeInsets.fromLTRB(16, 0, 16, 90),
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
                                horizontal: 16, vertical: 8,),
                            child: PaCard(
                              padding: EdgeInsets.all(18),
                              child: SkeletonList(lines: 5),
                            ),
                          ),
                        ),
                        error: (e, _) => SliverPadding(
                          padding: const EdgeInsets.fromLTRB(16, 8, 16, 0),
                          sliver: SliverToBoxAdapter(
                            child: PaErrorState(
                              onRetry: () => ref
                                  .read(contributionsProvider.notifier)
                                  .refresh(),
                            ),
                          ),
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
    return PaCard(
      padding: const EdgeInsets.all(20),
      child: Row(
        children: [
          Container(
            width: 52,
            height: 52,
            decoration: BoxDecoration(
              color: PaColors.tealSurface,
              borderRadius: BorderRadius.circular(16),
            ),
            child: const Icon(
              Icons.account_balance_wallet_outlined,
              color: PaColors.teal,
              size: 26,
            ),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(l.contrib_total_label,
                    style: PaText.body(size: 13, color: PaColors.inkSecondary),),
                const SizedBox(height: 4),
                Text(
                  XAFFormatter.format(total),
                  style: PaText.amount(size: 22, color: PaColors.navyDeep),
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
                  top: isFirst ? 22 : 0,
                  bottom: isLast ? null : 0,
                  height: isLast ? 22 : null,
                  child: Container(width: 2, color: PaColors.line),
                ),
                Positioned(
                  top: 22,
                  child: Container(
                    width: 14,
                    height: 14,
                    decoration: BoxDecoration(
                      color: meta.tint,
                      shape: BoxShape.circle,
                      border: Border.all(color: PaColors.canvas, width: 3),
                    ),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(width: 6),
          Expanded(
            child: Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: PaCard(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Icon(meta.icon, size: 18, color: meta.tint),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Text(meta.label,
                              style: PaText.label(size: 14),),
                        ),
                        _StatusBadge(status: contribution.statut),
                      ],
                    ),
                    const SizedBox(height: 10),
                    Row(
                      children: [
                        Text(
                          XAFFormatter.format(contribution.montant),
                          style: PaText.amount(size: 17),
                        ),
                        const Spacer(),
                        Text(
                          AppDateFormatter.long(contribution.date),
                          style: PaText.body(
                              size: 12.5, color: PaColors.inkMuted,),
                        ),
                      ],
                    ),
                    // Frais de transaction Tara (Mobile Money) : affichés EN PLUS
                    // du montant, comme sur le portail. Rien si versé en agence
                    // (frais = 0).
                    if (contribution.frais > 0) ...[
                      const SizedBox(height: 4),
                      Text(
                        '+ ${XAFFormatter.format(contribution.frais)} de frais'
                        ' = ${XAFFormatter.format(contribution.totalPaye)} payés',
                        style: PaText.body(
                          size: 12, color: PaColors.warning,),
                      ),
                    ],
                    if (contribution.reference != null) ...[
                      const SizedBox(height: 6),
                      Row(
                        children: [
                          const Icon(
                            Icons.confirmation_number_outlined,
                            size: 13,
                            color: PaColors.inkMuted,
                          ),
                          const SizedBox(width: 4),
                          Text(
                            l.contrib_ref(contribution.reference!),
                            style: PaText.body(
                                size: 11.5, color: PaColors.inkMuted,),
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
      ContributionType t, AppL10n l,) {
    switch (t) {
      case ContributionType.fraisInscription:
        return (
          icon: Icons.how_to_reg_outlined,
          tint: PaColors.success,
          label: l.contrib_type_inscription,
        );
      case ContributionType.fraisAdhesion:
        return (
          icon: Icons.diversity_3_rounded,
          tint: PaColors.teal,
          label: l.contrib_type_adhesion,
        );
      case ContributionType.fraisDemandeCredit:
        return (
          icon: Icons.account_balance_outlined,
          tint: PaColors.blue,
          label: l.contrib_type_credit_request,
        );
      case ContributionType.fraisReconduction:
        return (
          icon: Icons.refresh_rounded,
          tint: PaColors.warning,
          label: l.contrib_type_renewal,
        );
      case ContributionType.fraisCarnet:
        return (
          icon: Icons.menu_book_outlined,
          tint: PaColors.navy,
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
          PaColors.successSurface,
          PaColors.success,
        ),
      ContributionStatus.enAttente => (
          l.contrib_status_pending,
          PaColors.warningSurface,
          PaColors.warning,
        ),
      ContributionStatus.echec => (
          l.contrib_status_failed,
          PaColors.dangerSurface,
          PaColors.danger,
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
    return Padding(
      padding: const EdgeInsets.fromLTRB(24, 60, 24, 60),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Container(
            width: 72,
            height: 72,
            decoration: BoxDecoration(
              color: PaColors.tealSurface,
              borderRadius: BorderRadius.circular(24),
            ),
            alignment: Alignment.center,
            child: const Icon(
              Icons.receipt_long_outlined,
              color: PaColors.teal,
              size: 32,
            ),
          ),
          const SizedBox(height: 18),
          Text(l.contrib_empty_title, style: PaText.heading(size: 17)),
          const SizedBox(height: 6),
          Text(
            l.contrib_empty_sub,
            textAlign: TextAlign.center,
            style: PaText.body(size: 14, color: PaColors.inkSecondary),
          ),
        ],
      ),
    );
  }
}
