import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../../app/theme/paysika/pa_colors.dart';
import '../../../../app/theme/paysika/pa_typography.dart';
import '../../../../core/formatters/date_formatter.dart';
import '../../../../core/formatters/xaf_formatter.dart';
import '../../../../core/widgets/paysika/pa_card.dart';
import '../../../../core/widgets/paysika/pa_pattern_background.dart';
import '../../../../core/widgets/skeleton.dart';
import '../../../../l10n/gen/app_localizations.dart';
import '../../../avaliste/presentation/state/avaliste_notifier.dart';
import '../../../loans/domain/entities/loan.dart';
import '../../../loans/domain/entities/loan_request.dart';
import '../../../loans/presentation/state/loans_notifier.dart';
import '../../../loans/presentation/widgets/loan_request_sheet.dart';
import '../../../loans/presentation/widgets/renewal_sheet.dart';
import '../../../loans/presentation/widgets/repayment_sheet.dart';

/// Page Crédit — style **Paysika** (palette navy/teal, cards soft).
///
/// Composition :
///   - Header simple (eyebrow + titre)
///   - Liste des Loans actifs (PaCard chacun) avec montant, statut, échéance
///     et 2 actions : « Rembourser » + « Reconduire »
///   - Liste des LoanRequest en cours (en instruction / contre-proposition)
///   - FAB **« + Nouvelle demande »** toujours visible — c'est l'élément
///     critique qui manquait avant.
class CreditPage extends ConsumerWidget {
  const CreditPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final loansAsync = ref.watch(loansProvider);
    final requestsAsync = ref.watch(loanRequestsProvider);
    final l = AppL10n.of(context);

    return Scaffold(
      backgroundColor: PaColors.canvas,
      body: PaPatternBackground(
        child: SafeArea(
        bottom: false,
        child: Column(
          children: [
            // ── Header FIXE ──────────────────────────────────────────────
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 16, 16, 12),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(l.credit_eyebrow.toUpperCase(), style: PaText.eyebrow()),
                  const SizedBox(height: 3),
                  Text(l.credit_title, style: PaText.heading(size: 22)),
                ],
              ),
            ),
            // ── Accès Mandats avaliste (LOT 21) ──────────────────────────
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
              child: _AvalisteEntryTile(),
            ),
            Expanded(
              child: RefreshIndicator.adaptive(
          color: PaColors.teal,
          onRefresh: () async {
            await Future.wait([
              ref.read(loansProvider.notifier).refresh(),
              ref.read(loanRequestsProvider.notifier).refresh(),
              ref.read(eligibilityProvider.notifier).refresh(),
            ]);
          },
          child: CustomScrollView(
            physics: const AlwaysScrollableScrollPhysics(),
            slivers: [
              // ── Crédits actifs ────────────────────────────────────────
              SliverToBoxAdapter(
                child: Padding(
                  padding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
                  child: loansAsync.when(
                    data: (loans) {
                      if (loans.isEmpty) {
                        return const _EmptyState();
                      }
                      return Column(
                        children: [
                          for (final loan in loans) ...[
                            _LoanCard(loan: loan),
                            const SizedBox(height: 12),
                          ],
                        ],
                      );
                    },
                    loading: () => const PaCard(
                      padding: EdgeInsets.symmetric(vertical: 30, horizontal: 16),
                      child: SkeletonList(lines: 3),
                    ),
                    error: (e, _) => _ErrorBox(message: e.toString()),
                  ),
                ),
              ),

              // ── Demandes en cours ────────────────────────────────────
              SliverToBoxAdapter(
                child: requestsAsync.maybeWhen(
                  data: (requests) => requests.isEmpty
                      ? const SizedBox.shrink()
                      : Padding(
                          padding: const EdgeInsets.fromLTRB(20, 14, 20, 8),
                          child: Text(
                            l.credit_requests_title,
                            style: const TextStyle(
                              color: PaColors.inkPrimary,
                              fontSize: 15,
                              fontWeight: FontWeight.w700,
                            ),
                          ),
                        ),
                  orElse: () => const SizedBox.shrink(),
                ),
              ),
              SliverToBoxAdapter(
                child: requestsAsync.maybeWhen(
                  data: (requests) => requests.isEmpty
                      ? const SizedBox.shrink()
                      : Padding(
                          padding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
                          child: Column(
                            children: [
                              for (final r in requests) ...[
                                _RequestCard(request: r),
                                const SizedBox(height: 10),
                              ],
                            ],
                          ),
                        ),
                  orElse: () => const SizedBox.shrink(),
                ),
              ),

              // ── Espace bas pour le FAB ───────────────────────────────
              const SliverToBoxAdapter(child: SizedBox(height: 100)),
            ],
          ),
              ),
            ),
          ],
        ),
        ),
      ),
      floatingActionButton: Consumer(
        builder: (context, ref, _) {
          final eligibility = ref.watch(eligibilityProvider).valueOrNull;
          final isLoading = eligibility == null;
          final isBlocked = eligibility != null && !eligibility.eligible;
          return _NewRequestFab(
            onPressed: isLoading
                ? null
                : isBlocked
                    ? () => _showIneligibilityDialog(context, eligibility.motifs)
                    : () => LoanRequestSheet.show(context, eligibility),
            disabled: isLoading || isBlocked,
          );
        },
      ),
    );
  }
}


