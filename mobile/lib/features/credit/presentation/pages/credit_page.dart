import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../../app/theme/app_typography.dart';
import '../../../../app/theme/paysika/pa_colors.dart';
import '../../../booklet/presentation/pages/booklet_page.dart';
import '../../../../core/di/providers.dart';
import '../../../../core/formatters/date_formatter.dart';
import '../../../../core/formatters/xaf_formatter.dart';
import '../../../../core/network/api_config.dart';
import '../../../../core/services/transaction_fee_provider.dart';
import '../../../../core/widgets/live_poller.dart';
import '../../../../core/widgets/payment_fee_breakdown.dart';
import '../../../../core/widgets/pdf_preview_page.dart';
import '../../../../core/widgets/paysika/pa_button.dart';
import '../../../../core/widgets/paysika/pa_card.dart';
import '../../../../core/widgets/paysika/pa_dialog.dart';
import '../../../../core/widgets/paysika/pa_gradient_header_band.dart';
import '../../../../core/widgets/paysika/pa_pattern_background.dart';
import '../../../../core/widgets/skeleton.dart';
import '../../../../l10n/gen/app_localizations.dart';
import '../../../avaliste/presentation/state/avaliste_notifier.dart';
import '../../../loans/domain/entities/eligibility.dart';
import '../../../loans/domain/entities/loan.dart';
import '../../../loans/domain/entities/loan_request.dart';
import '../../../loans/presentation/state/loans_notifier.dart';
import '../../../loans/presentation/widgets/loan_request_sheet.dart';
import '../../../loans/presentation/widgets/renewal_sheet.dart';
import '../../../loans/presentation/widgets/repayment_sheet.dart';
import '../../../../core/error/error_message.dart';

/// Page Crédit . style **Paysika** (palette navy/teal, cards soft).
///
/// Composition :
///   - Header simple (eyebrow + titre)
///   - Liste des Loans actifs (PaCard chacun) avec montant, statut, échéance
///     et 2 actions : « Rembourser » + « Reconduire »
///   - Liste des LoanRequest en cours (en instruction / contre-proposition)
///   - FAB **« + Nouvelle demande »** toujours visible . c'est l'élément
///     critique qui manquait avant.
class CreditPage extends ConsumerWidget {
  const CreditPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final loansAsync = ref.watch(loansProvider);
    final requestsAsync = ref.watch(loanRequestsProvider);
    // Garde les données affichées pendant les refresh du LivePoller (sinon la
    // section « Mes demandes » disparaît/réapparaît à chaque tick = flicker).
    final requests = requestsAsync.valueOrNull ?? const [];
    final l = AppL10n.of(context);

    // §6 / LOT 11 . La Home (carousel campagnes) pousse l'id d'une campagne
    // sélectionnée via ce StateProvider, puis route ici. Quand l'éligibilité
    // est résolue, on ouvre automatiquement le sheet de demande avec la
    // voie campagne pré-sélectionnée et l'id renseigné, puis on reset.
    ref.listen<int?>(pendingCampaignSelectionProvider, (_, next) {
      if (next == null) return;
      final eligibility = ref.read(eligibilityProvider).valueOrNull;
      if (eligibility == null) return;
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (!context.mounted) return;
        ref.read(pendingCampaignSelectionProvider.notifier).state = null;
        _startLoanRequestFlow(
          context,
          ref,
          eligibility,
          prefillCampaignId: next,
        );
      });
    });

    return DefaultTabController(
      length: 2,
      child: Scaffold(
      backgroundColor: PaColors.canvas,
      body: PaPatternBackground(
        child: SafeArea(
        bottom: false,
        child: Column(
          children: [
            // Polling 30 s sur loans + loanRequests pour voir en quasi-temps-reel
            // les changements d'etat fait cote dashboard admin (approbation
            // provisoire, encaissement frais d'etude, decision definitive...).
            // Idempotence via hash : pas de rebuild si la donnee est inchangee.
            LivePoller(
              branchIndex: 1,
              refresh: () => ref.read(loansProvider.notifier).refresh(),
              readSnapshot: () => ref.read(loansProvider).valueOrNull,
            ),
            LivePoller(
              branchIndex: 1,
              refresh: () => ref.read(loanRequestsProvider.notifier).refresh(),
              readSnapshot: () => ref.read(loanRequestsProvider).valueOrNull,
            ),
            // ── Header FIXE compact . band gradient soft vert→bleu ──────
            PaGradientHeaderBand(title: l.credit_title),
            const SizedBox(height: 12),
            // ── Sélecteur segmenté Crédit | Carnet (refonte nav 2026) ────
            const Padding(
              padding: EdgeInsets.fromLTRB(16, 0, 16, 10),
              child: _CreditCarnetTabs(),
            ),
            Expanded(
              child: TabBarView(
                children: [
                  // ═══════════ Onglet CRÉDIT ═══════════
                  Column(
                    children: [
            // ── Accès Mandats avaliste (LOT 21) ──────────────────────────
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
              child: _AvalisteEntryTile(),
            ),
            // ── CH-12 . Mes versements prêteur (Sinora §5.3) ──────────────
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
              child: _LenderPayoutsEntryTile(),
            ),
            Expanded(
              child: RefreshIndicator.adaptive(
          color: PaColors.teal,
          onRefresh: () async {
            await Future.wait([
              ref.read(loansProvider.notifier).refresh(),
              ref.read(loanRequestsProvider.notifier).refresh(),
              ref.read(eligibilityProvider.notifier).refresh(),
              ref.read(closedLoansProvider.notifier).refresh(),
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
                    // Ne repasse PAS en squelette lors des refresh du poller.
                    skipLoadingOnRefresh: true,
                    skipLoadingOnReload: true,
                    data: (loans) {
                      if (loans.isEmpty) {
                        // Ne PAS afficher « pas encore de crédit » si le membre
                        // a une demande en cours : elle est déjà rendue dans la
                        // section « Demandes en cours » juste en dessous, donc
                        // la carte vide serait contradictoire. On ne la montre
                        // que s'il n'a NI crédit actif NI demande.
                        if (requests.isNotEmpty) {
                          return const SizedBox.shrink();
                        }
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
                    error: (e, _) => _ErrorBox(message: friendlyError(e)),
                  ),
                ),
              ),

              // ── Crédits clôturés (masquables par le membre) ───────────
              const SliverToBoxAdapter(child: _ClosedLoansSection()),

              // ── Voies de crédit disponibles (refonte 2026) ──────────
              //     Refonte 2026 LOT 12 : 3 voies d'éligibilité existent
              //     côté backend (SENIOR_BRC / AVALISTE / CAMPAGNE). Cette
              //     section les rend visibles au membre avant qu'il ne
              //     soumette une demande, pour qu'il sache laquelle il vise.
              SliverToBoxAdapter(
                child: Padding(
                  padding: const EdgeInsets.fromLTRB(20, 14, 20, 8),
                  child: Text(
                    l.credit_paths_title,
                    style: const TextStyle(
                      color: PaColors.inkPrimary,
                      fontSize: 14,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ),
              ),
              SliverToBoxAdapter(
                child: Consumer(
                  builder: (context, ref, _) {
                    final eligibility =
                        ref.watch(eligibilityProvider).valueOrNull;
                    return _LoanRoutesCarousel(
                      onSelect: eligibility == null
                          ? null
                          : (voie) => _startLoanRequestFlow(
                                context,
                                ref,
                                eligibility,
                                voie: voie,
                              ),
                    );
                  },
                ),
              ),

              // ── Demandes en cours ────────────────────────────────────
              SliverToBoxAdapter(
                child: requests.isEmpty
                    ? const SizedBox.shrink()
                    : Padding(
                        padding: const EdgeInsets.fromLTRB(20, 14, 20, 8),
                        child: Text(
                          l.credit_requests_title,
                          style: const TextStyle(
                            color: PaColors.inkPrimary,
                            fontSize: 14,
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                      ),
              ),
              SliverToBoxAdapter(
                child: requests.isEmpty
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
              ),

              // ── Espace bas pour le FAB ───────────────────────────────
              const SliverToBoxAdapter(child: SizedBox(height: 100)),
            ],
          ),
              ),
            ),
                    ],
                  ),
                  // ═══════════ Onglet CARNET ═══════════
                  const BookletBody(),
                ],
              ),
            ),
          ],
        ),
        ),
      ),
      floatingActionButton: Consumer(
        builder: (context, ref, _) {
          final eligibility = ref.watch(eligibilityProvider).valueOrNull;
          // On observe AUSSI les demandes en cours : une demande déjà en
          // instruction bloque une nouvelle (sinon le « + » ouvrait le
          // formulaire pour rien → 400 au submit).
          final requests =
              ref.watch(loanRequestsProvider).valueOrNull ?? const [];
          final hasBlockingRequest =
              requests.any((r) => r.statut.blocksNewLoanRequest);
          final isLoading = eligibility == null;
          final isBlocked = hasBlockingRequest ||
              (eligibility != null && !eligibility.eligible);
          return _NewRequestFab(
            onPressed: isLoading
                ? null
                : () => _startLoanRequestFlow(context, ref, eligibility),
            disabled: isLoading || isBlocked,
          );
        },
      ),
      ),
    );
  }
}


