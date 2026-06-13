import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';

import '../../../../app/theme/paysika/pa_colors.dart';
import '../../../../app/theme/paysika/pa_typography.dart';
import '../../../../core/formatters/xaf_formatter.dart';
import '../../../../core/widgets/paysika/pa_button.dart';
import '../../../../core/widgets/paysika/pa_card.dart';
import '../../../../core/widgets/paysika/pa_error_state.dart';
import '../../../../core/widgets/paysika/pa_pattern_background.dart';
import '../../../../core/widgets/skeleton.dart';
import '../../../../l10n/gen/app_localizations.dart';
import '../../../auth/domain/entities/member.dart';
import '../../../auth/presentation/state/auth_notifier.dart';
import '../../../contributions/presentation/state/contributions_notifier.dart';
import '../../../savings/domain/entities/savings_account.dart';
import '../../../savings/domain/entities/savings_transaction.dart';
import '../../../savings/presentation/state/savings_notifier.dart';
import '../../data/releve_pdf_service.dart';
import 'releve_preview_page.dart';

/// Page « Mes états » — style **Paysika**. Relevé synthèse + KPIs + détail
/// épargne + export PDF.
class StatesPage extends ConsumerWidget {
  const StatesPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final memberAsync = ref.watch(authProvider);
    final savings = ref.watch(savingsProvider);
    final contributions = ref.watch(contributionsProvider);
    final totalCotisations = ref.watch(totalContributionsValideesProvider);
    final l = AppL10n.of(context);
    final locale = Localizations.localeOf(context).toLanguageTag();

