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
import '../../../../core/di/providers.dart';
import '../state/classic_savings_notifier.dart';
import '../state/savings_notifier.dart';
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

/// Fenêtre temporelle du filtre « par période ».
enum _Period { all, thisMonth, last3, thisYear }

class _SavingsHistoryPageState extends ConsumerState<SavingsHistoryPage> {
  SavingsType? _type;
  _Period _period = _Period.all;
  int? _bookletId; // null = tous les carnets

  @override
  Widget build(BuildContext context) {
    // Historique unifié : épargne classique + collecte journalière, pour que
    // les versements collecte soient visibles ici (et plus seulement dans
    // Mes états). Les deux comptes sont fusionnés et triés par date.
    // Historique COMPLET paginé (au-delà des 10 dernières écritures du snapshot).
    final history = ref.watch(savingsFullHistoryProvider);
    final l = AppL10n.of(context);

    // Entrées fusionnées (peut être vide tant que ça charge) — sert à dresser
    // la liste des carnets disponibles pour le filtre « par carnet ».
    final classic = history.valueOrNull?.classic ??
        const <SavingsTransaction>[];
    final coti = history.valueOrNull?.collecte ??
        const <SavingsTransaction>[];
    final entries = <_Entry>[
      for (final t in classic) (tx: t, collecte: false),
      for (final t in coti) (tx: t, collecte: true),
    ];
    final carnets = _carnetOptions(entries);
    // Si le carnet filtré n'existe plus dans les données, on revient à « tous ».
    if (_bookletId != null && !carnets.any((c) => c.id == _bookletId)) {
      _bookletId = null;
    }

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
          // Filtre « par période » — toutes / ce mois / 3 mois / cette année.
          _PeriodFilters(
            value: _period,
            onChanged: (p) {
              HapticFeedback.selectionClick();
              setState(() => _period = p);
            },
          ),
          // « Mes carnets » — état par carnet (nb, crédits, débits, net) ET
          // filtre : un tap isole les écritures du carnet. Grouped view.
          if (carnets.isNotEmpty)
            _BookletStateCards(
              states: _bookletStates(entries),
              value: _bookletId,
              onChanged: (id) {
                HapticFeedback.selectionClick();
                setState(() => _bookletId = id);
              },
            ),
          // NB 2026-08 : le choix « fin de mois collecte » a été déplacé dans
          // la page Profil (préférence de compte) — retiré de l'historique pour
          // n'y garder que le relevé des écritures.
          Expanded(
            child: RefreshIndicator.adaptive(
              color: PaColors.teal,
              onRefresh: () async {
                ref.invalidate(savingsFullHistoryProvider);
                await Future.wait([
                  ref.read(classicSavingsProvider.notifier).refresh(),
                  ref.read(savingsProvider.notifier).refresh(),
                  ref.read(savingsFullHistoryProvider.future),
                ]);
              },
              child: history.when(
                data: (_) => _List(
                  entries: entries,
                  typeFilter: _type,
                  period: _period,
                  bookletId: _bookletId,
                ),
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

/// Dresse la liste ordonnée des carnets présents dans les écritures (année
/// décroissante), en désambiguïsant les carnets d'une même année (« Carnet
/// 2026 · 2 »). Sert d'options au filtre « par carnet ».
List<({int id, String label})> _carnetOptions(List<_Entry> entries) {
  final annee = <int, int?>{}; // bookletId -> année
  for (final e in entries) {
    final id = e.tx.bookletId;
    if (id != null) annee[id] = e.tx.bookletAnnee;
  }
  final ids = annee.keys.toList()
    ..sort((a, b) {
      final c = (annee[b] ?? 0).compareTo(annee[a] ?? 0); // année desc
      return c != 0 ? c : b.compareTo(a); // puis id desc
    });
  final perYear = <int?, int>{};
  for (final y in annee.values) {
    perYear[y] = (perYear[y] ?? 0) + 1;
  }
  final seen = <int?, int>{};
  return [
    for (final id in ids)
      (
        id: id,
        label: () {
          final y = annee[id];
          if (y == null) return 'Carnet n°$id';
          if ((perYear[y] ?? 0) > 1) {
            final n = seen[y] = (seen[y] ?? 0) + 1;
            return 'Carnet $y · $n';
          }
          return 'Carnet $y';
        }(),
      ),
  ];
}

/// État par carnet (grouped view) : pour chaque carnet des écritures, le nombre
/// d'écritures, le total crédité/débité et le net (crédits − débits). Calculé
/// côté client à partir des écritures déjà chargées (qui portent bookletId +
/// isDebit), donc pas d'appel réseau supplémentaire.
typedef _BookletState = ({
  int id,
  int? annee,
  int count,
  num credit,
  num debit,
  num net,
});

List<_BookletState> _bookletStates(List<_Entry> entries) {
  final credit = <int, num>{};
  final debit = <int, num>{};
  final count = <int, int>{};
  final annee = <int, int?>{};
  for (final e in entries) {
    final id = e.tx.bookletId;
    if (id == null) continue;
    annee[id] = e.tx.bookletAnnee;
    count[id] = (count[id] ?? 0) + 1;
    if (e.tx.isDebit) {
      debit[id] = (debit[id] ?? 0) + e.tx.montant;
    } else {
      credit[id] = (credit[id] ?? 0) + e.tx.montant;
    }
  }
  final ids = count.keys.toList()
    ..sort((a, b) {
      final c = (annee[b] ?? 0).compareTo(annee[a] ?? 0);
      return c != 0 ? c : b.compareTo(a);
    });
  return [
    for (final id in ids)
      (
        id: id,
        annee: annee[id],
        count: count[id] ?? 0,
        credit: credit[id] ?? 0,
        debit: debit[id] ?? 0,
        net: (credit[id] ?? 0) - (debit[id] ?? 0),
      ),
  ];
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


class _PeriodFilters extends StatelessWidget {
  const _PeriodFilters({required this.value, required this.onChanged});

  final _Period value;
  final ValueChanged<_Period> onChanged;

  @override
  Widget build(BuildContext context) {
    const items = <(_Period, String)>[
      (_Period.all, 'Toutes'),
      (_Period.thisMonth, 'Ce mois'),
      (_Period.last3, '3 mois'),
      (_Period.thisYear, 'Cette année'),
    ];
    return SizedBox(
      height: 46,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 4),
        itemCount: items.length,
        separatorBuilder: (_, __) => const SizedBox(width: 8),
        itemBuilder: (context, i) {
          final (p, label) = items[i];
          return _FilterChip(
            label: label,
            selected: p == value,
            onTap: () => onChanged(p),
          );
        },
      ),
    );
  }
}


class _BookletStateCards extends StatelessWidget {
  const _BookletStateCards({
    required this.states,
    required this.value,
    required this.onChanged,
  });

  final List<_BookletState> states;
  final int? value;
  final ValueChanged<int?> onChanged;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 92,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 4),
        itemCount: states.length + 1,
        separatorBuilder: (_, __) => const SizedBox(width: 10),
        itemBuilder: (context, i) {
          if (i == 0) {
            final selected = value == null;
            return _CardShell(
              selected: selected,
              onTap: () => onChanged(null),
              child: Center(
                child: Text(
                  'Tous\nles carnets',
                  textAlign: TextAlign.center,
                  style: TextStyle(
                    fontSize: 13,
                    fontWeight: FontWeight.w700,
                    color: selected ? PaColors.teal : PaColors.inkPrimary,
                  ),
                ),
              ),
            );
          }
          final s = states[i - 1];
          final selected = value == s.id;
          final net = s.net;
          return _CardShell(
            selected: selected,
            onTap: () => onChanged(selected ? null : s.id),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Text(
                  s.annee != null ? 'Carnet ${s.annee}' : 'Carnet n°${s.id}',
                  style: const TextStyle(
                    fontSize: 12.5,
                    fontWeight: FontWeight.w700,
                    color: PaColors.inkPrimary,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  '${net >= 0 ? '+' : '−'}${XAFFormatter.format(net.abs())}',
                  style: TextStyle(
                    fontSize: 15,
                    fontWeight: FontWeight.w800,
                    color: net >= 0 ? PaColors.success : PaColors.danger,
                  ),
                ),
                const SizedBox(height: 1),
                Text(
                  '${s.count} écriture${s.count > 1 ? 's' : ''}',
                  style: const TextStyle(
                    fontSize: 11, color: PaColors.inkMuted,),
                ),
              ],
            ),
          );
        },
      ),
    );
  }
}