// ───────────────────────────────────────────────────────────────────────────
// FAB « + Nouvelle demande » . gradient teal/cyan
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
      child: Tooltip(
        message: l.credit_new_request,
        child: Container(
          width: 56,
          height: 56,
          decoration: BoxDecoration(
            gradient: PaGradients.ctaPill,
            shape: BoxShape.circle,
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
            shape: const CircleBorder(),
            child: InkWell(
              onTap: onPressed,
              customBorder: const CircleBorder(),
              child: const Center(
                child: Icon(Icons.add_rounded, color: PaColors.onTeal, size: 28),
              ),
            ),
          ),
        ),
      ),
    );
  }
}


// Motif affiché quand une demande est DÉJÀ en cours de traitement. Le backend
// rejette de toute façon une 2e demande (« demande en cours »), mais on l'
// explique AVANT d'ouvrir le formulaire — au lieu de laisser le membre remplir
// pour rien puis se heurter à un 400.
const String _kRequestInProgressMotif =
    'Tu as déjà une demande de crédit en cours de traitement. Attends la '
    'décision (ou la clôture du crédit) avant d\'en soumettre une nouvelle.';

/// Point d'entrée UNIQUE pour lancer une demande de crédit. Vérifie d'abord :
///   1. qu'aucune demande n'est déjà en cours (statut bloquant), et
///   2. que l'éligibilité backend est OK (pas de crédit actif non soldé…).
/// Si l'un des deux bloque, affiche le message explicatif ; sinon ouvre le
/// formulaire. Centralisé pour que TOUS les points d'entrée (FAB, carrousel
/// des voies, sélection d'une campagne depuis la Home) soient gardés pareil.
void _startLoanRequestFlow(
  BuildContext context,
  WidgetRef ref,
  Eligibility eligibility, {
  LoanRequestVoie? voie,
  int? prefillCampaignId,
}) {
  final requests = ref.read(loanRequestsProvider).valueOrNull ?? const [];
  final hasBlockingRequest =
      requests.any((r) => r.statut.blocksNewLoanRequest);
  final motifs = <String>[
    if (hasBlockingRequest) _kRequestInProgressMotif,
    if (!eligibility.eligible) ...eligibility.motifs,
  ];
  if (motifs.isNotEmpty) {
    _showIneligibilityDialog(context, motifs);
    return;
  }
  LoanRequestSheet.show(
    context,
    eligibility,
    initialVoie: voie,
    prefillCampaignId: prefillCampaignId,
  );
}

// Dialog présenté au tap du FAB quand le membre n'est pas éligible à une
// nouvelle demande (typiquement : un crédit en cours non soldé . Règle 2 de
// compute_eligibility côté backend, ou une demande déjà en cours). Affiche les
// motifs.
void _showIneligibilityDialog(BuildContext context, List<String> motifs) {
  showPaAlert(
    context,
    icon: Icons.block_rounded,
    accent: PaColors.danger,
    title: 'Demande de crédit indisponible',
    message: 'Tu ne peux pas demander un nouveau crédit pour le moment :',
    bullets: motifs,
  );
}


