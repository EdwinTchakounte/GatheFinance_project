import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

import '../../../../app/theme/paysika/pa_colors.dart';
import '../../../../core/formatters/date_formatter.dart';
import '../../../../core/formatters/xaf_formatter.dart';
import '../../../../core/widgets/paysika/pa_card.dart';
import '../../../../core/widgets/paysika/pa_pattern_background.dart';
import '../../../../core/widgets/paysika/pa_transaction_tile.dart';
import '../../../../core/widgets/skeleton.dart';
import '../../../../l10n/gen/app_localizations.dart';
import '../../domain/entities/savings_transaction.dart';
import '../state/classic_savings_notifier.dart';
import '../state/savings_notifier.dart';
import '../widgets/collecte_eom_card.dart';
import '../../../../core/error/error_message.dart';

/// Une transaction + sa provenance (collecte journalière vs épargne classique),
/// pour libeller chaque ligne sans ambiguïté dans l'historique fusionné.
typedef _Entry = ({SavingsTransaction tx, bool collecte});

/// Page Historique . style **Paysika** (palette navy/teal).
///
///   1. AppBar minimaliste (back + titre)
///   2. Filtres par type (chips navy/teal)
///   3. Sections mois (eyebrow + net total) + PaTransactionTile groupées
///      dans une PaCard
class SavingsHistoryPage extends ConsumerStatefulWidget {
  const SavingsHistoryPage({super.key});

  @override
  ConsumerState<SavingsHistoryPage> createState() =>
      _SavingsHistoryPageState();
}

class _SavingsHistoryPageState extends ConsumerState<SavingsHistoryPage> {
  SavingsType? _type;

  @override
  Widget build(BuildContext context) {
    // Historique unifié : épargne classique + collecte journalière, pour que
    // les versements collecte soient visibles ici (et plus seulement dans
    // Mes états). Les deux comptes sont fusionnés et triés par date.
    final savings = ref.watch(classicSavingsProvider);
    final cotisation = ref.watch(savingsProvider);
    final l = AppL10n.of(context);

    return Scaffold(
      backgroundColor: PaColors.canvas,
      appBar: AppBar(
        backgroundColor: PaColors.canvas,
        surfaceTintColor: PaColors.canvas,
        elevation: 0,
        scrolledUnderElevation: 0,
        centerTitle: true,
        title: Text(
          l.savings_history_title,
          style: const TextStyle(
            color: PaColors.inkPrimary,
            fontSize: 16,
            fontWeight: FontWeight.w700,
          ),
        ),
        iconTheme: const IconThemeData(color: PaColors.inkPrimary),
      ),
      body: PaPatternBackground(
        child: Column(
        children: [
          _TypeFilters(
            value: _type,
            onChanged: (t) {
              HapticFeedback.selectionClick();
              setState(() => _type = t);
            },
          ),
          // Choix de fin de mois collecte (cash vs bascule épargne) — piloté
          // par le membre, respecté par le cron mensuel.
          const Padding(
            padding: EdgeInsets.fromLTRB(16, 4, 16, 8),
            child: CollecteEomCard(),
          ),
          Expanded(
            child: RefreshIndicator.adaptive(
              color: PaColors.teal,
              onRefresh: () async {
                await Future.wait([
                  ref.read(classicSavingsProvider.notifier).refresh(),
                  ref.read(savingsProvider.notifier).refresh(),
                ]);
              },
              child: savings.when(
                data: (data) {
                  final coti = cotisation.valueOrNull?.transactions ??
                      const <SavingsTransaction>[];
                  final entries = <_Entry>[
                    for (final t in data.transactions) (tx: t, collecte: false),
                    for (final t in coti) (tx: t, collecte: true),
                  ];
                  return _List(entries: entries, typeFilter: _type);
                },
                loading: () => const _LoadingList(),
                error: (e, _) => _ErrorState(message: friendlyError(e)),
              ),
            ),
          ),
        ],
      ),
      ),
    );
  }
}


class _TypeFilters extends StatelessWidget {
  const _TypeFilters({required this.value, required this.onChanged});

