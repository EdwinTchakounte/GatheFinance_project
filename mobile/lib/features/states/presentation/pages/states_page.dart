import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';

import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_radii.dart';
import '../../../../app/theme/app_spacing.dart';
import '../../../../app/theme/app_typography.dart';
import '../../../../core/formatters/xaf_formatter.dart';
import '../../../../core/widgets/app_card.dart';
import '../../../../core/widgets/app_pill.dart';
import '../../../../core/widgets/brand_background.dart';
import '../../../../core/widgets/eyebrow.dart';
import '../../../../core/widgets/skeleton.dart';
import '../../../../core/widgets/static_page_header.dart';
import '../../../../l10n/gen/app_localizations.dart';
import '../../../auth/presentation/state/auth_notifier.dart';
import '../../../contributions/presentation/state/contributions_notifier.dart';
import '../../../savings/domain/entities/savings_transaction.dart';
import '../../../savings/presentation/state/savings_notifier.dart';
import '../../data/releve_pdf_service.dart';
import 'releve_preview_page.dart';

class StatesPage extends ConsumerWidget {
  const StatesPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final memberAsync = ref.watch(authProvider);
    final savings = ref.watch(savingsProvider);
    final contributions = ref.watch(contributionsProvider);
    final totalCotisations = ref.watch(totalContributionsValideesProvider);
    final l = AppL10n.of(context);
    final scheme = Theme.of(context).colorScheme;
    final locale = Localizations.localeOf(context).toLanguageTag();