// ───────────────────────────────────────────────────────────────────────────
// Card Loan actif . montant + statut + prochaine échéance + 2 boutons
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
                    fontSize: 12,
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
            style: const TextStyle(color: PaColors.inkMuted, fontSize: 12),
          ),

          // CH-11 . Annonce explicite « intérêts retenus à la source ».
          if (loan.modeRetenueInterets == LoanInterestMode.source &&
              loan.montantDecaisseNet != null) ...[
            const SizedBox(height: 6),
            Container(
              padding:
                  const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
              decoration: BoxDecoration(
                color: PaColors.success.withValues(alpha: 0.10),
                borderRadius: BorderRadius.circular(10),
              ),
              child: Row(
                children: [
                  const Icon(Icons.bolt_rounded,
                      size: 14, color: PaColors.success,),
                  const SizedBox(width: 6),
                  Expanded(
                    child: Text(
                      'Net versé : ${XAFFormatter.format(loan.montantDecaisseNet!)} '
                      '· intérêts retenus à la source',
                      style: const TextStyle(
                        color: PaColors.success,
                        fontSize: 11,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ],

          // CH-8 . Date butoire formelle si posée.
          if (loan.dateButoire != null) ...[
            const SizedBox(height: 6),
            Text(
              'Date butoire : ${_formatDateShort(loan.dateButoire!)}',
              style: const TextStyle(
                color: PaColors.inkMuted,
                fontSize: 11,
                fontWeight: FontWeight.w500,
              ),
            ),
          ],

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
                (progression * 100).clamp(0, 100).toStringAsFixed(0),),
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
                            fontSize: 11,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                        const SizedBox(height: 1),
                        Text(
                          '${AppDateFormatter.long(next.dateEcheance)} · ${XAFFormatter.format(next.montantTotal)}',
                          style: const TextStyle(
                            color: PaColors.inkPrimary,
                            fontSize: 13,
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

          // Pénalité de retard (Article 12) . visible seulement si exigible.
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
                      color: PaColors.danger, size: 18,),
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
                                fontSize: 12,
                                fontWeight: FontWeight.w700,
                              ),
                            ),
                            Text(
                              XAFFormatter.format(penalty),
                              style: const TextStyle(
                                color: PaColors.danger,
                                fontSize: 13,
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
                            fontSize: 11,
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

/// L6 . Statuts « encore en cours d'étude » : la demande n'a pas encore reçu
/// de décision définitive (ni approuvée, ni rejetée). C'est le seul cas où
/// l'échéance indicative d'étude reste pertinente à afficher.
bool _isUnderStudy(LoanRequestStatus statut) {
  switch (statut) {
    case LoanRequestStatus.enAttente:
    case LoanRequestStatus.enInstruction:
    case LoanRequestStatus.enAttenteAcceptationMembre:
    case LoanRequestStatus.approuveeProvisoire:
    case LoanRequestStatus.enAttenteAvaliste:
    case LoanRequestStatus.enValidationCampagne:
    case LoanRequestStatus.enAttenteFunding:
      return true;
    case LoanRequestStatus.approuvee:
    case LoanRequestStatus.rejetee:
    case LoanRequestStatus.rejeteeAvaliste:
    case LoanRequestStatus.rejeteeCampagne:
      return false;
  }
}

class _RequestCard extends ConsumerWidget {
  const _RequestCard({required this.request});
  final LoanRequestEntity request;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = AppL10n.of(context);
    final statusColor = switch (request.statut) {
      LoanRequestStatus.enAttente => PaColors.warning,
      LoanRequestStatus.enInstruction => PaColors.teal,
      LoanRequestStatus.enAttenteAcceptationMembre => PaColors.teal,
      LoanRequestStatus.approuveeProvisoire => PaColors.warning,
      LoanRequestStatus.approuvee => PaColors.success,
      LoanRequestStatus.rejetee => PaColors.danger,
      // Sous-etats fins (refonte 2026)
      LoanRequestStatus.enAttenteAvaliste => PaColors.warning,
      LoanRequestStatus.rejeteeAvaliste => PaColors.danger,
      LoanRequestStatus.enValidationCampagne => PaColors.teal,
      LoanRequestStatus.rejeteeCampagne => PaColors.danger,
      LoanRequestStatus.enAttenteFunding => PaColors.warning,
    };
    final statusLabel = switch (request.statut) {
      LoanRequestStatus.enAttente => l.credit_status_fee_due,
      LoanRequestStatus.enInstruction => l.credit_req_review,
      LoanRequestStatus.enAttenteAcceptationMembre => l.credit_req_counter,
      LoanRequestStatus.approuveeProvisoire => l.credit_status_field_visit,
      LoanRequestStatus.approuvee => l.credit_req_approved,
      LoanRequestStatus.rejetee => l.credit_req_rejected,
      LoanRequestStatus.enAttenteAvaliste => l.credit_status_await_avaliste,
      LoanRequestStatus.rejeteeAvaliste => l.credit_status_rejected_avaliste,
      LoanRequestStatus.enValidationCampagne =>
        l.credit_status_campaign_validation,
      LoanRequestStatus.rejeteeCampagne => l.credit_status_rejected_campaign,
      LoanRequestStatus.enAttenteFunding => l.credit_status_await_funding,
    };

    return PaCard(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Montant en haut, statut en dessous : un libellé de statut long ne
          // chevauche plus le montant sur petit écran.
          Text(
            XAFFormatter.format(request.montantDemande),
            style: const TextStyle(
              color: PaColors.inkPrimary,
              fontSize: 18,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 6),
          Align(
            alignment: Alignment.centerLeft,
            child: _StatusChip(label: statusLabel, color: statusColor),
          ),
          const SizedBox(height: 4),
          Text(
            l.credit_req_submitted_on(AppDateFormatter.long(request.dateSoumission)),
            style: const TextStyle(color: PaColors.inkMuted, fontSize: 12),
          ),
          // L6 . Échéance indicative d'étude de la commission (soumission +
          // ~1 mois). Affichée tant que la demande est encore en cours
          // d'examen (statuts non terminaux) et si le backend a fourni la date.
          if (request.dateLimiteEtude != null && _isUnderStudy(request.statut)) ...[
            const SizedBox(height: 4),
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Icon(Icons.schedule_rounded,
                    size: 14, color: PaColors.inkMuted,),
                const SizedBox(width: 5),
                Expanded(
                  child: Text(
                    'Étude sous 1 semaine à 1 mois — échéance le '
                    '${AppDateFormatter.long(request.dateLimiteEtude!)}',
                    style: const TextStyle(
                        color: PaColors.inkMuted, fontSize: 12,),
                  ),
                ),
              ],
            ),
          ],
          // §6 . Badge de la voie empruntee (BRC / Avaliste / Campagne) si connu.
          if (request.route != null) ...[
            const SizedBox(height: 6),
            _RouteBadge(route: request.route!),
          ],
          // Voie avaliste : le demandeur doit connaître le montant que son
          // garant s'engage à couvrir (le manque = montant − son épargne dispo).
          if (request.route == LoanRoute.avaliste &&
              (request.avalisteMontantACouvrir ?? 0) > 0) ...[
            const SizedBox(height: 6),
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Icon(Icons.handshake_outlined,
                    size: 14, color: PaColors.teal,),
                const SizedBox(width: 5),
                Expanded(
                  child: Text(
                    'Votre avaliste doit couvrir '
                    '${XAFFormatter.format(request.avalisteMontantACouvrir!)} '
                    'sur ce crédit.',
                    style: const TextStyle(
                      color: PaColors.inkSecondary,
                      fontSize: 12,
                      height: 1.35,
                    ),
                  ),
                ),
              ],
            ),
          ],
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
          // Flow de la demande — timeline VERTICALE (beaucoup d'étapes
          // possibles selon la voie, d'où le format vertical plutôt qu'horizontal).
          const SizedBox(height: 14),
          _CreditFlowTimeline(status: request.statut),

          // CH-9 . Bouton « Télécharger ma note » disponible à tout moment
          // après création (la note PDF reflète l'état courant : moyen de
          // réception, échéancier si Loan créé, etc.).
          const SizedBox(height: 10),
          InkWell(
            onTap: () => _openLoanNote(context, request.id),
            borderRadius: BorderRadius.circular(8),
            child: Padding(
              padding: const EdgeInsets.symmetric(vertical: 4),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Icon(Icons.picture_as_pdf_rounded,
                      size: 16, color: PaColors.teal,),
                  const SizedBox(width: 6),
                  Text(
                    'Télécharger ma note PDF',
                    style: AppTypography.bodySmall.copyWith(
                      color: PaColors.teal,
                      fontWeight: FontWeight.w600,
                      decoration: TextDecoration.underline,
                      decorationColor: PaColors.teal,
                    ),
                  ),
                ],
              ),
            ),
          ),
          // Voie campagne : la demande attend la validation du comité. Les
          // frais d'étude ne deviennent réglables qu'APRÈS validation (le
          // statut passe alors à en_attente). On l'explique clairement.
          if (request.statut == LoanRequestStatus.enValidationCampagne) ...[
            const SizedBox(height: 12),
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: PaColors.blue.withValues(alpha: 0.08),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: PaColors.blue.withValues(alpha: 0.22)),
              ),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Icon(Icons.hourglass_top_rounded,
                      size: 18, color: PaColors.blue,),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      'En attente de validation par le comité. Une fois votre '
                      'candidature validée, vous pourrez régler vos frais '
                      'd\'étude ici même.',
                      style: AppTypography.bodySmall.copyWith(
                        color: PaColors.inkMuted,
                        height: 1.35,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ],
          // CH-7 . Le CTA de paiement des frais d'étude n'apparaît QUE si la
          // demande est en_attente ET que les frais ne sont pas encore réglés.
          // Anti double-paiement : une demande peut rester en_attente frais DÉJÀ
          // payés (bénéficiaire campagne qui attend son carnet) — dans ce cas on
          // n'affiche plus le bouton (sinon le membre re-paierait), mais une note.
          if (request.statut == LoanRequestStatus.enAttente &&
              !request.fraisPaye) ...[
            const SizedBox(height: 12),
            SizedBox(
              width: double.infinity,
              child: ElevatedButton.icon(
                onPressed: () =>
                    _StudyFeePaySheet.show(context, request: request),
                icon: const Icon(Icons.receipt_long_rounded, size: 18),
                label: const Text('Payer les frais d\'étude'),
                style: ElevatedButton.styleFrom(
                  backgroundColor: PaColors.warning,
                  foregroundColor: Colors.white,
                  padding: const EdgeInsets.symmetric(vertical: 12),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                  ),
                  textStyle: const TextStyle(
                    fontWeight: FontWeight.w700,
                    fontSize: 13,
                  ),
                ),
              ),
            ),
          ] else if (request.statut == LoanRequestStatus.enAttente &&
              request.fraisPaye) ...[
            const SizedBox(height: 12),
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: PaColors.success.withValues(alpha: 0.08),
                borderRadius: BorderRadius.circular(12),
                border:
                    Border.all(color: PaColors.success.withValues(alpha: 0.22)),
              ),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Icon(Icons.check_circle_outline_rounded,
                      size: 18, color: PaColors.success,),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      'Frais d\'étude réglés. Votre dossier finalise sa mise en '
                      'place — aucun autre paiement n\'est requis pour le moment.',
                      style: AppTypography.bodySmall.copyWith(
                        color: PaColors.inkMuted,
                        height: 1.35,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ],
      ),
    );
  }
}