// ───────────────────────────────────────────────────────────────────────────
// FAB « + Nouvelle demande » — gradient teal/cyan
// ───────────────────────────────────────────────────────────────────────────

class _NewRequestFab extends StatelessWidget {
  const _NewRequestFab({required this.onPressed, this.disabled = false});
  final VoidCallback? onPressed;
  final bool disabled;

  @override
  Widget build(BuildContext context) {
    final l = AppL10n.of(context);
    return Opacity(
      opacity: disabled ? 0.55 : 1.0,
      child: Container(
        decoration: BoxDecoration(
          gradient: PaGradients.ctaPill,
          borderRadius: BorderRadius.circular(999),
          boxShadow: [
            BoxShadow(
              color: PaColors.teal.withValues(alpha: 0.30),
              blurRadius: 16,
              offset: const Offset(0, 6),
            ),
          ],
        ),
        child: Material(
          color: Colors.transparent,
          child: InkWell(
            onTap: onPressed,
            borderRadius: BorderRadius.circular(999),
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 22, vertical: 14),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Icon(Icons.add_rounded, color: PaColors.onTeal, size: 20),
                  const SizedBox(width: 6),
                  Text(
                    l.credit_new_request,
                    style: const TextStyle(
                      color: PaColors.onTeal,
                      fontSize: 14.5,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}


// Dialog présenté au tap du FAB quand le membre n'est pas éligible à une
// nouvelle demande (typiquement : un crédit en cours non soldé — Règle 2 de
// compute_eligibility côté backend). Affiche les motifs renvoyés par l'API.
void _showIneligibilityDialog(BuildContext context, List<String> motifs) {
  showDialog<void>(
    context: context,
    builder: (ctx) => AlertDialog(
      title: const Text("Demande de crédit indisponible"),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            "Tu ne peux pas demander un nouveau crédit pour le moment :",
            style: TextStyle(fontSize: 14),
          ),
          const SizedBox(height: 12),
          ...motifs.map(
            (m) => Padding(
              padding: const EdgeInsets.only(bottom: 6),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text("• ", style: TextStyle(fontWeight: FontWeight.w700)),
                  Expanded(child: Text(m, style: const TextStyle(fontSize: 13.5))),
                ],
              ),
            ),
          ),
        ],
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(ctx).pop(),
          child: const Text("J'ai compris"),
        ),
      ],
    ),
  );
}


// ───────────────────────────────────────────────────────────────────────────
// Card Loan actif — montant + statut + prochaine échéance + 2 boutons
// ───────────────────────────────────────────────────────────────────────────