  final SavingsType? value;
  final ValueChanged<SavingsType?> onChanged;

  @override
  Widget build(BuildContext context) {
    final l = AppL10n.of(context);
    final items = <(SavingsType?, String)>[
      (null, l.savings_type_all),
      (SavingsType.depot, l.savings_type_deposits),
      (SavingsType.interet, l.savings_type_interest),
      (SavingsType.retrait, l.savings_type_withdrawals),
    ];
    return SizedBox(
      height: 50,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 6),
        itemCount: items.length,
        separatorBuilder: (_, __) => const SizedBox(width: 8),
        itemBuilder: (context, i) {
          final (t, label) = items[i];
          return _FilterChip(
            label: label,
            selected: t == value,
            onTap: () => onChanged(t),
          );
        },
      ),
    );
  }
}


class _FilterChip extends StatelessWidget {
  const _FilterChip({
    required this.label,
    required this.selected,
    required this.onTap,
  });

  final String label;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: selected ? PaColors.navy : PaColors.paper,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(999),
        side: BorderSide(
          color: selected ? PaColors.navy : PaColors.line,
          width: 1,
        ),
      ),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(999),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
          child: Text(
            label,
            style: TextStyle(
              color: selected ? Colors.white : PaColors.inkSecondary,
              fontSize: 13,
              fontWeight: FontWeight.w600,
            ),
          ),
        ),
      ),
    );
  }
}


class _List extends StatelessWidget {
  const _List({required this.entries, required this.typeFilter});

  final List<_Entry> entries;
  final SavingsType? typeFilter;

  @override
  Widget build(BuildContext context) {
    final l = AppL10n.of(context);
    final filtered = typeFilter == null
        ? entries
        : entries.where((e) => e.tx.type == typeFilter).toList();

    if (filtered.isEmpty) {
      return _EmptyState(message: l.savings_empty_period);
    }

    final groups = <String, _MonthGroup>{};
    for (final e in filtered) {
      final d = e.tx.date;
      final key = '${d.year}-${d.month.toString().padLeft(2, '0')}';
      groups.putIfAbsent(key, () => _MonthGroup(month: d)).add(e);
    }
    final keys = groups.keys.toList()..sort((a, b) => b.compareTo(a));

    return ListView.builder(
      physics: const AlwaysScrollableScrollPhysics(),
      padding: const EdgeInsets.fromLTRB(16, 6, 16, 60),
      itemCount: keys.length,
      itemBuilder: (context, i) {
        return _MonthSection(group: groups[keys[i]]!);
      },
    );
  }
}


class _MonthGroup {
  _MonthGroup({required this.month});
  final DateTime month;
  final List<_Entry> entries = [];

  void add(_Entry e) => entries.add(e);

  num get netTotal {
    num n = 0;
    for (final e in entries) {
      switch (e.tx.type) {
        case SavingsType.depot:
        case SavingsType.interet:
          n += e.tx.montant;
        case SavingsType.retrait:
          n -= e.tx.montant;
      }
    }
    return n;
  }
}


class _MonthSection extends StatelessWidget {
  const _MonthSection({required this.group});
  final _MonthGroup group;