/// CH-7 . Sheet compact pour régler les frais d'étude depuis la page Crédit
/// quand la demande est restée bloquée en `enAttente`.
/// Timeline VERTICALE du parcours d'une demande de crédit. Le crédit ayant
/// beaucoup d'états possibles (3 voies, double approbation, funding…), le
/// format vertical reste lisible là où un stepper horizontal serait trop serré.
class _CreditFlowTimeline extends StatelessWidget {
  const _CreditFlowTimeline({required this.status});
  final LoanRequestStatus status;

  bool get _rejected => switch (status) {
        LoanRequestStatus.rejetee ||
        LoanRequestStatus.rejeteeAvaliste ||
        LoanRequestStatus.rejeteeCampagne =>
          true,
        _ => false,
      };

  // Index de l'étape courante (0..4).
  int get _reached => switch (status) {
        // Frais d'étude à payer → l'étape « Frais d'étude » est la courante.
        LoanRequestStatus.enAttente => 1,
        // Voies avaliste / campagne : pré-étape non finie → encore à « Soumise »
        // (elles n'ont pas atteint la porte des frais d'étude).
        LoanRequestStatus.enAttenteAvaliste ||
        LoanRequestStatus.enValidationCampagne =>
          0,
        LoanRequestStatus.enInstruction => 2,
        LoanRequestStatus.enAttenteAcceptationMembre ||
        LoanRequestStatus.approuveeProvisoire ||
        LoanRequestStatus.enAttenteFunding =>
          3,
        LoanRequestStatus.approuvee => 4,
        LoanRequestStatus.rejetee ||
        LoanRequestStatus.rejeteeAvaliste ||
        LoanRequestStatus.rejeteeCampagne =>
          3,
      };

  @override
  Widget build(BuildContext context) {
    final l = AppL10n.of(context);
    final steps = [
      l.credit_step_submitted,
      l.credit_step_fee_paid,
      l.credit_step_committee,
      l.credit_step_decision,
      l.credit_step_granted,
    ];
    // Si rejeté, on s'arrête à « Décision » (pas de « Crédit accordé »).
    final count = _rejected ? 4 : steps.length;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        for (var i = 0; i < count; i++)
          _VStep(
            index: i + 1,
            label: (_rejected && i == 3) ? l.credit_step_rejected : steps[i],
            done: i < _reached && !(_rejected && i == 3),
            active: i == _reached && !_rejected,
            rejected: _rejected && i == 3,
            isLast: i == count - 1,
          ),
      ],
    );
  }
}

class _VStep extends StatelessWidget {
  const _VStep({
    required this.index,
    required this.label,
    required this.done,
    required this.active,
    required this.rejected,
    required this.isLast,
  });

  final int index;
  final String label;
  final bool done;
  final bool active;
  final bool rejected;
  final bool isLast;