class _CardShell extends StatelessWidget {
  const _CardShell({
    required this.selected,
    required this.onTap,
    required this.child,
  });

  final bool selected;
  final VoidCallback onTap;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        width: 150,
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        decoration: BoxDecoration(
          color: selected ? PaColors.tealSurface : PaColors.paper,
          borderRadius: BorderRadius.circular(14),
          border: Border.all(
            color: selected ? PaColors.teal : PaColors.line,
            width: selected ? 1.4 : 1,
          ),
        ),
        child: child,
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
  const _List({
    required this.entries,
    required this.typeFilter,
    required this.period,
    required this.bookletId,
  });

  final List<_Entry> entries;
  final SavingsType? typeFilter;
  final _Period period;
  final int? bookletId;

  bool _inPeriod(DateTime d, DateTime now) => switch (period) {
        _Period.all => true,
        _Period.thisMonth => d.year == now.year && d.month == now.month,
        // Fenêtre glissante de 3 mois (bornes incluses).
        _Period.last3 =>
          !d.isBefore(DateTime(now.year, now.month - 2, 1)),
        _Period.thisYear => d.year == now.year,
      };

  @override
  Widget build(BuildContext context) {
    final l = AppL10n.of(context);
    final now = DateTime.now();
    final filtered = entries
        .where(
          (e) =>
              (typeFilter == null || e.tx.type == typeFilter) &&
              (bookletId == null || e.tx.bookletId == bookletId) &&
              _inPeriod(e.tx.date, now),
        )
        .toList();

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
      // Signé : les débits (retrait, frais…) comptent en négatif.
      n += e.tx.montantSigne;
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
                    kind: _mapKind(group.entries[i].tx),
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

  PaTxKind _mapKind(SavingsTransaction tx) => switch (tx.type) {
        SavingsType.depot =>
          tx.isDebit ? PaTxKind.frais : PaTxKind.depot,
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