  @override
  Widget build(BuildContext context) {
    final l = AppL10n.of(context);
    final locale = Localizations.localeOf(context).toLanguageTag();
    final monthLabel = DateFormat.yMMMM(locale).format(group.month).toUpperCase();
    final net = group.netTotal;
    final positive = net >= 0;
    final netColor = positive ? PaColors.success : PaColors.danger;

    return Padding(
      padding: const EdgeInsets.only(bottom: 18),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Section header . month + total net
          Padding(
            padding: const EdgeInsets.only(left: 4, bottom: 6),
            child: Row(
              children: [
                Expanded(
                  child: Text(
                    monthLabel,
                    style: const TextStyle(
                      color: PaColors.inkMuted,
                      fontSize: 11,
                      fontWeight: FontWeight.w700,
                      letterSpacing: 1.6,
                    ),
                  ),
                ),
                Text(
                  '${positive ? '+' : '−'} ${XAFFormatter.formatNumber(net.abs())}',
                  style: TextStyle(
                    color: netColor,
                    fontSize: 12,
                    fontWeight: FontWeight.w700,
                    fontFeatures: const [FontFeature.tabularFigures()],
                  ),
                ),
              ],
            ),
          ),

          PaCard(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 4),
            child: Column(
              children: [
                for (var i = 0; i < group.entries.length; i++) ...[
                  PaTransactionTile(
                    kind: _mapKind(group.entries[i].tx.type),
                    label: _label(
                      l,
                      group.entries[i].tx.type,
                      group.entries[i].collecte,
                    ),
                    time: AppDateFormatter.withTime(group.entries[i].tx.date),
                    amount: group.entries[i].tx.montant,
                  ),
                  if (i < group.entries.length - 1)
                    const SizedBox(height: 6),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }

  PaTxKind _mapKind(SavingsType t) => switch (t) {
        SavingsType.depot => PaTxKind.depot,
        SavingsType.interet => PaTxKind.interet,
        SavingsType.retrait => PaTxKind.retrait,
      };

  String _label(AppL10n l, SavingsType t, bool collecte) => switch (t) {
        SavingsType.depot =>
          collecte ? l.tx_deposit_cotisation : l.tx_deposit,
        SavingsType.interet => l.tx_interest,
        SavingsType.retrait => l.tx_withdrawal,
      };
}


class _LoadingList extends StatelessWidget {
  const _LoadingList();

  @override
  Widget build(BuildContext context) {
    return ListView.builder(
      padding: const EdgeInsets.fromLTRB(16, 10, 16, 60),
      itemCount: 3,
      itemBuilder: (_, __) => const Padding(
        padding: EdgeInsets.only(bottom: 18),
        child: PaCard(
          padding: EdgeInsets.symmetric(vertical: 18, horizontal: 14),
          child: SkeletonList(lines: 3),
        ),
      ),
    );
  }
}


class _EmptyState extends StatelessWidget {
  const _EmptyState({required this.message});
  final String message;

  @override
  Widget build(BuildContext context) {
    final l = AppL10n.of(context);
    return ListView(
      physics: const AlwaysScrollableScrollPhysics(),
      padding: const EdgeInsets.fromLTRB(20, 60, 20, 60),
      children: [
        Container(
          width: 64,
          height: 64,
          margin: const EdgeInsets.only(bottom: 20),
          decoration: const BoxDecoration(
            color: PaColors.tealSurface,
            shape: BoxShape.circle,
          ),
          alignment: Alignment.center,
          child: const Icon(
            Icons.receipt_long_outlined,
            color: PaColors.teal,
            size: 28,
          ),
        ),
        Text(
          l.savings_nothing_title,
          textAlign: TextAlign.center,
          style: const TextStyle(
            color: PaColors.inkPrimary,
            fontSize: 16,
            fontWeight: FontWeight.w700,
          ),
        ),
        const SizedBox(height: 6),
        Text(
          message,
          textAlign: TextAlign.center,
          style: const TextStyle(
            color: PaColors.inkMuted,
            fontSize: 13,
          ),
        ),
      ],
    );
  }
}


class _ErrorState extends StatelessWidget {
  const _ErrorState({required this.message});
  final String message;

  @override
  Widget build(BuildContext context) {
    final l = AppL10n.of(context);
    return ListView(
      physics: const AlwaysScrollableScrollPhysics(),
      padding: const EdgeInsets.fromLTRB(20, 60, 20, 60),
      children: [
        const Icon(
          Icons.cloud_off_outlined,
          color: PaColors.danger,
          size: 32,
        ),
        const SizedBox(height: 10),
        Text(
          l.savings_history_unavailable,
          textAlign: TextAlign.center,
          style: const TextStyle(
            color: PaColors.danger,
            fontSize: 16,
            fontWeight: FontWeight.w700,
          ),
        ),
        const SizedBox(height: 6),
        Text(
          message,
          textAlign: TextAlign.center,
          style: const TextStyle(color: PaColors.inkMuted, fontSize: 12),
        ),
      ],
    );
  }
}