    return Scaffold(
      backgroundColor: PaColors.canvas,
      body: PaPatternBackground(
        child: SafeArea(
          bottom: false,
          child: Column(
            children: [
              Padding(
                padding: const EdgeInsets.fromLTRB(8, 8, 16, 12),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    IconButton(
                      onPressed: () => Navigator.of(context).maybePop(),
                      icon: const Icon(Icons.arrow_back_rounded,
                          color: PaColors.inkPrimary),
                      tooltip: l.common_back,
                    ),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(l.profile_eyebrow.toUpperCase(),
                              style: PaText.eyebrow()),
                          const SizedBox(height: 3),
                          Text(l.states_title, style: PaText.heading(size: 22)),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
              Expanded(
                child: RefreshIndicator.adaptive(
                  color: PaColors.teal,
                  onRefresh: () async {
                    await Future.wait([
                      ref.read(savingsProvider.notifier).refresh(),
                      ref.read(contributionsProvider.notifier).refresh(),
                    ]);
                  },
                  child: ListView(
                    physics: const AlwaysScrollableScrollPhysics(),
                    padding: const EdgeInsets.fromLTRB(16, 4, 16, 90),
                    children: [
                      _ReleveCard(
                        memberNumber:
                            memberAsync.valueOrNull?.numeroMembre ?? '—',
                        memberName: memberAsync.valueOrNull?.fullName ??
                            l.profile_member_badge,
                        dateAdhesion: memberAsync.valueOrNull?.dateAdhesion,
                      ),
                      const SizedBox(height: 22),
                      Text(l.states_glance, style: PaText.label(size: 15)),
                      const SizedBox(height: 12),
                      GridView.count(
                        shrinkWrap: true,
                        physics: const NeverScrollableScrollPhysics(),
                        crossAxisCount: 2,
                        mainAxisSpacing: 12,
                        crossAxisSpacing: 12,
                        childAspectRatio: 1.18,
                        children: [
                          savings.when(
                            data: (d) => _KpiTile(
                              icon: Icons.savings_outlined,
                              tint: PaColors.teal,
                              label: l.states_kpi_savings,
                              value: XAFFormatter.formatCompact(d.solde),
                              full: XAFFormatter.format(d.solde),
                            ),
                            loading: () => const _KpiSkeleton(),
                            error: (_, __) => _KpiTile(
                              icon: Icons.savings_outlined,
                              tint: PaColors.teal,
                              label: l.states_kpi_savings,
                              value: '—',
                              full: l.common_unavailable,
                            ),
                          ),
                          _KpiTile(
                            icon: Icons.account_balance_outlined,
                            tint: PaColors.blue,
                            label: l.states_kpi_credit,
                            value: '0 XAF',
                            full: l.states_no_active_credit,
                          ),
                          contributions.when(
                            data: (_) => _KpiTile(
                              icon: Icons.account_balance_wallet_outlined,
                              tint: PaColors.warning,
                              label: l.states_kpi_contributions,
                              value:
                                  XAFFormatter.formatCompact(totalCotisations),
                              full: XAFFormatter.format(totalCotisations),
                            ),
                            loading: () => const _KpiSkeleton(),
                            error: (_, __) => _KpiTile(
                              icon: Icons.account_balance_wallet_outlined,
                              tint: PaColors.warning,
                              label: l.states_kpi_contributions,
                              value: '—',
                              full: l.common_unavailable,
                            ),
                          ),
                          _AncienneteTile(
                            dateAdhesion:
                                memberAsync.valueOrNull?.dateAdhesion,
                          ),
                        ],
                      ),
                      const SizedBox(height: 22),
                      Text(l.states_savings_detail,
                          style: PaText.label(size: 15)),
                      const SizedBox(height: 12),
                      savings.when(
                        data: (d) => _DetailCard(
                          lines: [
                            (l.states_balance_today,
                                XAFFormatter.format(d.solde)),
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
                        loading: () => const PaCard(
                          padding: EdgeInsets.all(16),
                          child: SkeletonList(lines: 4),
                        ),
                        error: (e, _) => PaErrorState(
                          onRetry: () =>
                              ref.read(savingsProvider.notifier).refresh(),
                        ),
                      ),
                      const SizedBox(height: 22),
                      PaCard(
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
                                  color: PaColors.tealSurface,
                                  borderRadius: BorderRadius.circular(12),
                                ),
                                child: const Icon(
                                  Icons.receipt_long_outlined,
                                  color: PaColors.teal,
                                  size: 20,
                                ),
                              ),
                              const SizedBox(width: 14),
                              Expanded(
                                child: Column(
                                  crossAxisAlignment:
                                      CrossAxisAlignment.start,
                                  children: [
                                    Text(l.states_contrib_detail_title,
                                        style: PaText.label(size: 14)),
                                    const SizedBox(height: 2),
                                    Text(
                                      l.states_contrib_detail_sub,
                                      style: PaText.body(
                                          size: 12.5,
                                          color: PaColors.inkMuted),
                                    ),
                                  ],
                                ),
                              ),
                              const Icon(Icons.chevron_right_rounded,
                                  color: PaColors.inkFaint),
                            ],
                          ),
                        ),
                      ),
                      const SizedBox(height: 22),
                      PaButton(
                        label: l.states_download_pdf,
                        icon: Icons.picture_as_pdf_outlined,
                        variant: PaButtonVariant.outline,
                        onPressed: () =>
                            _exportPdf(context, ref, savings.valueOrNull,
                                memberAsync.valueOrNull, totalCotisations, l),
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

  Future<void> _exportPdf(
    BuildContext context,
    WidgetRef ref,
    SavingsAccount? data,
    Member? member,
    num totalCotisations,
    AppL10n l,
  ) async {
    unawaited(HapticFeedback.lightImpact());
    if (data == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(l.common_unavailable)),
      );
      return;
    }
    final df = DateFormat('dd/MM/yyyy');
    // La page Mes états affiche les transactions de cotisation journalière
    // (savingsProvider), pas l'épargne classique — on utilise donc le libellé
    // dédié pour ne plus brouiller les deux notions côté membre.
    String txLabel(SavingsType t) => switch (t) {
          SavingsType.depot => l.tx_deposit_cotisation,
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
      issuedOn: l.releve_pdf_issued_on(df.format(DateTime.now())),
      memberLabel: l.releve_pdf_member,
      memberName: member?.fullName ?? l.profile_member_badge,
      numberLabel: l.releve_pdf_number,
      memberNumber: member?.numeroMembre ?? '—',
      balanceLabel: l.releve_pdf_balance,
      balanceValue: XAFFormatter.format(data.solde),
      rateLabel: l.releve_pdf_rate,
      rateValue: '${(data.tauxInteret * 100).toStringAsFixed(0)} %',
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
        builder: (_) =>
            RelevePreviewPage(data: pdfData, title: l.releve_pdf_title),
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
    final locale = Localizations.localeOf(context).toLanguageTag();
    final today = DateFormat.yMMMMd(locale).format(DateTime.now());

    return PaCard(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Text(l.states_releve_eyebrow.toUpperCase(),
                  style: PaText.eyebrow()),
              const Spacer(),
              Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                decoration: BoxDecoration(
                  color: PaColors.tealSurface,
                  borderRadius: BorderRadius.circular(999),
                ),
                child: Text(
                  l.states_releve_official,
                  style: PaText.label(size: 11, color: PaColors.teal),
                ),
              ),
            ],
          ),
          const SizedBox(height: 14),
          Text(memberName, style: PaText.heading(size: 20)),
          const SizedBox(height: 6),
          Wrap(
            spacing: 14,
            runSpacing: 4,
            children: [
              _MetaItem(icon: Icons.tag_rounded, text: memberNumber),
              _MetaItem(
                  icon: Icons.event_outlined, text: l.states_releve_on(today)),
            ],
          ),
          if (dateAdhesion != null) ...[
            const SizedBox(height: 14),
            const Divider(height: 1, color: PaColors.line),
            const SizedBox(height: 14),
            Text(
              l.states_member_since(
                DateFormat.yMMMMd(locale).format(dateAdhesion!),
              ),
              style: PaText.body(size: 14, color: PaColors.inkSecondary),
            ),
          ],
        ],
      ),
    );
  }
}


class _MetaItem extends StatelessWidget {
  const _MetaItem({required this.icon, required this.text});
  final IconData icon;
  final String text;

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, size: 14, color: PaColors.inkMuted),
        const SizedBox(width: 4),
        Text(text, style: PaText.body(size: 12.5, color: PaColors.inkSecondary)),
      ],
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
    return PaCard(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 38,
            height: 38,
            decoration: BoxDecoration(
              color: tint.withValues(alpha: 0.12),
              borderRadius: BorderRadius.circular(12),
            ),
            child: Icon(icon, color: tint, size: 20),
          ),
          const Spacer(),
          Text(label,
              style: PaText.body(size: 12.5, color: PaColors.inkMuted)),
          const SizedBox(height: 2),
          Text(value, style: PaText.amount(size: 17)),
          const SizedBox(height: 2),
          Text(
            full,
            style: PaText.body(size: 11.5, color: PaColors.inkMuted),
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
        tint: PaColors.navy,
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
      tint: PaColors.navy,
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
    return const PaCard(
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
    return PaCard(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
      child: Column(
        children: [
          for (var i = 0; i < lines.length; i++) ...[
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 14),
              child: Row(
                children: [
                  Expanded(
                    child: Text(lines[i].$1,
                        style: PaText.body(
                            size: 14, color: PaColors.inkSecondary)),
                  ),
                  Text(lines[i].$2, style: PaText.amount(size: 15)),
                ],
              ),
            ),
            if (i < lines.length - 1)
              const Divider(height: 1, color: PaColors.line),
          ],
        ],
      ),
    );
  }
}
