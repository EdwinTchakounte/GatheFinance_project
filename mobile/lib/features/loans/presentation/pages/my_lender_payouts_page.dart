import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../app/theme/app_typography.dart';
import '../../../../app/theme/paysika/pa_colors.dart';
import '../../../../core/di/providers.dart';
import '../../../../core/formatters/xaf_formatter.dart';
import '../../../../core/widgets/paysika/pa_card.dart';
import '../../../../core/widgets/paysika/pa_error_state.dart';
import '../../../../core/widgets/paysika/pa_shimmer.dart';
import '../../domain/entities/lender_payout.dart';

/// CH-12 . Écran « Mes versements prêteur ».
///
/// Liste les versements d'intérêts reçus par le membre en tant que prêteur
/// (refonte 2026 §7.5 + Sinora §5.3). Distingue les versements à T0 (mode
/// source CH-11) des versements au fil des remboursements (mode legacy).
class MyLenderPayoutsPage extends ConsumerWidget {
  const MyLenderPayoutsPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(myLenderPayoutsProvider);
    return Scaffold(
      backgroundColor: PaColors.appBg,
      appBar: AppBar(
        title: const Text('Mes intérêts de prêteur'),
        backgroundColor: PaColors.appBg,
        elevation: 0,
        scrolledUnderElevation: 0,
      ),
      body: async.when(
        loading: () => ListView(
          padding: const EdgeInsets.fromLTRB(16, 16, 16, 24),
          children: const [
            PaCard(
              padding: EdgeInsets.all(16),
              child: PaShimmerList(count: 4),
            ),
          ],
        ),
        error: (err, _) => PaErrorState(
          message: 'Impossible de charger tes versements.',
          onRetry: () => ref.invalidate(myLenderPayoutsProvider),
        ),
        data: (items) => items.isEmpty
            ? const _EmptyView()
            : RefreshIndicator(
                onRefresh: () async => ref.invalidate(myLenderPayoutsProvider),
                child: ListView.separated(
                  padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
                  itemCount: items.length + 1,
                  separatorBuilder: (_, __) => const SizedBox(height: 10),
                  itemBuilder: (context, index) {
                    if (index == 0) return _TotalHeader(items: items);
                    return _PayoutTile(payout: items[index - 1]);
                  },
                ),
              ),
      ),
    );
  }
}


class _TotalHeader extends StatelessWidget {
  const _TotalHeader({required this.items});
  final List<LenderPayout> items;

  @override
  Widget build(BuildContext context) {
    final total = items.fold<num>(0, (s, p) => s + p.montant);
    return PaCard(
      padding: const EdgeInsets.all(18),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Total perçu',
            style: AppTypography.bodySmall.copyWith(
              color: PaColors.inkSecondary,
              fontSize: 12,
              fontWeight: FontWeight.w600,
              letterSpacing: 0.4,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            XAFFormatter.format(total),
            style: const TextStyle(
              color: PaColors.success,
              fontSize: 26,
              fontWeight: FontWeight.w700,
              letterSpacing: -0.4,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            '${items.length} versement${items.length > 1 ? "s" : ""} sur les '
            '${_distinctLoans(items)} crédit${_distinctLoans(items) > 1 ? "s" : ""} '
            'que tu as financés.',
            style: AppTypography.bodySmall.copyWith(
              color: PaColors.inkSecondary,
              fontSize: 12,
            ),
          ),
        ],
      ),
    );
  }

  int _distinctLoans(List<LenderPayout> items) =>
      items.map((p) => p.loanId).toSet().length;
}


class _PayoutTile extends StatelessWidget {
  const _PayoutTile({required this.payout});
  final LenderPayout payout;

  @override
  Widget build(BuildContext context) {
    final isSource = payout.kind == LenderPayoutKind.atSource;
    return PaCard(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
      child: Row(
        children: [
          Container(
            width: 38,
            height: 38,
            decoration: BoxDecoration(
              color: isSource
                  ? PaColors.success.withValues(alpha: 0.12)
                  : PaColors.teal.withValues(alpha: 0.10),
              borderRadius: BorderRadius.circular(10),
            ),
            child: Icon(
              isSource ? Icons.bolt_rounded : Icons.event_repeat_rounded,
              color: isSource ? PaColors.success : PaColors.teal,
              size: 20,
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Expanded(
                      child: Text(
                        payout.loanNumeroDossier.isEmpty
                            ? 'Crédit'
                            : payout.loanNumeroDossier,
                        style: const TextStyle(
                          color: PaColors.inkPrimary,
                          fontSize: 14,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                    ),
                    Text(
                      '+${XAFFormatter.format(payout.montant)}',
                      style: const TextStyle(
                        color: PaColors.success,
                        fontSize: 14,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 2),
                Text(
                  isSource
                      ? 'À la mise à disposition · ta part ${(payout.quotePart * 100).toStringAsFixed(0)} %'
                      : 'Échéance n°${payout.installmentNumero ?? "?"} · part ${(payout.quotePart * 100).toStringAsFixed(0)} %',
                  style: const TextStyle(
                    color: PaColors.inkSecondary,
                    fontSize: 12,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  _shortDate(payout.date),
                  style: const TextStyle(
                    color: PaColors.inkMuted,
                    fontSize: 11,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  String _shortDate(DateTime d) {
    const mois = [
      'janv', 'févr', 'mars', 'avril', 'mai', 'juin',
      'juil', 'août', 'sept', 'oct', 'nov', 'déc',
    ];
    return '${d.day} ${mois[d.month - 1]} ${d.year}';
  }
}


class _EmptyView extends StatelessWidget {
  const _EmptyView();

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(28),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const SizedBox(height: 40),
          Container(
            width: 64,
            height: 64,
            decoration: BoxDecoration(
              color: PaColors.teal.withValues(alpha: 0.08),
              shape: BoxShape.circle,
            ),
            child: const Icon(Icons.savings_rounded,
                size: 30, color: PaColors.teal,),
          ),
          const SizedBox(height: 16),
          const Text(
            'Aucun versement pour l\'instant',
            style: TextStyle(
              color: PaColors.inkPrimary,
              fontSize: 16,
              fontWeight: FontWeight.w700,
            ),
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 8),
          const Text(
            'Quand une portion de ton épargne placée sera utilisée pour '
            'financer un crédit, tu verras ici la rémunération que tu perçois.',
            textAlign: TextAlign.center,
            style: TextStyle(
              color: PaColors.inkSecondary,
              fontSize: 13,
              height: 1.45,
            ),
          ),
        ],
      ),
    );
  }
}