  @override
  Widget build(BuildContext context) {
    final Color circle = rejected
        ? PaColors.danger
        : done
            ? PaColors.teal
            : active
                ? PaColors.navy
                : PaColors.paper;
    final Color border = (rejected || done || active) ? circle : PaColors.line;
    final Color txt = (rejected || done || active) ? Colors.white : PaColors.inkMuted;
    final Color labelColor = rejected
        ? PaColors.danger
        : active
            ? PaColors.navy
            : done
                ? PaColors.teal
                : PaColors.inkMuted;

    return IntrinsicHeight(
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Column(
            children: [
              Container(
                width: 26,
                height: 26,
                decoration: BoxDecoration(
                  color: circle,
                  shape: BoxShape.circle,
                  border: Border.all(color: border, width: 1.5),
                ),
                alignment: Alignment.center,
                child: rejected
                    ? const Icon(Icons.close_rounded, size: 15, color: Colors.white)
                    : done
                        ? const Icon(Icons.check_rounded, size: 15, color: Colors.white)
                        : Text(
                            '$index',
                            style: TextStyle(
                              color: txt,
                              fontSize: 12,
                              fontWeight: FontWeight.w700,
                            ),
                          ),
              ),
              if (!isLast)
                Expanded(
                  child: Container(
                    width: 2,
                    color: done ? PaColors.teal : PaColors.line,
                  ),
                ),
            ],
          ),
          const SizedBox(width: 12),
          Padding(
            padding: EdgeInsets.only(top: 4, bottom: isLast ? 0 : 14),
            child: Text(
              label,
              style: TextStyle(
                color: labelColor,
                fontSize: 13,
                fontWeight: active || rejected ? FontWeight.w700 : FontWeight.w600,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

/// Porte des frais 2026 — les 3 canaux de règlement, un seul au choix.
enum _FeeChannel { deduction, momo, agence }

class _StudyFeePaySheet extends ConsumerStatefulWidget {
  const _StudyFeePaySheet({required this.request});

  /// La demande à régler. Porte le montant (piloté admin, non éditable) et le
  /// retirable, qui décide si la déduction — canal par défaut — est tenable.
  final LoanRequestEntity request;

  static Future<void> show(BuildContext context,
      {required LoanRequestEntity request,}) {
    return showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Theme.of(context).colorScheme.surface,
      barrierColor: Colors.black.withValues(alpha: 0.45),
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(28)),
      ),
      builder: (_) => _StudyFeePaySheet(request: request),
    );
  }

  @override
  ConsumerState<_StudyFeePaySheet> createState() => _StudyFeePaySheetState();
}

class _StudyFeePaySheetState extends ConsumerState<_StudyFeePaySheet> {
  final _phoneCtrl = TextEditingController();
  bool _loading = false;
  late _FeeChannel _channel;

  int? get _montant => widget.request.fraisEtudeMontant?.round();

  @override
  void initState() {
    super.initState();
    // La déduction est le canal par défaut — mais seulement si le retirable
    // couvre les frais. Sinon on bascule d'office sur Mobile Money plutôt que
    // de pré-sélectionner un canal qui se ferait refuser.
    _channel = widget.request.peutDeduireSurEpargne
        ? _FeeChannel.deduction
        : _FeeChannel.momo;
  }

  @override
  void dispose() {
    _phoneCtrl.dispose();
    super.dispose();
  }

  /// Déduction sur épargne : transfert interne, donc synchrone. Pas de Tara,
  /// pas de notification à valider — au retour, la demande a déjà avancé.
  Future<void> _submitDeduction() async {
    unawaited(HapticFeedback.mediumImpact());
    setState(() => _loading = true);
    try {
      await ref
          .read(loanRequestsProvider.notifier)
          .payStudyFeeFromSavings(requestId: widget.request.id);
      if (!mounted) return;
      unawaited(HapticFeedback.heavyImpact());
      Navigator.of(context).pop();
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text(
            'Frais réglés sur votre épargne . votre dossier part en étude.',
          ),
        ),
      );
    } catch (err) {
      if (!mounted) return;
      setState(() => _loading = false);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(friendlyError(err))),
      );
    }
  }

  Future<void> _submit() async {
    final phone = _phoneCtrl.text.trim();
    if (phone.length < 9) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Numéro Mobile Money requis (au moins 9 chiffres).'),
        ),
      );
      return;
    }
    final amount = _montant;
    if (amount == null || amount <= 0) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Montant des frais indisponible.')),
      );
      return;
    }
    unawaited(HapticFeedback.mediumImpact());
    setState(() => _loading = true);
    try {
      await ref.read(loanRequestsProvider.notifier).payStudyFee(
            phone: phone,
            // Opérateur non requis : Tara le détecte via le préfixe du numéro.
            network: '',
            montant: amount,
          );
      if (!mounted) return;
      unawaited(HapticFeedback.heavyImpact());
      Navigator.of(context).pop();
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text(
            'Paiement initié . validez la notification Mobile Money sur votre téléphone.',
          ),
        ),
      );
    } catch (err) {
      if (!mounted) return;
      setState(() => _loading = false);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(friendlyError(err))),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.only(
        bottom: MediaQuery.viewInsetsOf(context).bottom,
      ),
      child: SafeArea(
        top: false,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(20, 12, 20, 28),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Center(
                child: Container(
                  width: 36,
                  height: 4,
                  decoration: BoxDecoration(
                    color: Theme.of(context).colorScheme.outline,
                    borderRadius: BorderRadius.circular(2),
                  ),
                ),
              ),
              const SizedBox(height: 18),
              const Text(
                'Régler les frais d\'étude',
                style: TextStyle(
                  fontSize: 20,
                  fontWeight: FontWeight.w700,
                  color: PaColors.inkPrimary,
                ),
              ),
              const SizedBox(height: 6),
              const Text(
                'Ces frais d\'étude sont non-remboursables et débloquent '
                'l\'instruction de votre demande.',
                style: TextStyle(
                  color: PaColors.inkSecondary,
                  fontSize: 13,
                  height: 1.45,
                ),
              ),
              const SizedBox(height: 20),
              const Text('Comment voulez-vous régler ?',
                  style: TextStyle(
                      color: PaColors.inkSecondary,
                      fontSize: 13,
                      fontWeight: FontWeight.w600,),),
              const SizedBox(height: 8),
              Row(
                children: [
                  Expanded(
                    child: _FeeChannelChip(
                      label: 'Mon épargne',
                      icon: Icons.savings_rounded,
                      selected: _channel == _FeeChannel.deduction,
                      // Grisé si le retirable ne couvre pas les frais : le
                      // placement et l'épargne gelée en garantie ne sont pas
                      // ponctionnables.
                      enabled: widget.request.peutDeduireSurEpargne,
                      onTap: () =>
                          setState(() => _channel = _FeeChannel.deduction),
                    ),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: _FeeChannelChip(
                      label: 'Mobile Money',
                      icon: Icons.phone_iphone_rounded,
                      selected: _channel == _FeeChannel.momo,
                      onTap: () => setState(() => _channel = _FeeChannel.momo),
                    ),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: _FeeChannelChip(
                      label: 'Agence',
                      icon: Icons.store_rounded,
                      selected: _channel == _FeeChannel.agence,
                      onTap: () => setState(() => _channel = _FeeChannel.agence),
                    ),
                  ),
                ],
              ),
              if (!widget.request.peutDeduireSurEpargne) ...[
                const SizedBox(height: 8),
                Text(
                  'Épargne disponible : '
                  '${XAFFormatter.format(widget.request.epargneDisponibleFrais.round())} '
                  '. insuffisant pour ces frais. Votre placement et votre '
                  'épargne gelée en garantie ne sont pas ponctionnables.',
                  style: const TextStyle(
                    color: PaColors.inkSecondary,
                    fontSize: 11,
                    height: 1.4,
                  ),
                ),
              ],
              if (_channel == _FeeChannel.momo) ...[
                const SizedBox(height: 20),
                const Text('Numéro Mobile Money',
                    style: TextStyle(
                        color: PaColors.inkSecondary,
                        fontSize: 13,
                        fontWeight: FontWeight.w600,),),
                const SizedBox(height: 8),
                TextFormField(
                  controller: _phoneCtrl,
                  keyboardType: TextInputType.phone,
                  decoration: const InputDecoration(
                    hintText: '+237 6XX XX XX XX',
                    prefixIcon: Icon(Icons.phone_iphone_rounded, size: 20),
                    contentPadding:
                        EdgeInsets.symmetric(horizontal: 16, vertical: 14),
                  ),
                ),
              ],
              if (_channel == _FeeChannel.agence) ...[
                const SizedBox(height: 16),
                const Text(
                  'Présentez-vous à Akwa, Douala (Bercy), du lundi au vendredi '
                  'entre 08h00 et 17h00, avec votre numéro de membre. L\'agent '
                  'enregistre le règlement et votre dossier part aussitôt en '
                  'étude.',
                  style: TextStyle(
                    color: PaColors.inkSecondary,
                    fontSize: 13,
                    height: 1.45,
                  ),
                ),
              ],
              if (_montant != null) ...[
                const SizedBox(height: 16),
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    const Text('Frais d\'étude',
                        style: TextStyle(
                            color: PaColors.inkSecondary,
                            fontSize: 13,
                            fontWeight: FontWeight.w600,),),
                    Text(
                      XAFFormatter.format(_montant!),
                      style: const TextStyle(
                        color: PaColors.inkPrimary,
                        fontSize: 14,
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                  ],
                ),
                // Frais de transaction (%) — Mobile Money uniquement. Un
                // transfert interne (déduction) et un versement en espèces à
                // l'agence n'en supportent aucun.
                if (_channel == _FeeChannel.momo)
                  PaymentFeeBreakdown(
                    montant: _montant ?? 0,
                    rate:
                        ref.watch(transactionFeeRateProvider).valueOrNull ?? 0.0,
                  ),
              ],
              const SizedBox(height: 22),
              if (_channel == _FeeChannel.agence)
                PaButton(
                  label: 'J\'ai compris',
                  onPressed: () => Navigator.of(context).pop(),
                )
              else
                PaButton(
                  label: _channel == _FeeChannel.deduction
                      ? 'Régler sur mon épargne'
                      : 'Payer maintenant',
                  onPressed: _channel == _FeeChannel.deduction
                      ? _submitDeduction
                      : _submit,
                  loading: _loading,
                ),
            ],
          ),
        ),
      ),
    );
  }
}