    return Scaffold(
      body: BrandBackground(
        intensity: 0.55,
        child: SafeArea(
          bottom: false,
          child: Column(
            children: [
              StaticPageHeader(
                eyebrow: l.profile_eyebrow,
                title: l.states_title,
              ),
              Expanded(
                child: RefreshIndicator.adaptive(
                  color: scheme.primary,
                  onRefresh: () async {
                    await Future.wait([
                      ref.read(savingsProvider.notifier).refresh(),
                      ref.read(contributionsProvider.notifier).refresh(),
                    ]);
                  },
                  child: ListView(
                    physics: const AlwaysScrollableScrollPhysics(),
                    padding: const EdgeInsets.only(top: AppSpacing.l),
                    children: [
                Padding(
                  padding: const EdgeInsets.symmetric(
                      horizontal: AppSpacing.screenH),
                  child: _ReleveCard(
                    memberNumber:
                        memberAsync.valueOrNull?.numeroMembre ?? '—',
                    memberName: memberAsync.valueOrNull?.fullName ??
                        l.profile_member_badge,
                    dateAdhesion: memberAsync.valueOrNull?.dateAdhesion,
                  ),
                ),
                const SizedBox(height: AppSpacing.xl),
                Padding(
                  padding: const EdgeInsets.fromLTRB(
                    AppSpacing.screenH,
                    0,
                    AppSpacing.screenH,
                    AppSpacing.m,
                  ),
                  child: Text(
                    l.states_glance,
                    style: AppTypography.labelLarge
                        .copyWith(color: scheme.onSurface),
                  ),
                ),
                Padding(
                  padding: const EdgeInsets.symmetric(
                      horizontal: AppSpacing.screenH),
                  child: GridView.count(
                    shrinkWrap: true,
                    physics: const NeverScrollableScrollPhysics(),
                    crossAxisCount: 2,
                    mainAxisSpacing: AppSpacing.m,
                    crossAxisSpacing: AppSpacing.m,
                    childAspectRatio: 1.18,
                    children: [
                      savings.when(
                        data: (d) => _KpiTile(
                          icon: Icons.savings_outlined,
                          tint: AppColors.emerald,
                          label: l.states_kpi_savings,
                          value: XAFFormatter.formatCompact(d.solde),
                          full: XAFFormatter.format(d.solde),
                        ),
                        loading: () => const _KpiSkeleton(),
                        error: (_, __) => _KpiTile(
                          icon: Icons.savings_outlined,
                          tint: AppColors.emerald,
                          label: l.states_kpi_savings,
                          value: '—',
                          full: l.common_unavailable,
                        ),
                      ),
                      _KpiTile(
                        icon: Icons.account_balance_outlined,
                        tint: AppColors.cobalt,
                        label: l.states_kpi_credit,
                        value: '0 XAF',
                        full: l.states_no_active_credit,
                      ),
                      contributions.when(
                        data: (_) => _KpiTile(
                          icon: Icons.account_balance_wallet_outlined,
                          tint: AppColors.terra,
                          label: l.states_kpi_contributions,
                          value:
                              XAFFormatter.formatCompact(totalCotisations),
                          full: XAFFormatter.format(totalCotisations),
                        ),
                        loading: () => const _KpiSkeleton(),
                        error: (_, __) => _KpiTile(
                          icon: Icons.account_balance_wallet_outlined,
                          tint: AppColors.terra,
                          label: l.states_kpi_contributions,
                          value: '—',
                          full: l.common_unavailable,
                        ),
                      ),
                      _AncienneteTile(
                        dateAdhesion: memberAsync.valueOrNull?.dateAdhesion,
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: AppSpacing.xl),
                Padding(
                  padding: const EdgeInsets.fromLTRB(
                    AppSpacing.screenH,
                    0,
                    AppSpacing.screenH,
                    AppSpacing.m,
                  ),
                  child: Text(
                    l.states_savings_detail,
                    style: AppTypography.labelLarge
                        .copyWith(color: scheme.onSurface),
                  ),
                ),
                Padding(
                  padding: const EdgeInsets.symmetric(
                      horizontal: AppSpacing.screenH),
                  child: savings.when(
                    data: (d) => _DetailCard(
                      lines: [
                        (l.states_balance_today, XAFFormatter.format(d.solde)),
                        (
                          l.states_interest_rate,
                          '${(d.tauxInteret * 100).toStringAsFixed(2).replaceAll('.', ',')} %'
                        ),
                        (
                          l.states_account_opened,
                          DateFormat.yMMMMd(locale).format(d.dateOuverture)
                        ),
                        (l.states_movements, '${d.transactions.length}'),
                      ],
                    ),
                    loading: () => const AppCard(
                      padding: EdgeInsets.all(16),
                      child: SkeletonList(lines: 4),
                    ),
                    error: (e, _) => AppCard(
                      padding: const EdgeInsets.all(16),
                      child: Text(
                        e.toString(),
                        style: AppTypography.bodySmall.copyWith(
                          color: AppColors.terraDark,
                        ),
                      ),
                    ),
                  ),
                ),
                const SizedBox(height: AppSpacing.xl),
                Padding(
                  padding: const EdgeInsets.symmetric(
                      horizontal: AppSpacing.screenH),
                  child: AppCard(
                    padding: EdgeInsets.zero,
                    onTap: () => context.push('/contributions'),
                    child: Padding(
                      padding: const EdgeInsets.fromLTRB(18, 16, 14, 16),
                      child: Row(
                        children: [
                          Container(
                            width: 42,
                            height: 42,
                            decoration: BoxDecoration(
                              color: scheme.surfaceContainerHighest,
                              borderRadius:
                                  const BorderRadius.all(AppRadii.r12),
                            ),
                            child: Icon(
                              Icons.receipt_long_outlined,
                              color: scheme.primary,
                              size: 20,
                            ),
                          ),
                          const SizedBox(width: 14),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  l.states_contrib_detail_title,
                                  style: AppTypography.labelLarge
                                      .copyWith(color: scheme.onSurface),
                                ),
                                const SizedBox(height: 2),
                                Text(
                                  l.states_contrib_detail_sub,
                                  style: AppTypography.bodySmall.copyWith(
                                    color: scheme.onSurface
                                        .withValues(alpha: 0.55),
                                  ),
                                ),
                              ],
                            ),
                          ),
                          Icon(
                            Icons.chevron_right_rounded,
                            color: scheme.onSurface.withValues(alpha: 0.35),
                          ),
                        ],
                      ),
                    ),
                  ),
                ),
                const SizedBox(height: AppSpacing.xl),
                Padding(
                  padding: const EdgeInsets.symmetric(
                      horizontal: AppSpacing.screenH),
                  child: OutlinedButton.icon(
                    onPressed: () async {
                      unawaited(HapticFeedback.lightImpact());
                      final data = savings.valueOrNull;
                      if (data == null) {
                        ScaffoldMessenger.of(context).showSnackBar(
                          SnackBar(content: Text(l.common_unavailable)),
                        );
                        return;
                      }
                      final member = memberAsync.valueOrNull;
                      final df = DateFormat('dd/MM/yyyy');
                      String txLabel(SavingsType t) => switch (t) {
                            SavingsType.depot => l.tx_deposit,
                            SavingsType.interet => l.tx_interest,
                            SavingsType.retrait => l.tx_withdrawal,
                          };
                      final rows = [
                        for (final t in data.transactions)
                          [
                            df.format(t.date),
                            txLabel(t.type),
                            '${t.type == SavingsType.retrait ? '- ' : '+ '}'
                                '${XAFFormatter.format(t.montant)}',
                          ],
                      ];
                      final pdfData = RelevePdfData(
                        docTitle: l.releve_pdf_title,
                        issuedOn:
                            l.releve_pdf_issued_on(df.format(DateTime.now())),
                        memberLabel: l.releve_pdf_member,
                        memberName: member?.fullName ?? l.profile_member_badge,
                        numberLabel: l.releve_pdf_number,
                        memberNumber: member?.numeroMembre ?? '—',
                        balanceLabel: l.releve_pdf_balance,
                        balanceValue: XAFFormatter.format(data.solde),
                        rateLabel: l.releve_pdf_rate,
                        rateValue:
                            '${(data.tauxInteret * 100).toStringAsFixed(0)} %',
                        totalLabel: l.releve_pdf_total_contrib,
                        totalValue: XAFFormatter.format(totalCotisations),
                        txHeader: l.releve_pdf_tx_header,
                        colDate: l.releve_pdf_col_date,
                        colLabel: l.releve_pdf_col_label,
                        colAmount: l.releve_pdf_col_amount,
                        rows: rows,
                        footer: l.releve_pdf_footer,
                        fileName: l.releve_pdf_filename,
                      );
                      if (!context.mounted) return;
                      Navigator.of(context).push(
                        MaterialPageRoute<void>(
                          builder: (_) => RelevePreviewPage(
                            data: pdfData,
                            title: l.releve_pdf_title,
                          ),
                        ),
                      );
                    },
                    icon: const Icon(Icons.picture_as_pdf_outlined, size: 18),
                    label: Text(
                      l.states_download_pdf,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                ),
                const SizedBox(height: AppSpacing.huge),
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


class _ReleveCard extends StatelessWidget {
  const _ReleveCard({
    required this.memberNumber,
    required this.memberName,
    required this.dateAdhesion,
  });

  final String memberNumber;
  final String memberName;
  final DateTime? dateAdhesion;

  @override
  Widget build(BuildContext context) {
    final l = AppL10n.of(context);
    final scheme = Theme.of(context).colorScheme;
    final locale = Localizations.localeOf(context).toLanguageTag();
    final today = DateFormat.yMMMMd(locale).format(DateTime.now());

    return AppCard(
      hero: true,
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Eyebrow(l.states_releve_eyebrow),
              const Spacer(),
              AppPill(label: l.states_releve_official, tone: PillTone.info),
            ],
          ),
          const SizedBox(height: 14),
          Text(
            memberName,
            style: AppTypography.headingMedium
                .copyWith(color: scheme.onSurface),
          ),
          const SizedBox(height: 4),
          Row(
            children: [
              Icon(Icons.tag_rounded,
                  size: 14, color: scheme.onSurface.withValues(alpha: 0.55)),
              const SizedBox(width: 4),
              Text(
                memberNumber,
                style: AppTypography.monoSmall.copyWith(
                  color: scheme.onSurface.withValues(alpha: 0.7),
                ),
              ),
              const SizedBox(width: 14),
              Icon(Icons.event_outlined,
                  size: 14, color: scheme.onSurface.withValues(alpha: 0.55)),
              const SizedBox(width: 4),
              Text(
                l.states_releve_on(today),
                style: AppTypography.bodySmall.copyWith(
                  color: scheme.onSurface.withValues(alpha: 0.7),
                ),
              ),
            ],
          ),
          if (dateAdhesion != null) ...[
            const SizedBox(height: 14),
            Container(height: 1, color: scheme.outline),
            const SizedBox(height: 14),
            Text(
              l.states_member_since(
                DateFormat.yMMMMd(locale).format(dateAdhesion!),
              ),
              style: AppTypography.bodyMedium.copyWith(
                color: scheme.onSurface.withValues(alpha: 0.7),
              ),
            ),
          ],
        ],
      ),
    );
  }
}


class _KpiTile extends StatelessWidget {
  const _KpiTile({
    required this.icon,
    required this.tint,
    required this.label,
    required this.value,
    required this.full,
  });

  final IconData icon;
  final Color tint;
  final String label;
  final String value;
  final String full;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return AppCard(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 38,
            height: 38,
            decoration: BoxDecoration(
              color: tint.withValues(alpha: 0.12),
              borderRadius: const BorderRadius.all(AppRadii.r12),
            ),
            child: Icon(icon, color: tint, size: 20),
          ),
          const Spacer(),
          Text(
            label,
            style: AppTypography.bodySmall.copyWith(
              color: scheme.onSurface.withValues(alpha: 0.55),
            ),
          ),
          const SizedBox(height: 2),
          Text(
            value,
            style: AppTypography.headingSmall.copyWith(
              color: scheme.onSurface,
              fontFeatures: const [FontFeature.tabularFigures()],
            ),
          ),
          const SizedBox(height: 2),
          Text(
            full,
            style: AppTypography.bodySmall.copyWith(
              color: scheme.onSurface.withValues(alpha: 0.55),
              fontSize: 11.5,
            ),
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
          ),
        ],
      ),
    );
  }
}


class _AncienneteTile extends StatelessWidget {
  const _AncienneteTile({required this.dateAdhesion});
  final DateTime? dateAdhesion;

  @override
  Widget build(BuildContext context) {
    final l = AppL10n.of(context);
    if (dateAdhesion == null) {
      return _KpiTile(
        icon: Icons.calendar_month_outlined,
        tint: AppColors.cobaltLight,
        label: l.states_kpi_seniority,
        value: '—',
        full: l.common_unavailable,
      );
    }
    final days = DateTime.now().difference(dateAdhesion!).inDays;
    final months = (days / 30).floor();
    final years = (days / 365).floor();

    String value;
    String full;
    if (years >= 1) {
      // FR pluriel : « 1 an », « 2 ans » — EN : « 1 year », « 2 years »
      value = l.states_years(years, years > 1 ? 's' : '');
      full = l.states_months_total(months);
    } else if (months >= 1) {
      value = l.states_months(months);
      full = l.states_days_long(days);
    } else {
      value = l.states_days_short(days);
      full = l.states_since_join;
    }

    return _KpiTile(
      icon: Icons.calendar_month_outlined,
      tint: AppColors.cobaltLight,
      label: l.states_kpi_seniority,
      value: value,
      full: full,
    );
  }
}


class _KpiSkeleton extends StatelessWidget {
  const _KpiSkeleton();

  @override
  Widget build(BuildContext context) {
    return const AppCard(
      padding: EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Skeleton(width: 38, height: 38, borderRadius: 12),
          Spacer(),
          Skeleton(width: 80, height: 10),
          SizedBox(height: 8),
          Skeleton(width: 100, height: 18),
          SizedBox(height: 6),
          Skeleton(width: 60, height: 10),
        ],
      ),
    );
  }
}


class _DetailCard extends StatelessWidget {
  const _DetailCard({required this.lines});
  final List<(String, String)> lines;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return AppCard(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
      child: Column(
        children: [
          for (var i = 0; i < lines.length; i++) ...[
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 14),
              child: Row(
                children: [
                  Expanded(
                    child: Text(
                      lines[i].$1,
                      style: AppTypography.bodyMedium.copyWith(
                        color: scheme.onSurface.withValues(alpha: 0.7),
                      ),
                    ),
                  ),
                  Text(
                    lines[i].$2,
                    style: AppTypography.labelLarge.copyWith(
                      color: scheme.onSurface,
                      fontFeatures: const [FontFeature.tabularFigures()],
                    ),
                  ),
                ],
              ),
            ),
            if (i < lines.length - 1)
              Divider(height: 1, color: scheme.outline),
          ],
        ],
      ),
    );
  }
}
