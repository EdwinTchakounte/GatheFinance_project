import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../../../app/theme/app_typography.dart';
import '../../../../app/theme/paysika/pa_colors.dart';
import '../../../../core/di/providers.dart';
import '../../../../core/formatters/date_formatter.dart';
import '../../../../core/formatters/xaf_formatter.dart';
import '../../../../core/network/api_config.dart';
import '../../../../core/widgets/live_poller.dart';
import '../../../../core/widgets/paysika/pa_card.dart';
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
        LoanRequestSheet.show(
          context,
          eligibility,
          prefillCampaignId: next,
        );
      });
    });

    return Scaffold(
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
              refresh: () => ref.read(loansProvider.notifier).refresh(),
              readSnapshot: () => ref.read(loansProvider).valueOrNull,
            ),
            LivePoller(
              refresh: () => ref.read(loanRequestsProvider.notifier).refresh(),
              readSnapshot: () => ref.read(loanRequestsProvider).valueOrNull,
            ),
            // ── Header FIXE compact . band gradient soft vert→bleu ──────
            PaGradientHeaderBand(title: l.credit_title),
            const SizedBox(height: 12),
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

              // ── Voies de crédit disponibles (refonte 2026) ──────────
              //     Refonte 2026 LOT 12 : 3 voies d'éligibilité existent
              //     côté backend (SENIOR_BRC / AVALISTE / CAMPAGNE). Cette
              //     section les rend visibles au membre avant qu'il ne
              //     soumette une demande, pour qu'il sache laquelle il vise.
              const SliverToBoxAdapter(
                child: Padding(
                  padding: EdgeInsets.fromLTRB(20, 14, 20, 8),
                  child: Text(
                    'Vos voies de crédit',
                    style: TextStyle(
                      color: PaColors.inkPrimary,
                      fontSize: 15,
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
                      eligibility: eligibility,
                      onSelect: eligibility == null
                          ? null
                          : (voie) => LoanRequestSheet.show(
                                context,
                                eligibility,
                                initialVoie: voie,
                              ),
                    );
                  },
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


// Dialog présenté au tap du FAB quand le membre n'est pas éligible à une
// nouvelle demande (typiquement : un crédit en cours non soldé . Règle 2 de
// compute_eligibility côté backend). Affiche les motifs renvoyés par l'API.
void _showIneligibilityDialog(BuildContext context, List<String> motifs) {
  showDialog<void>(
    context: context,
    builder: (ctx) => AlertDialog(
      title: const Text('Demande de crédit indisponible'),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'Tu ne peux pas demander un nouveau crédit pour le moment :',
            style: TextStyle(fontSize: 14),
          ),
          const SizedBox(height: 12),
          ...motifs.map(
            (m) => Padding(
              padding: const EdgeInsets.only(bottom: 6),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('• ', style: TextStyle(fontWeight: FontWeight.w700)),
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
                        fontSize: 11.5,
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
                fontSize: 11.5,
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
      LoanRequestStatus.enAttente => 'Frais d\'étude à payer',
      LoanRequestStatus.enInstruction => l.credit_req_review,
      LoanRequestStatus.enAttenteAcceptationMembre => l.credit_req_counter,
      LoanRequestStatus.approuveeProvisoire => 'Visite terrain à effectuer',
      LoanRequestStatus.approuvee => l.credit_req_approved,
      LoanRequestStatus.rejetee => l.credit_req_rejected,
      LoanRequestStatus.enAttenteAvaliste =>
        'En attente de l\'avaliste',
      LoanRequestStatus.rejeteeAvaliste => 'Refusée par l\'avaliste',
      LoanRequestStatus.enValidationCampagne =>
        'En validation activité campagne',
      LoanRequestStatus.rejeteeCampagne => 'Refusée (campagne)',
      LoanRequestStatus.enAttenteFunding =>
        'En attente de financement (24h)',
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
          // §6 . Badge de la voie empruntee (BRC / Avaliste / Campagne) si connu.
          if (request.route != null) ...[
            const SizedBox(height: 6),
            _RouteBadge(route: request.route!),
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
          // CH-7 . Tant que la demande est en_attente, les frais d'étude n'ont
          // pas encore été réglés et la demande ne passe pas en instruction.
          // On propose un CTA visible pour relancer le paiement Tara depuis
          // la page Crédit (cas du membre qui a fermé le sheet avant de payer).
          if (request.statut == LoanRequestStatus.enAttente) ...[
            const SizedBox(height: 12),
            SizedBox(
              width: double.infinity,
              child: ElevatedButton.icon(
                onPressed: () => _StudyFeePaySheet.show(context),
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
                    fontSize: 13.5,
                  ),
                ),
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
class _StudyFeePaySheet extends ConsumerStatefulWidget {
  const _StudyFeePaySheet();

  static Future<void> show(BuildContext context) {
    return showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Theme.of(context).colorScheme.surface,
      barrierColor: Colors.black.withValues(alpha: 0.45),
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(28)),
      ),
      builder: (_) => const _StudyFeePaySheet(),
    );
  }

  @override
  ConsumerState<_StudyFeePaySheet> createState() => _StudyFeePaySheetState();
}

class _StudyFeePaySheetState extends ConsumerState<_StudyFeePaySheet> {
  final _phoneCtrl = TextEditingController();
  // TODO: REMOVE_FOR_PROD . montant éditable pour tester STK Push à 100 XAF.
  final _amountCtrl = TextEditingController(text: '100');
  bool _loading = false;

  @override
  void dispose() {
    _phoneCtrl.dispose();
    _amountCtrl.dispose();
    super.dispose();
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
    final amount = int.tryParse(_amountCtrl.text.trim());
    if (amount == null || amount < 100) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Montant min : 100 XAF.')),
      );
      return;
    }
    unawaited(HapticFeedback.mediumImpact());
    setState(() => _loading = true);
    try {
      await ref.read(loanRequestsProvider.notifier).payStudyFee(
            phone: phone,
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
        SnackBar(content: Text(err.toString())),
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
              const SizedBox(height: 16),
              // TODO: REMOVE_FOR_PROD . montant éditable mode test.
              const Text('Montant (XAF) . mode test',
                  style: TextStyle(
                      color: PaColors.inkSecondary,
                      fontSize: 13,
                      fontWeight: FontWeight.w600,),),
              const SizedBox(height: 8),
              TextFormField(
                controller: _amountCtrl,
                keyboardType: TextInputType.number,
                decoration: const InputDecoration(
                  hintText: '100',
                  suffixText: 'XAF',
                  contentPadding:
                      EdgeInsets.symmetric(horizontal: 16, vertical: 14),
                ),
              ),
              const SizedBox(height: 22),
              SizedBox(
                width: double.infinity,
                child: ElevatedButton(
                  onPressed: _loading ? null : _submit,
                  style: ElevatedButton.styleFrom(
                    backgroundColor: PaColors.navy,
                    foregroundColor: Colors.white,
                    padding: const EdgeInsets.symmetric(vertical: 14),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(14),
                    ),
                  ),
                  child: _loading
                      ? const SizedBox(
                          width: 18,
                          height: 18,
                          child: CircularProgressIndicator(
                              strokeWidth: 2, color: Colors.white,),
                        )
                      : const Text(
                          'Payer maintenant',
                          style: TextStyle(
                            fontWeight: FontWeight.w700,
                            fontSize: 14.5,
                          ),
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
                    fontSize: 14.5,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                const SizedBox(height: 3),
                Text(
                  l.credit_empty_body,
                  style: const TextStyle(
                    color: PaColors.inkSecondary,
                    fontSize: 12.5,
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
                        fontSize: 11.5,
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

/// Tuile d'accès aux mandats d'avaliste . badge avec compteur pending.
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


// CH-8 . Format court pour la date butoire affichée sur les cartes Loan.
String _formatDateShort(DateTime d) {
  const mois = [
    'janv', 'févr', 'mars', 'avril', 'mai', 'juin',
    'juil', 'août', 'sept', 'oct', 'nov', 'déc',
  ];
  return '${d.day} ${mois[d.month - 1]} ${d.year}';
}


// CH-9 . Ouvre la note PDF d'une demande de crédit dans le navigateur
// système (la session cookie du backend est partagée avec le webview/Chrome
// Custom Tab, donc l'auth fonctionne pour les membres déjà connectés).
Future<void> _openLoanNote(BuildContext context, int requestId) async {
  final url = Uri.parse(
    '${ApiConfig.apiBase}/loans/requests/$requestId/note/',
  );
  final ok = await launchUrl(
    url,
    mode: LaunchMode.externalApplication,
  );
  if (!context.mounted) return;
  if (!ok) {
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Impossible d\'ouvrir la note PDF.')),
    );
  }
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
                    fontSize: 14.5,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  '${items.length} versement${items.length > 1 ? "s" : ""} · '
                  'total ${XAFFormatter.format(total)}',
                  style: const TextStyle(
                    color: PaColors.inkSecondary,
                    fontSize: 12.5,
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
// Carousel des voies de crédit éligibles au membre (LOT 12)
//
// Avant le chantier juin 2026, le membre voyait un seul bouton « Nouvelle
// demande ». Depuis la refonte (3 produits + 3 voies), le membre voit
// désormais ses voies disponibles :
//   • SENIOR_BRC   . voie senior éligibles BRC, plafond = solde × ratio
//   • AVALISTE     . voie classique avec garant désigné (LOT 10/18)
//
// La voie CAMPAGNE n'est PAS exposée ici : elle est réservée aux
// bénéficiaires non-adhérents (Membre TEMPORAIRE), recrutés via la
// vitrine web. Les campagnes actives sont affichées séparément sur la
// Home (cf. Phase 2 . section "Campagnes en cours") avec un bouton de
// partage, mais elles ne donnent pas accès au formulaire crédit membre.
// ───────────────────────────────────────────────────────────────────────────

class _LoanRoutesCarousel extends StatelessWidget {
  const _LoanRoutesCarousel({
    required this.eligibility,
    required this.onSelect,
  });

  final Eligibility? eligibility;
  // Callback avec la voie touchée → ouvre le formulaire présélectionné.
  final void Function(LoanRequestVoie voie)? onSelect;

  @override
  Widget build(BuildContext context) {
    final elig = eligibility;
    final isEligible = elig != null && elig.eligible;
    final plafond = elig?.plafondMax;
    final ready = onSelect != null;

    // Les 3 voies tiennent sur UNE ligne (Row + Expanded), hauteurs égalisées
    // via IntrinsicHeight. Toucher une carte ouvre le formulaire sur la voie.
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16),
      child: IntrinsicHeight(
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Expanded(
              child: _LoanRouteCard(
                icon: Icons.workspace_premium_rounded,
                iconColor: PaColors.teal,
                iconBg: PaColors.tealSurface,
                title: 'BRC',
                subtitle: plafond != null && plafond > 0
                    ? '${_formatPlafond(plafond)} XAF'
                    : 'Selon épargne',
                statusLabel: isEligible ? 'Disponible' : 'Non éligible',
                statusOk: isEligible,
                onTap: ready && isEligible
                    ? () => onSelect!(LoanRequestVoie.brc)
                    : null,
              ),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: _LoanRouteCard(
                icon: Icons.handshake_rounded,
                iconColor: PaColors.blue,
                iconBg: const Color(0xFFE8EEFC),
                title: 'Avaliste',
                subtitle: 'Garant désigné',
                statusLabel: 'Disponible',
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
                title: 'Campagne',
                subtitle: 'Micro-crédit',
                statusLabel: 'Disponible',
                statusOk: true,
                onTap: ready ? () => onSelect!(LoanRequestVoie.campaign) : null,
              ),
            ),
          ],
        ),
      ),
    );
  }

  static String _formatPlafond(num value) {
    final str = value.toInt().toString();
    final buf = StringBuffer();
    for (int i = 0; i < str.length; i++) {
      if (i > 0 && (str.length - i) % 3 == 0) buf.write(' ');
      buf.write(str[i]);
    }
    return buf.toString();
  }
}

class _LoanRouteCard extends StatelessWidget {
  const _LoanRouteCard({
    required this.icon,
    required this.iconColor,
    required this.iconBg,
    required this.title,
    required this.subtitle,
    required this.statusLabel,
    required this.statusOk,
    required this.onTap,
  });

  final IconData icon;
  final Color iconColor;
  final Color iconBg;
  final String title;
  final String subtitle;
  final String statusLabel;
  final bool statusOk;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final disabled = onTap == null;
    return Opacity(
      opacity: disabled ? 0.6 : 1.0,
      // Carte compacte conçue pour vivre dans un Expanded (3 par ligne).
      child: PaCard(
        padding: const EdgeInsets.all(11),
        onTap: onTap,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
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
            const SizedBox(height: 9),
            Text(
              title,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(
                color: PaColors.inkPrimary,
                fontSize: 13,
                fontWeight: FontWeight.w700,
              ),
            ),
            const SizedBox(height: 3),
            Text(
              subtitle,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(
                color: PaColors.inkSecondary,
                fontSize: 10.5,
                height: 1.25,
              ),
            ),
            const SizedBox(height: 9),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 3),
              decoration: BoxDecoration(
                color: statusOk
                    ? PaColors.successSurface
                    : PaColors.warningSurface,
                borderRadius: BorderRadius.circular(999),
              ),
              child: Text(
                statusLabel,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: TextStyle(
                  color: statusOk ? PaColors.success : PaColors.warning,
                  fontSize: 9.5,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}


/// Badge "Voie empruntee" affiche sur chaque carte LoanRequest pour que le
/// membre voie clairement par quel chemin sa demande passe (BRC, Avaliste,
/// Campagne) . aide a comprendre le statut + le delai.
class _RouteBadge extends StatelessWidget {
  const _RouteBadge({required this.route});

  final LoanRoute route;

  @override
  Widget build(BuildContext context) {
    // Voie 1 . membre du CGA BRC ou ancien apprenant CFP BRC + anciennete
    // >= 12 mois. Les 2 justificatifs sont uploades au moment de la
    // demande de credit (un seul suffit).
    final (label, icon, color) = switch (route) {
      LoanRoute.seniorBrc => (
        'Voie BRC',
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
              fontSize: 11.5,
              fontWeight: FontWeight.w700,
              letterSpacing: 0.2,
            ),
          ),
        ],
      ),
    );
  }
}
