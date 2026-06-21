import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../app/theme/paysika/pa_colors.dart';
import '../../../../core/formatters/date_formatter.dart';
import '../../../../core/widgets/paysika/pa_card.dart';
import '../../../../core/widgets/paysika/pa_gradient_header_band.dart';
import '../../../../core/widgets/paysika/pa_pattern_background.dart';
import '../../../../core/widgets/skeleton.dart';
import '../../../../l10n/gen/app_localizations.dart';
import '../../domain/entities/booklet_order.dart';
import '../state/booklet_notifier.dart';
import '../widgets/order_booklet_sheet.dart';

/// Page Carnet — style **Paysika**.
///
/// Affiche soit la commande en cours (avec timeline status), soit un appel à
/// commander un nouveau carnet (1 000 FCFA, Article 4 du règlement).
/// Liste l'historique des carnets précédemment délivrés.
class BookletPage extends ConsumerWidget {
  const BookletPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final ordersAsync = ref.watch(bookletProvider);
    final l = AppL10n.of(context);

    return Scaffold(
      backgroundColor: PaColors.canvas,
      body: PaPatternBackground(
        child: SafeArea(
        bottom: false,
        child: Column(
          children: [
            // ── Header FIXE compact — band gradient soft vert→bleu ──────
            PaGradientHeaderBand(title: l.booklet_title),
            const SizedBox(height: 12),
            Expanded(
              child: RefreshIndicator.adaptive(
          color: PaColors.teal,
          onRefresh: () => ref.read(bookletProvider.notifier).refresh(),
          child: CustomScrollView(
            physics: const AlwaysScrollableScrollPhysics(),
            slivers: [
              // ── Commande en cours ou appel à commander ───────────────
              SliverToBoxAdapter(
                child: Padding(
                  padding: const EdgeInsets.fromLTRB(16, 0, 16, 14),
                  child: ordersAsync.when(
                    data: (orders) {
                      final pending = orders
                          .where((o) => o.statut != BookletStatus.delivree)
                          .toList();
                      if (pending.isNotEmpty) {
                        return _PendingOrderCard(order: pending.first);
                      }
                      return const _OrderNewCard();
                    },
                    loading: () => const PaCard(
                      padding: EdgeInsets.all(20),
                      child: SkeletonList(lines: 4),
                    ),
                    error: (e, _) => _ErrorBox(message: e.toString()),
                  ),
                ),
              ),

              // ── Historique (carnets livrés) ──────────────────────────
              SliverToBoxAdapter(
                child: ordersAsync.maybeWhen(
                  data: (orders) {
                    final history = orders
                        .where((o) => o.statut == BookletStatus.delivree)
                        .toList();
                    if (history.isEmpty) return const SizedBox.shrink();
                    return Padding(
                      padding: const EdgeInsets.fromLTRB(20, 14, 20, 8),
                      child: Text(
                        l.booklet_history_title,
                        style: const TextStyle(
                          color: PaColors.inkPrimary,
                          fontSize: 15,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                    );
                  },
                  orElse: () => const SizedBox.shrink(),
                ),
              ),
              SliverToBoxAdapter(
                child: ordersAsync.maybeWhen(
                  data: (orders) {
                    final history = orders
                        .where((o) => o.statut == BookletStatus.delivree)
                        .toList();
                    if (history.isEmpty) return const SizedBox.shrink();
                    return Padding(
                      padding: const EdgeInsets.fromLTRB(16, 0, 16, 80),
                      child: Column(
                        children: [
                          for (final o in history) ...[
                            _HistoryTile(order: o),
                            const SizedBox(height: 8),
                          ],
                        ],
                      ),
                    );
                  },
                  orElse: () => const SizedBox.shrink(),
                ),
              ),

              const SliverToBoxAdapter(child: SizedBox(height: 40)),
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


// ───────────────────────────────────────────────────────────────────────────
// Card "Commande en cours" — header + timeline + hint
// ───────────────────────────────────────────────────────────────────────────

class _PendingOrderCard extends StatelessWidget {
  const _PendingOrderCard({required this.order});
  final BookletOrder order;

  @override
  Widget build(BuildContext context) {
    final l = AppL10n.of(context);

    final statusColor = switch (order.statut) {
      BookletStatus.payee => PaColors.teal,
      BookletStatus.enImpression => PaColors.warning,
      BookletStatus.delivree => PaColors.success,
    };
    final statusLabel = switch (order.statut) {
      BookletStatus.payee => l.booklet_status_paid,
      BookletStatus.enImpression => l.booklet_status_printing,
      BookletStatus.delivree => l.booklet_status_delivered,
    };
    final hint = switch (order.statut) {
      BookletStatus.payee => l.booklet_hint_paid,
      BookletStatus.enImpression => l.booklet_hint_printing,
      BookletStatus.delivree => l.booklet_hint_delivered,
    };

    return PaCard(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 52,
                height: 52,
                decoration: BoxDecoration(
                  color: PaColors.tealSurface,
                  borderRadius: BorderRadius.circular(14),
                ),
                alignment: Alignment.center,
                child: const Icon(
                  Icons.menu_book_rounded,
                  color: PaColors.teal,
                  size: 26,
                ),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      l.booklet_pending_eyebrow.toUpperCase(),
                      style: const TextStyle(
                        color: PaColors.inkMuted,
                        fontSize: 11,
                        fontWeight: FontWeight.w700,
                        letterSpacing: 1.4,
                      ),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      '#${order.id}',
                      style: const TextStyle(
                        color: PaColors.inkPrimary,
                        fontSize: 15,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ],
                ),
              ),
              _StatusChip(label: statusLabel, color: statusColor),
            ],
          ),

          const SizedBox(height: 22),
          _Timeline(current: order.statut),

          const SizedBox(height: 18),
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: PaColors.appBg,
              borderRadius: BorderRadius.circular(10),
            ),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Icon(
                  Icons.notifications_outlined,
                  color: PaColors.teal,
                  size: 18,
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: Text(
                    hint,
                    style: const TextStyle(
                      color: PaColors.inkSecondary,
                      fontSize: 12.5,
                      height: 1.5,
                    ),
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


// ───────────────────────────────────────────────────────────────────────────
// Timeline horizontale 3 étapes
// ───────────────────────────────────────────────────────────────────────────

class _Timeline extends StatelessWidget {
  const _Timeline({required this.current});
  final BookletStatus current;

  int get _activeIndex => switch (current) {
        BookletStatus.payee => 0,
        BookletStatus.enImpression => 1,
        BookletStatus.delivree => 2,
      };

  @override
  Widget build(BuildContext context) {
    final l = AppL10n.of(context);
    final steps = [
      l.booklet_step_payment,
      l.booklet_step_printing,
      l.booklet_step_delivered,
    ];
    return Row(
      children: [
        for (var i = 0; i < steps.length; i++) ...[
          _TimelineStep(
            index: i + 1,
            label: steps[i],
            done: i < _activeIndex,
            active: i == _activeIndex,
          ),
          if (i < steps.length - 1)
            Expanded(
              child: Container(
                height: 2,
                margin: const EdgeInsets.only(bottom: 22),
                color: i < _activeIndex ? PaColors.teal : PaColors.line,
              ),
            ),
        ],
      ],
    );
  }
}


class _TimelineStep extends StatelessWidget {
  const _TimelineStep({
    required this.index,
    required this.label,
    required this.done,
    required this.active,
  });

  final int index;
  final String label;
  final bool done;
  final bool active;

  @override
  Widget build(BuildContext context) {
    final bg = done
        ? PaColors.teal
        : active
            ? PaColors.navy
            : PaColors.paper;
    final border = done || active ? bg : PaColors.line;
    final textColor =
        done || active ? Colors.white : PaColors.inkMuted;
    final labelColor = active
        ? PaColors.navy
        : done
            ? PaColors.teal
            : PaColors.inkMuted;

    return Column(
      children: [
        Container(
          width: 32,
          height: 32,
          decoration: BoxDecoration(
            color: bg,
            shape: BoxShape.circle,
            border: Border.all(color: border, width: 1.5),
          ),
          alignment: Alignment.center,
          child: done
              ? const Icon(Icons.check_rounded, size: 18, color: Colors.white)
              : Text(
                  '$index',
                  style: TextStyle(
                    color: textColor,
                    fontSize: 13,
                    fontWeight: FontWeight.w700,
                  ),
                ),
        ),
        const SizedBox(height: 8),
        Text(
          label,
          style: TextStyle(
            color: labelColor,
            fontSize: 11.5,
            fontWeight: active ? FontWeight.w700 : FontWeight.w600,
          ),
        ),
      ],
    );
  }
}


// ───────────────────────────────────────────────────────────────────────────
// Card "Commander un nouveau carnet"
// ───────────────────────────────────────────────────────────────────────────

class _OrderNewCard extends StatelessWidget {
  const _OrderNewCard();

  @override
  Widget build(BuildContext context) {
    final l = AppL10n.of(context);
    return PaCard(
      padding: const EdgeInsets.all(22),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 52,
                height: 52,
                decoration: BoxDecoration(
                  color: PaColors.tealSurface,
                  borderRadius: BorderRadius.circular(14),
                ),
                alignment: Alignment.center,
                child: const Icon(
                  Icons.menu_book_rounded,
                  color: PaColors.teal,
                  size: 26,
                ),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      l.booklet_new_eyebrow_fee.toUpperCase(),
                      style: const TextStyle(
                        color: PaColors.inkMuted,
                        fontSize: 11,
                        fontWeight: FontWeight.w700,
                        letterSpacing: 1.4,
                      ),
                    ),
                    const SizedBox(height: 3),
                    Text(
                      l.booklet_new_title,
                      style: const TextStyle(
                        color: PaColors.inkPrimary,
                        fontSize: 17,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    const SizedBox(height: 6),
                    // Le carnet est valide 1 an d'après le règlement
                    // intérieur ; on l'affiche explicitement pour cadrer
                    // l'attente avant le bouton commande.
                    Container(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 8, vertical: 3,),
                      decoration: BoxDecoration(
                        color: PaColors.tealSurface,
                        borderRadius: BorderRadius.circular(999),
                      ),
                      child: const Text(
                        'Validité 1 an',
                        style: TextStyle(
                          color: PaColors.teal,
                          fontSize: 11,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 18),
          _Step(number: '1', title: l.booklet_step1),
          const SizedBox(height: 10),
          _Step(number: '2', title: l.booklet_step2),
          const SizedBox(height: 10),
          _Step(number: '3', title: l.booklet_step3),
          const SizedBox(height: 18),
          SizedBox(
            width: double.infinity,
            child: Material(
              color: Colors.transparent,
              child: InkWell(
                onTap: () => OrderBookletSheet.show(context),
                borderRadius: BorderRadius.circular(999),
                child: Container(
                  height: 50,
                  decoration: BoxDecoration(
                    gradient: PaGradients.ctaPill,
                    borderRadius: BorderRadius.circular(999),
                  ),
                  alignment: Alignment.center,
                  child: Text(
                    l.booklet_order_cta,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                      color: PaColors.onTeal,
                      fontSize: 14.5,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}


class _Step extends StatelessWidget {
  const _Step({required this.number, required this.title});
  final String number;
  final String title;

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Container(
          width: 26,
          height: 26,
          decoration: const BoxDecoration(
            color: PaColors.tealSurface,
            shape: BoxShape.circle,
          ),
          alignment: Alignment.center,
          child: Text(
            number,
            style: const TextStyle(
              color: PaColors.teal,
              fontSize: 12,
              fontWeight: FontWeight.w800,
            ),
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: Padding(
            padding: const EdgeInsets.only(top: 4),
            child: Text(
              title,
              style: const TextStyle(
                color: PaColors.inkSecondary,
                fontSize: 13.5,
                height: 1.4,
              ),
            ),
          ),
        ),
      ],
    );
  }
}


// ───────────────────────────────────────────────────────────────────────────
// Tile historique (carnet livré)
// ───────────────────────────────────────────────────────────────────────────

class _HistoryTile extends StatelessWidget {
  const _HistoryTile({required this.order});
  final BookletOrder order;

  @override
  Widget build(BuildContext context) {
    final l = AppL10n.of(context);
    return PaCard(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      child: Row(
        children: [
          Container(
            width: 38,
            height: 38,
            decoration: BoxDecoration(
              color: PaColors.successSurface,
              borderRadius: BorderRadius.circular(11),
            ),
            child: const Icon(
              Icons.menu_book_outlined,
              color: PaColors.success,
              size: 19,
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  l.booklet_history_item('${order.id}'),
                  style: const TextStyle(
                    color: PaColors.inkPrimary,
                    fontSize: 14,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  l.booklet_history_delivered_on(
                    AppDateFormatter.long(
                      order.dateDelivrance ?? order.dateCommande,
                    ),
                  ),
                  style: const TextStyle(
                    color: PaColors.inkMuted,
                    fontSize: 12,
                  ),
                ),
              ],
            ),
          ),
          _StatusChip(label: l.booklet_status_delivered, color: PaColors.success),
        ],
      ),
    );
  }
}


// ───────────────────────────────────────────────────────────────────────────
// Helpers communs (chip status, errorbox)
// ───────────────────────────────────────────────────────────────────────────

class _StatusChip extends StatelessWidget {
  const _StatusChip({required this.label, required this.color});
  final String label;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.14),
        borderRadius: BorderRadius.circular(999),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 6,
            height: 6,
            decoration: BoxDecoration(color: color, shape: BoxShape.circle),
          ),
          const SizedBox(width: 6),
          Text(
            label,
            style: TextStyle(
              color: color,
              fontSize: 11.5,
              fontWeight: FontWeight.w700,
            ),
          ),
        ],
      ),
    );
  }
}


class _ErrorBox extends StatelessWidget {
  const _ErrorBox({required this.message});
  final String message;

  @override
  Widget build(BuildContext context) {
    final l = AppL10n.of(context);
    return PaCard(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Icon(Icons.error_outline, color: PaColors.danger, size: 24),
          const SizedBox(height: 8),
          Text(
            l.booklet_error_title,
            style: const TextStyle(
              color: PaColors.danger,
              fontSize: 16,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            message,
            style: const TextStyle(color: PaColors.inkMuted, fontSize: 12.5),
          ),
        ],
      ),
    );
  }
}