// ───────────────────────────────────────────────────────────────────────────
// Empty state . pas de crédit actif
// ───────────────────────────────────────────────────────────────────────────

class _EmptyState extends StatelessWidget {
  const _EmptyState();

  @override
  Widget build(BuildContext context) {
    final l = AppL10n.of(context);
    // Empty-state soft & compact : une ligne icône + texte, un petit indice
    // dessous. Beaucoup moins imposant que l'ancienne grosse carte.
    return PaCard(
      padding: const EdgeInsets.all(14),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 38,
            height: 38,
            decoration: const BoxDecoration(
              color: PaColors.tealSurface,
              shape: BoxShape.circle,
            ),
            alignment: Alignment.center,
            child: const Icon(
              Icons.account_balance_outlined,
              color: PaColors.teal,
              size: 19,
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  l.credit_empty_title,
                  style: const TextStyle(
                    color: PaColors.inkPrimary,
                    fontSize: 14,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                const SizedBox(height: 3),
                Text(
                  l.credit_empty_body,
                  style: const TextStyle(
                    color: PaColors.inkSecondary,
                    fontSize: 12,
                    height: 1.35,
                  ),
                ),
                const SizedBox(height: 8),
                Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Icon(Icons.arrow_downward_rounded,
                        color: PaColors.teal, size: 13,),
                    const SizedBox(width: 4),
                    Text(
                      l.credit_empty_hint,
                      style: const TextStyle(
                        color: PaColors.teal,
                        fontSize: 11,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ],
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
// Bouton primary (gradient cyan) . utilisé pour « Rembourser »
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
              fontSize: 13,
              fontWeight: FontWeight.w700,
            ),
          ),
        ),
      ),
    );
  }
}


// ───────────────────────────────────────────────────────────────────────────
// Bouton outline navy . utilisé pour « Reconduire »
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
              fontSize: 13,
              fontWeight: FontWeight.w700,
            ),
          ),
        ),
      ),
    );
  }
}


// ───────────────────────────────────────────────────────────────────────────
// Status chip . petit pill coloré
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
              fontSize: 11,
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
            style: const TextStyle(color: PaColors.inkMuted, fontSize: 12),
          ),
        ],
      ),
    );
  }
}

/// Tuile d'accès aux mandats d'avaliste . badge avec compteur pending.
class _AvalisteEntryTile extends ConsumerWidget {
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = AppL10n.of(context);
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
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  l.credit_mandates_title,
                  style: const TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w700,
                    color: PaColors.inkPrimary,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  l.credit_mandates_sub,
                  style: const TextStyle(fontSize: 12, color: PaColors.inkMuted),
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


// CH-8 . Format court pour la date butoire affichée sur les cartes Loan.
String _formatDateShort(DateTime d) {
  const mois = [
    'janv', 'févr', 'mars', 'avril', 'mai', 'juin',
    'juil', 'août', 'sept', 'oct', 'nov', 'déc',
  ];
  return '${d.day} ${mois[d.month - 1]} ${d.year}';
}


// CH-9 . Ouvre la note PDF d'une demande de crédit dans le viewer interne.
// IMPORTANT : on passe par PdfPreviewPage (qui récupère le binaire via le Dio
// de l'app, cookie de session inclus) et NON par le navigateur système —
// celui-ci a son propre magasin de cookies, la requête arriverait donc non
// authentifiée et le backend renverrait un 403 (page vide).
Future<void> _openLoanNote(BuildContext context, int requestId) async {
  await PdfPreviewPage.open(
    context,
    url: '${ApiConfig.apiBase}/loans/requests/$requestId/note/',
    title: 'Ma note de crédit',
  );
}


/// CH-12 . Tuile d'accès aux versements prêteur. Affichée seulement si
/// l'API a renvoyé au moins un payout (sinon on évite de polluer la page
/// Crédit avec une porte vide). Compteur+total perçu en aperçu rapide.
class _LenderPayoutsEntryTile extends ConsumerWidget {
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(myLenderPayoutsProvider);
    final items = async.maybeWhen(data: (d) => d, orElse: () => null);
    if (items == null || items.isEmpty) return const SizedBox.shrink();

