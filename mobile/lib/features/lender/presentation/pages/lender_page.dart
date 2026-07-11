import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../app/theme/paysika/pa_colors.dart';
import '../../../../core/formatters/date_formatter.dart';
import '../../../../core/formatters/xaf_formatter.dart';
import '../../../../core/widgets/live_poller.dart';
import '../../../../core/widgets/paysika/pa_card.dart';
import '../../../../core/widgets/paysika/pa_pattern_background.dart';
import '../../domain/entities/lender_state.dart';
import '../state/lender_notifier.dart';
import '../../../../core/error/error_message.dart';

/// Espace prêteur du membre (équivalent mobile du portail Next.js).
///
/// Affiche en lecture la convention signée, les tranches par statut, et les
/// agrégats XAF. Permet :
///   - opt-in (signature convention globale)
///   - revoke (si pas de tranche engagée)
///   - addTranche (rendre une nouvelle tranche disponible)
///
/// Pas d'écran d'acceptation par-funding : l'admin engage les tranches
/// directement, le prêteur reçoit une notif et les intérêts sont crédités
/// automatiquement sur son compte épargne classique.
class LenderPage extends ConsumerWidget {
  const LenderPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(lenderProvider);
    return Scaffold(
      backgroundColor: PaColors.canvas,
      body: Stack(
        children: [
          // Polling 30s : voit les engagements admin sur ses tranches +
          // crediter intérêts sans avoir a pull-to-refresh.
          LivePoller(
            refresh: () => ref.read(lenderProvider.notifier).refresh(),
            readSnapshot: () => ref.read(lenderProvider).valueOrNull,
          ),
          PaPatternBackground(
        child: SafeArea(
          child: RefreshIndicator.adaptive(
            color: PaColors.teal,
            onRefresh: () => ref.read(lenderProvider.notifier).refresh(),
            child: state.when(
              data: (data) => _LenderBody(state: data),
              loading: () => const Center(
                child: CircularProgressIndicator(color: PaColors.teal),
              ),
              error: (e, _) => ListView(
                physics: const AlwaysScrollableScrollPhysics(),
                padding: const EdgeInsets.all(20),
                children: [
                  PaCard(
                    padding: const EdgeInsets.all(20),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Icon(Icons.error_outline,
                            color: PaColors.danger, size: 26,),
                        const SizedBox(height: 8),
                        const Text(
                          'Espace prêteur indisponible',
                          style: TextStyle(
                            color: PaColors.danger,
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                        const SizedBox(height: 4),
                        Text(
                          friendlyError(e),
                          style: const TextStyle(
                            color: PaColors.inkMuted,
                            fontSize: 12.5,
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
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

class _LenderBody extends ConsumerWidget {
  const _LenderBody({required this.state});
  final LenderState state;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return ListView(
      physics: const AlwaysScrollableScrollPhysics(),
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 40),
      children: [
        const Padding(
          padding: EdgeInsets.symmetric(horizontal: 4, vertical: 8),
          child: Row(
            children: [
              BackButton(color: PaColors.inkPrimary),
              SizedBox(width: 4),
              Text(
                'Espace prêteur',
                style: TextStyle(
                  color: PaColors.inkPrimary,
                  fontSize: 19,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: 4),
        if (!state.hasActiveConsent)
          _OptInCard(onTap: () => _doOptIn(context, ref)),
        if (state.hasActiveConsent) ...[
          _ConsentCard(consent: state.consent!),
          const SizedBox(height: 12),
          _TotalsCard(totals: state.totals),
          const SizedBox(height: 12),
          _TranchesSection(
            tranches: state.tranches,
            onAdd: () => _openAddTranche(context, ref),
          ),
          const SizedBox(height: 16),
          TextButton.icon(
            onPressed: () => _doRevoke(context, ref),
            icon: const Icon(Icons.logout_rounded,
                size: 18, color: PaColors.danger,),
            label: const Text(
              'Révoquer ma convention prêteur',
              style: TextStyle(color: PaColors.danger),
            ),
          ),
        ],
      ],
    );
  }

  Future<void> _doOptIn(BuildContext context, WidgetRef ref) async {
    try {
      await ref.read(lenderProvider.notifier).optIn(isGlobal: true);
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Convention prêteur signée.')),
        );
      }
    } catch (e) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Impossible de signer : ${friendlyError(e)}')),
        );
      }
    }
  }

  Future<void> _doRevoke(BuildContext context, WidgetRef ref) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('Révoquer la convention ?'),
        content: const Text(
          "Tu ne pourras plus prêter tant que tu n'auras pas signé une "
          'nouvelle convention. Les tranches engagées restent jusqu’au '
          'remboursement complet.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('Annuler'),
          ),
          FilledButton(
            style: FilledButton.styleFrom(backgroundColor: PaColors.danger),
            onPressed: () => Navigator.of(context).pop(true),
            child: const Text('Révoquer'),
          ),
        ],
      ),
    );
    if (ok != true) return;
    try {
      await ref.read(lenderProvider.notifier).revoke();
    } catch (e) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Échec : ${friendlyError(e)}')),
        );
      }
    }
  }

  Future<void> _openAddTranche(BuildContext context, WidgetRef ref) async {
    final ctrl = TextEditingController();
    final submitted = await showModalBottomSheet<num?>(
      context: context,
      isScrollControlled: true,
      backgroundColor: PaColors.paper,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      builder: (sheetContext) => Padding(
        padding: EdgeInsets.fromLTRB(
          20,
          16,
          20,
          MediaQuery.viewInsetsOf(sheetContext).bottom + 20,
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Nouvelle tranche prêtable',
              style: TextStyle(
                color: PaColors.inkPrimary,
                fontSize: 17,
                fontWeight: FontWeight.w700,
              ),
            ),
            const SizedBox(height: 8),
            const Text(
              'Cette tranche reste DISPONIBLE jusqu’à ce qu’un crédit la '
              'sollicite. Tu pourras l’annuler tant qu’elle n’est pas '
              'engagée.',
              style: TextStyle(color: PaColors.inkSecondary, fontSize: 12.5),
            ),
            const SizedBox(height: 14),
            TextField(
              controller: ctrl,
              keyboardType: TextInputType.number,
              decoration: const InputDecoration(
                labelText: 'Montant (XAF)',
                border: OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: 16),
            SizedBox(
              width: double.infinity,
              child: FilledButton(
                style: FilledButton.styleFrom(
                  backgroundColor: PaColors.teal,
                  foregroundColor: PaColors.onTeal,
                ),
                onPressed: () {
                  final n = num.tryParse(ctrl.text.trim());
                  Navigator.of(sheetContext).pop(n);
                },
                child: const Text('Créer la tranche'),
              ),
            ),
          ],
        ),
      ),
    );
    if (submitted == null || submitted <= 0) return;
    try {
      await ref.read(lenderProvider.notifier).addTranche(submitted);
    } catch (e) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Échec : ${friendlyError(e)}')),
        );
      }
    }
  }
}

// ── Sous-cartes ──────────────────────────────────────────────────────────

class _OptInCard extends StatelessWidget {
  const _OptInCard({required this.onTap});
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return PaCard(
      padding: const EdgeInsets.all(18),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Icon(Icons.volunteer_activism_rounded,
              color: PaColors.teal, size: 28,),
          const SizedBox(height: 10),
          const Text(
            'Devenir prêteur',
            style: TextStyle(
              color: PaColors.inkPrimary,
              fontSize: 16,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 6),
          const Text(
            'Une partie de ton épargne classique pourra financer les crédits '
            "d'autres membres. Tu reçois 50 % des intérêts générés, "
            'conformément au Règlement intérieur.',
            style: TextStyle(
              color: PaColors.inkSecondary,
              fontSize: 13,
              height: 1.4,
            ),
          ),
          const SizedBox(height: 14),
          SizedBox(
            width: double.infinity,
            child: FilledButton(
              onPressed: onTap,
              style: FilledButton.styleFrom(
                backgroundColor: PaColors.teal,
                foregroundColor: PaColors.onTeal,
              ),
              child: const Text('Signer la convention globale'),
            ),
          ),
        ],
      ),
    );
  }
}