class _LoanCard extends StatelessWidget {
  const _LoanCard({required this.loan});
  final Loan loan;

  @override
  Widget build(BuildContext context) {
    final l = AppL10n.of(context);
    final next = loan.nextDue;
    final progression = loan.progression;
    final tauxPct = (loan.tauxInteret * 100).toStringAsFixed(0);
    final penalty = loan.penaltyDue(DateTime.now()); // Article 12

    final statusColor = switch (loan.statut) {
      LoanStatus.actif => PaColors.success,
      LoanStatus.enRetard => PaColors.warning,
      LoanStatus.cloture => PaColors.inkMuted,
      LoanStatus.contentieux => PaColors.danger,
    };
    final statusLabel = switch (loan.statut) {
      LoanStatus.actif => l.credit_status_active,
      LoanStatus.enRetard => l.credit_status_late,
      LoanStatus.cloture => l.credit_status_closed,
      LoanStatus.contentieux => l.credit_status_litigation,
    };

    return PaCard(
      padding: const EdgeInsets.all(18),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  loan.numeroDossier,
                  style: const TextStyle(
                    color: PaColors.inkMuted,
                    fontSize: 12.5,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ),
              _StatusChip(label: statusLabel, color: statusColor),
            ],
          ),
          const SizedBox(height: 10),
          Row(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Text(
                XAFFormatter.format(loan.soldeRestant),
                style: const TextStyle(
                  color: PaColors.inkPrimary,
                  fontSize: 26,
                  fontWeight: FontWeight.w700,
                  letterSpacing: -0.4,
                ),
              ),
              const SizedBox(width: 6),
              Padding(
                padding: const EdgeInsets.only(bottom: 4),
                child: Text(
                  l.credit_remaining,
                  style: const TextStyle(
                    color: PaColors.inkMuted,
                    fontSize: 13,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 4),
          Text(
            l.credit_due_total(XAFFormatter.format(loan.montantTotalDu), tauxPct),
            style: const TextStyle(color: PaColors.inkMuted, fontSize: 12.5),
          ),

          // Barre progression
          const SizedBox(height: 14),
          ClipRRect(
            borderRadius: BorderRadius.circular(999),
            child: LinearProgressIndicator(
              value: progression.clamp(0.0, 1.0),
              minHeight: 6,
              backgroundColor: PaColors.line,
              valueColor: const AlwaysStoppedAnimation<Color>(PaColors.teal),
            ),
          ),
          const SizedBox(height: 6),
          Text(
            l.credit_repaid_pct(
                (progression * 100).clamp(0, 100).toStringAsFixed(0)),
            style: const TextStyle(color: PaColors.inkMuted, fontSize: 12),
          ),

          // Prochaine échéance
          if (next != null) ...[
            const SizedBox(height: 14),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
              decoration: BoxDecoration(
                color: PaColors.appBg,
                borderRadius: BorderRadius.circular(10),
              ),
              child: Row(
                children: [
                  const Icon(
                    Icons.event_outlined,
                    color: PaColors.teal,
                    size: 18,
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          l.credit_next_due,
                          style: const TextStyle(
                            color: PaColors.inkMuted,
                            fontSize: 11.5,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                        const SizedBox(height: 1),
                        Text(
                          '${AppDateFormatter.long(next.dateEcheance)} · ${XAFFormatter.format(next.montantTotal)}',
                          style: const TextStyle(
                            color: PaColors.inkPrimary,
                            fontSize: 13.5,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ],

          // Pénalité de retard (Article 12) — visible seulement si exigible.
          if (penalty > 0) ...[
            const SizedBox(height: 12),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
              decoration: BoxDecoration(
                color: PaColors.dangerSurface,
                borderRadius: BorderRadius.circular(10),
              ),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Icon(Icons.gavel_rounded,
                      color: PaColors.danger, size: 18),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            Text(
                              l.credit_penalty_title,
                              style: const TextStyle(
                                color: PaColors.danger,
                                fontSize: 12.5,
                                fontWeight: FontWeight.w700,
                              ),
                            ),
                            Text(
                              XAFFormatter.format(penalty),
                              style: const TextStyle(
                                color: PaColors.danger,
                                fontSize: 13.5,
                                fontWeight: FontWeight.w700,
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 2),
                        Text(
                          l.credit_penalty_sub,
                          style: const TextStyle(
                            color: PaColors.inkSecondary,
                            fontSize: 11.5,
                            height: 1.4,
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ],

          // Actions
          const SizedBox(height: 16),
          Row(
            children: [
              Expanded(
                child: _PrimaryActionButton(
                  label: l.credit_repay,
                  onTap: () => RepaymentSheet.show(context, loan),
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: _OutlineActionButton(
                  label: l.credit_renew,
                  onTap: () => RenewalSheet.show(context, loan),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}


// ───────────────────────────────────────────────────────────────────────────
// Card LoanRequest en cours (instruction / décision attendue)
// ───────────────────────────────────────────────────────────────────────────

class _RequestCard extends StatelessWidget {
  const _RequestCard({required this.request});
  final LoanRequestEntity request;

  @override
  Widget build(BuildContext context) {
    final l = AppL10n.of(context);
    final statusColor = switch (request.statut) {
      LoanRequestStatus.enAttente => PaColors.warning,
      LoanRequestStatus.enInstruction => PaColors.teal,
      LoanRequestStatus.enAttenteAcceptationMembre => PaColors.teal,
      LoanRequestStatus.approuvee => PaColors.success,
      LoanRequestStatus.rejetee => PaColors.danger,
    };
    final statusLabel = switch (request.statut) {
      LoanRequestStatus.enAttente => l.credit_req_pending,
      LoanRequestStatus.enInstruction => l.credit_req_review,
      LoanRequestStatus.enAttenteAcceptationMembre => l.credit_req_counter,
      LoanRequestStatus.approuvee => l.credit_req_approved,
      LoanRequestStatus.rejetee => l.credit_req_rejected,
    };

    return PaCard(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  XAFFormatter.format(request.montantDemande),
                  style: const TextStyle(
                    color: PaColors.inkPrimary,
                    fontSize: 18,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ),
              _StatusChip(label: statusLabel, color: statusColor),
            ],
          ),
          const SizedBox(height: 4),
          Text(
            l.credit_req_submitted_on(AppDateFormatter.long(request.dateSoumission)),
            style: const TextStyle(color: PaColors.inkMuted, fontSize: 12.5),
          ),
          if (request.motif.isNotEmpty) ...[
            const SizedBox(height: 8),
            Text(
              request.motif,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(
                color: PaColors.inkSecondary,
                fontSize: 13,
                height: 1.4,
              ),
            ),
          ],
        ],
      ),
    );
  }
}


// ───────────────────────────────────────────────────────────────────────────
// Empty state — pas de crédit actif
// ───────────────────────────────────────────────────────────────────────────

class _EmptyState extends StatelessWidget {
  const _EmptyState();

  @override
  Widget build(BuildContext context) {
    final l = AppL10n.of(context);
    return PaCard(
      padding: const EdgeInsets.all(22),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 56,
            height: 56,
            decoration: const BoxDecoration(
              color: PaColors.tealSurface,
              shape: BoxShape.circle,
            ),
            alignment: Alignment.center,
            child: const Icon(
              Icons.account_balance_outlined,
              color: PaColors.teal,
              size: 28,
            ),
          ),
          const SizedBox(height: 14),
          Text(
            l.credit_empty_title,
            style: const TextStyle(
              color: PaColors.inkPrimary,
              fontSize: 17,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 6),
          Text(
            l.credit_empty_body,
            style: const TextStyle(
              color: PaColors.inkSecondary,
              fontSize: 13.5,
              height: 1.5,
            ),
          ),
          const SizedBox(height: 14),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
            decoration: BoxDecoration(
              color: PaColors.tealSurface,
              borderRadius: BorderRadius.circular(8),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Icon(Icons.arrow_downward_rounded,
                    color: PaColors.teal, size: 14),
                const SizedBox(width: 4),
                Text(
                  l.credit_empty_hint,
                  style: const TextStyle(
                    color: PaColors.teal,
                    fontSize: 12,
                    fontWeight: FontWeight.w700,
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
// Bouton primary (gradient cyan) — utilisé pour « Rembourser »
// ───────────────────────────────────────────────────────────────────────────

class _PrimaryActionButton extends StatelessWidget {
  const _PrimaryActionButton({required this.label, required this.onTap});
  final String label;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(999),
        child: Container(
          height: 44,
          decoration: BoxDecoration(
            gradient: PaGradients.ctaPill,
            borderRadius: BorderRadius.circular(999),
          ),
          alignment: Alignment.center,
          child: Text(
            label,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(
              color: PaColors.onTeal,
              fontSize: 13.5,
              fontWeight: FontWeight.w700,
            ),
          ),
        ),
      ),
    );
  }
}


// ───────────────────────────────────────────────────────────────────────────
// Bouton outline navy — utilisé pour « Reconduire »
// ───────────────────────────────────────────────────────────────────────────

class _OutlineActionButton extends StatelessWidget {
  const _OutlineActionButton({required this.label, required this.onTap});
  final String label;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: PaColors.paper,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(999),
        side: const BorderSide(color: PaColors.line, width: 1.2),
      ),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(999),
        child: Container(
          height: 44,
          alignment: Alignment.center,
          child: Text(
            label,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(
              color: PaColors.inkPrimary,
              fontSize: 13.5,
              fontWeight: FontWeight.w700,
            ),
          ),
        ),
      ),
    );
  }
}


// ───────────────────────────────────────────────────────────────────────────
// Status chip — petit pill coloré
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
      padding: const EdgeInsets.all(18),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Icon(Icons.error_outline, color: PaColors.danger, size: 24),
          const SizedBox(height: 8),
          Text(
            l.credit_unavailable,
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

/// Tuile d'accès aux mandats d'avaliste — badge avec compteur pending.
class _AvalisteEntryTile extends ConsumerWidget {
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final asyncMandats = ref.watch(avalisteProvider);
    final pendingCount = asyncMandats.maybeWhen(
      data: (d) => d.pendingCount,
      orElse: () => 0,
    );
    final hasPending = pendingCount > 0;
    return PaCard(
      onTap: () => context.push('/avaliste/mandats'),
      padding: const EdgeInsets.fromLTRB(14, 12, 14, 12),
      child: Row(
        children: [
          Container(
            width: 40,
            height: 40,
            decoration: BoxDecoration(
              color: (hasPending ? Colors.orange : PaColors.teal)
                  .withValues(alpha: 0.12),
              borderRadius: BorderRadius.circular(20),
            ),
            child: Icon(
              Icons.handshake_outlined,
              size: 22,
              color: hasPending ? Colors.orange.shade800 : PaColors.teal,
            ),
          ),
          const SizedBox(width: 12),
          const Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Mes mandats d\'avaliste',
                  style: TextStyle(
                    fontSize: 14.5,
                    fontWeight: FontWeight.w700,
                    color: PaColors.inkPrimary,
                  ),
                ),
                SizedBox(height: 2),
                Text(
                  'Réponds aux demandes où tu es désigné garant.',
                  style: TextStyle(fontSize: 12, color: PaColors.inkMuted),
                ),
              ],
            ),
          ),
          if (hasPending)
            Container(
              padding:
                  const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
              decoration: BoxDecoration(
                color: Colors.orange.shade700,
                borderRadius: BorderRadius.circular(999),
              ),
              child: Text(
                '$pendingCount',
                style: const TextStyle(
                  color: Colors.white,
                  fontSize: 12,
                  fontWeight: FontWeight.w700,
                ),
              ),
            )
          else
            const Icon(
              Icons.chevron_right,
              size: 22,
              color: PaColors.inkMuted,
            ),
        ],
      ),
    );
  }
}