    final total = items.fold<num>(0, (s, p) => s + p.montant);
    return PaCard(
      onTap: () => context.push('/me/lender-payouts'),
      padding: const EdgeInsets.fromLTRB(14, 12, 14, 12),
      child: Row(
        children: [
          Container(
            width: 40,
            height: 40,
            decoration: BoxDecoration(
              color: PaColors.success.withValues(alpha: 0.12),
              borderRadius: BorderRadius.circular(20),
            ),
            child: const Icon(
              Icons.savings_rounded,
              size: 22,
              color: PaColors.success,
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Mes intérêts de prêteur',
                  style: TextStyle(
                    color: PaColors.inkPrimary,
                    fontSize: 14,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  '${items.length} versement${items.length > 1 ? "s" : ""} · '
                  'total ${XAFFormatter.format(total)}',
                  style: const TextStyle(
                    color: PaColors.inkSecondary,
                    fontSize: 12,
                  ),
                ),
              ],
            ),
          ),
          const Icon(
            Icons.chevron_right_rounded,
            size: 22,
            color: PaColors.inkMuted,
          ),
        ],
      ),
    );
  }
}


// ───────────────────────────────────────────────────────────────────────────
// Carousel des voies de crédit « spéciales » (LOT 12)
//
// Le carrousel n'expose que les voies qui nécessitent une SAISIE particulière :
//   • AVALISTE     . garant désigné qui comble le manque (LOT 10/18)
//   • CAMPAGNE     . crédit rattaché à une campagne active
//   • GARANTIE     . bien matériel déclaré en garantie
//
// La voie « CLASSIQUE » (par défaut : auto-couverture épargne ou ancienneté)
// n'a PAS de carte — elle s'ouvre via le FAB « + Nouvelle demande » (sheet sans
// voie présélectionnée). Une carte « Classique » ferait doublon avec le FAB.
// ───────────────────────────────────────────────────────────────────────────

class _LoanRoutesCarousel extends StatelessWidget {
  const _LoanRoutesCarousel({
    required this.onSelect,
  });

  // Callback avec la voie touchée → ouvre le formulaire présélectionné.
  // Null tant que l'éligibilité n'est pas chargée (cartes désactivées).
  final void Function(LoanRequestVoie voie)? onSelect;

  @override
  Widget build(BuildContext context) {
    final l = AppL10n.of(context);
    final ready = onSelect != null;

    // Carrousel des voies « spéciales » (avaliste, campagne, garantie). La voie
    // par défaut (« classique » : auto-couverture ou ancienneté) n'a PAS de
    // carte : elle s'ouvre via le FAB « + Nouvelle demande » (sheet sans voie
    // présélectionnée). Les 3 cartes tiennent sur UNE ligne (Row + Expanded),
    // hauteurs égalisées via IntrinsicHeight.
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16),
      child: IntrinsicHeight(
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Expanded(
              child: _LoanRouteCard(
                icon: Icons.handshake_rounded,
                iconColor: PaColors.blue,
                iconBg: const Color(0xFFE8EEFC),
                title: l.credit_path_avaliste_title,
                statusOk: true,
                onTap: ready ? () => onSelect!(LoanRequestVoie.avaliste) : null,
              ),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: _LoanRouteCard(
                icon: Icons.campaign_rounded,
                iconColor: PaColors.warning,
                iconBg: PaColors.warningSurface,
                title: l.credit_path_campaign_title,
                statusOk: true,
                onTap: ready ? () => onSelect!(LoanRequestVoie.campaign) : null,
              ),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: _LoanRouteCard(
                icon: Icons.home_work_rounded,
                iconColor: PaColors.blue,
                iconBg: const Color(0xFFE8EEFC),
                title: l.credit_path_garantie_title,
                statusOk: true,
                onTap: ready
                    ? () => onSelect!(LoanRequestVoie.garantieMaterielle)
                    : null,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// Carte de voie de crédit — design allégé (icône + libellé + point d'état).
///
/// Le membre choisit sa voie d'un coup d'œil : plus de sous-texte ni de
/// pilule textuelle « Disponible / Non éligible ». L'état se lit sur un
/// simple point coloré — **vert** = voie ouverte, **rouge** = indisponible
/// (typiquement BRC quand le membre n'est pas encore éligible).
class _LoanRouteCard extends StatelessWidget {
  const _LoanRouteCard({
    required this.icon,
    required this.iconColor,
    required this.iconBg,
    required this.title,
    required this.statusOk,
    required this.onTap,
  });

  final IconData icon;
  final Color iconColor;
  final Color iconBg;
  final String title;
  final bool statusOk;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final disabled = onTap == null;
    return Opacity(
      opacity: disabled ? 0.55 : 1.0,
      // Carte compacte conçue pour vivre dans un Expanded (4 par ligne).
      child: PaCard(
        padding: const EdgeInsets.all(11),
        onTap: onTap,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            Row(
              children: [
                Container(
                  width: 34,
                  height: 34,
                  decoration: BoxDecoration(
                    color: iconBg,
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Icon(icon, color: iconColor, size: 19),
                ),
                const Spacer(),
                // Point d'état : vert = voie disponible, rouge = indisponible.
                Container(
                  width: 9,
                  height: 9,
                  decoration: BoxDecoration(
                    color: statusOk ? PaColors.success : PaColors.danger,
                    shape: BoxShape.circle,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 9),
            Text(
              title,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(
                color: PaColors.inkPrimary,
                fontSize: 13,
                fontWeight: FontWeight.w700,
                height: 1.2,
              ),
            ),
          ],
        ),
      ),
    );
  }
}


/// Badge "Voie empruntee" affiche sur chaque carte LoanRequest pour que le
/// membre voie clairement par quel chemin sa demande passe (Classique,
/// Avaliste, Campagne) . aide a comprendre le statut + le delai.
class _RouteBadge extends StatelessWidget {
  const _RouteBadge({required this.route});

  final LoanRoute route;

  @override
  Widget build(BuildContext context) {
    // Voie 1 « Classique » : auto-couverture (épargne classique dispo >=
    // montant) ou ancienneté >= seuil. Le BRC n'est plus saisi à la demande
    // (pièce documentaire traitée au back-office).
    final (label, icon, color) = switch (route) {
      LoanRoute.seniorBrc => (
        'Voie classique',
        Icons.workspace_premium_rounded,
        PaColors.teal,
      ),
      LoanRoute.avaliste => (
        'Voie Avaliste',
        Icons.handshake_rounded,
        PaColors.navy,
      ),
      LoanRoute.campagne => (
        'Voie Campagne',
        Icons.campaign_rounded,
        PaColors.warning,
      ),
      LoanRoute.garantieMaterielle => (
        'Voie Garantie',
        Icons.home_work_rounded,
        PaColors.blue,
      ),
    };
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.10),
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: color.withValues(alpha: 0.30), width: 0.8),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, color: color, size: 13),
          const SizedBox(width: 5),
          Text(
            label,
            style: TextStyle(
              color: color,
              fontSize: 11,
              fontWeight: FontWeight.w700,
              letterSpacing: 0.2,
            ),
          ),
        ],
      ),
    );
  }
}