class _ConsentCard extends StatelessWidget {
  const _ConsentCard({required this.consent});
  final LenderConsent consent;

  @override
  Widget build(BuildContext context) {
    return PaCard(
      padding: const EdgeInsets.all(16),
      child: Row(
        children: [
          Container(
            width: 40,
            height: 40,
            decoration: BoxDecoration(
              color: PaColors.successSurface,
              borderRadius: BorderRadius.circular(12),
            ),
            child: const Icon(Icons.verified_user_outlined,
                color: PaColors.success, size: 22,),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Convention active',
                  style: TextStyle(
                    color: PaColors.inkPrimary,
                    fontSize: 14.5,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  consent.isGlobal
                      ? 'Mode global · signée le ${AppDateFormatter.short(consent.signedAt)}'
                      : 'Mode tranches · signée le ${AppDateFormatter.short(consent.signedAt)}',
                  style: const TextStyle(
                    color: PaColors.inkMuted,
                    fontSize: 12,
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

class _TotalsCard extends StatelessWidget {
  const _TotalsCard({required this.totals});
  final LenderTotals totals;

  @override
  Widget build(BuildContext context) {
    return PaCard(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'Répartition par statut',
            style: TextStyle(
              color: PaColors.inkPrimary,
              fontSize: 14.5,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 12),
          _row('Disponible', totals.disponible, PaColors.success),
          _row('Engagée', totals.engagee, PaColors.warning),
          _row('Libérée', totals.liberee, PaColors.teal),
          _row('Annulée', totals.annulee, PaColors.inkMuted),
        ],
      ),
    );
  }

  Widget _row(String label, num amount, Color color) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        children: [
          Container(width: 6, height: 6, decoration: BoxDecoration(
            color: color,
            shape: BoxShape.circle,
          ),),
          const SizedBox(width: 10),
          Expanded(
            child: Text(label,
                style: const TextStyle(
                  color: PaColors.inkSecondary,
                  fontSize: 13.5,
                ),),
          ),
          Text(
            XAFFormatter.format(amount),
            style: const TextStyle(
              color: PaColors.inkPrimary,
              fontSize: 13.5,
              fontWeight: FontWeight.w700,
            ),
          ),
        ],
      ),
    );
  }
}

class _TranchesSection extends StatelessWidget {
  const _TranchesSection({required this.tranches, required this.onAdd});
  final List<LenderTranche> tranches;
  final VoidCallback onAdd;

  @override
  Widget build(BuildContext context) {
    return PaCard(
      padding: const EdgeInsets.fromLTRB(16, 14, 16, 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Expanded(
                child: Text(
                  'Mes tranches',
                  style: TextStyle(
                    color: PaColors.inkPrimary,
                    fontSize: 14.5,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ),
              TextButton.icon(
                onPressed: onAdd,
                icon: const Icon(Icons.add_rounded, size: 18),
                label: const Text('Ajouter'),
              ),
            ],
          ),
          if (tranches.isEmpty)
            const Padding(
              padding: EdgeInsets.symmetric(vertical: 10),
              child: Text(
                'Aucune tranche pour le moment.',
                style: TextStyle(color: PaColors.inkMuted, fontSize: 13),
              ),
            ),
          for (final t in tranches)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 6),
              child: Row(
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          XAFFormatter.format(t.montant),
                          style: const TextStyle(
                            color: PaColors.inkPrimary,
                            fontSize: 14,
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                        Text(
                          AppDateFormatter.short(t.createdAt),
                          style: const TextStyle(
                            color: PaColors.inkMuted,
                            fontSize: 11.5,
                          ),
                        ),
                      ],
                    ),
                  ),
                  _StatutChip(statut: t.statut),
                ],
              ),
            ),
        ],
      ),
    );
  }
}

class _StatutChip extends StatelessWidget {
  const _StatutChip({required this.statut});
  final LenderTrancheStatut statut;

  @override
  Widget build(BuildContext context) {
    final (label, bg, fg) = switch (statut) {
      LenderTrancheStatut.disponible => ('Disponible', PaColors.successSurface, PaColors.success),
      LenderTrancheStatut.engagee => ('Engagée', PaColors.warningSurface, PaColors.warning),
      LenderTrancheStatut.liberee => ('Libérée', PaColors.tealSurface, PaColors.teal),
      LenderTrancheStatut.annulee => ('Annulée', const Color(0xFFEAEDF1), PaColors.inkMuted),
    };
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(999),
      ),
      child: Text(
        label,
        style: TextStyle(
          color: fg,
          fontSize: 11,
          fontWeight: FontWeight.w700,
        ),
      ),
    );
  }
}