/// Sélecteur de canal de règlement des frais d'étude.
///
/// Calqué sur `_ChannelChip` du sheet de retrait (même vocabulaire visuel pour
/// le membre), avec en plus un état désactivé : la déduction sur épargne n'est
/// proposable que si le retirable couvre les frais.
class _FeeChannelChip extends StatelessWidget {
  const _FeeChannelChip({
    required this.label,
    required this.icon,
    required this.selected,
    required this.onTap,
    this.enabled = true,
  });

  final String label;
  final IconData icon;
  final bool selected;
  final VoidCallback onTap;
  final bool enabled;

  @override
  Widget build(BuildContext context) {
    final fg = !enabled
        ? PaColors.inkMuted
        : selected
            ? PaColors.teal
            : PaColors.inkPrimary;
    return Opacity(
      opacity: enabled ? 1 : 0.5,
      child: InkWell(
        onTap: enabled ? onTap : null,
        borderRadius: BorderRadius.circular(14),
        child: Container(
          padding: const EdgeInsets.symmetric(vertical: 12, horizontal: 8),
          decoration: BoxDecoration(
            color: selected && enabled ? PaColors.tealSurface : PaColors.paper,
            borderRadius: BorderRadius.circular(14),
            border: Border.all(
              color: selected && enabled
                  ? PaColors.teal
                  : PaColors.inkMuted.withValues(alpha: 0.2),
              width: selected && enabled ? 1.6 : 1,
            ),
          ),
          child: Column(
            children: [
              Icon(icon, color: fg, size: 22),
              const SizedBox(height: 6),
              Text(
                label,
                textAlign: TextAlign.center,
                style: TextStyle(
                  color: fg,
                  fontSize: 12,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}


/// Sélecteur segmenté « pilule » en tête de la page Crédit : bascule entre
/// l'onglet Crédit et l'onglet Carnet (refonte nav 2026). S'appuie sur le
/// DefaultTabController qui enveloppe la page.
class _CreditCarnetTabs extends StatelessWidget {
  const _CreditCarnetTabs();

  @override
  Widget build(BuildContext context) {
    final l = AppL10n.of(context);
    return Container(
      height: 44,
      padding: const EdgeInsets.all(4),
      decoration: BoxDecoration(
        color: PaColors.tealSurface.withValues(alpha: 0.6),
        borderRadius: BorderRadius.circular(999),
      ),
      child: TabBar(
        indicator: BoxDecoration(
          color: PaColors.teal,
          borderRadius: BorderRadius.circular(999),
          boxShadow: [
            BoxShadow(
              color: PaColors.teal.withValues(alpha: 0.28),
              blurRadius: 10,
              offset: const Offset(0, 3),
            ),
          ],
        ),
        indicatorSize: TabBarIndicatorSize.tab,
        dividerColor: Colors.transparent,
        splashBorderRadius: BorderRadius.circular(999),
        labelColor: Colors.white,
        unselectedLabelColor: PaColors.inkSecondary,
        labelStyle: const TextStyle(fontSize: 13, fontWeight: FontWeight.w700),
        unselectedLabelStyle:
            const TextStyle(fontSize: 13, fontWeight: FontWeight.w600),
        tabs: [
          Tab(text: l.credit_tab_credit),
          Tab(text: l.credit_tab_carnet),
        ],
      ),
    );
  }
}


// ═══════════════════════════════════════════════════════════════════════════
// Crédits CLÔTURÉS — un crédit dont les remboursements sont finis apparaît en
// « Clôturé ». Le membre peut le masquer de sa vue (soft-hide) : rien n'est
// supprimé côté coopérative (audit/compta intacts).
// ═══════════════════════════════════════════════════════════════════════════
class _ClosedLoansSection extends ConsumerWidget {
  const _ClosedLoansSection();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = AppL10n.of(context);
    final loans = ref.watch(closedLoansProvider).valueOrNull ?? const <Loan>[];
    if (loans.isEmpty) return const SizedBox.shrink();

    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 4, 16, 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.only(bottom: 8, left: 2),
            child: Text(
              l.credit_closed_section_title,
              style: const TextStyle(
                color: PaColors.inkMuted,
                fontSize: 12,
                fontWeight: FontWeight.w700,
                letterSpacing: 0.2,
              ),
            ),
          ),
          for (final loan in loans) ...[
            _ClosedLoanCard(loan: loan),
            const SizedBox(height: 8),
          ],
        ],
      ),
    );
  }
}

class _ClosedLoanCard extends ConsumerWidget {
  const _ClosedLoanCard({required this.loan});

  final Loan loan;

  Future<void> _confirmHide(BuildContext context, WidgetRef ref) async {
    final l = AppL10n.of(context);
    final ok = await showPaConfirm(
      context,
      icon: Icons.visibility_off_rounded,
      title: l.credit_hide_confirm_title,
      message: l.credit_hide_confirm_body,
      confirmLabel: l.credit_hide_action,
      cancelLabel: l.credit_hide_cancel,
      danger: true,
    );
    if (!ok || !context.mounted) return;
    try {
      await ref.read(closedLoansProvider.notifier).hide(loan.id);
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(l.credit_hide_done)),
        );
      }
    } catch (e) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(friendlyError(e))),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = AppL10n.of(context);
    return PaCard(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '#${loan.numeroDossier}',
                  style: const TextStyle(
                    color: PaColors.inkPrimary,
                    fontSize: 12,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                const SizedBox(height: 1),
                Text(
                  XAFFormatter.format(loan.montant),
                  style: const TextStyle(
                    color: PaColors.inkMuted,
                    fontSize: 11,
                  ),
                ),
              ],
            ),
          ),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
            decoration: BoxDecoration(
              color: PaColors.inkMuted.withValues(alpha: 0.10),
              borderRadius: BorderRadius.circular(20),
            ),
            child: Text(
              l.credit_status_closed,
              style: const TextStyle(
                color: PaColors.inkSecondary,
                fontSize: 11,
                fontWeight: FontWeight.w700,
              ),
            ),
          ),
          const SizedBox(width: 2),
          // Cible tactile standard (≥ 48dp — Material/HIG) : on garde le
          // tapTargetSize.padded par défaut, juste un padding horizontal réduit.
          TextButton(
            onPressed: () => _confirmHide(context, ref),
            style: TextButton.styleFrom(
              foregroundColor: PaColors.danger,
              padding: const EdgeInsets.symmetric(horizontal: 10),
              visualDensity: VisualDensity.standard,
            ),
            child: Text(l.credit_hide_action),
          ),
        ],
      ),
    );
  }
}
