import 'package:flutter/material.dart';

import '../../../../app/theme/paysika/pa_colors.dart';
import '../../../../app/theme/paysika/pa_typography.dart';
import '../../../../core/formatters/date_formatter.dart' as date_fmt;
import '../../../../core/formatters/xaf_formatter.dart' as xaf_fmt;
import '../../../../core/widgets/paysika/pa_button.dart';
import '../../../../core/widgets/paysika/pa_card.dart';
import '../../../../core/widgets/paysika/pa_status_chip.dart';
import '../../domain/entities/avaliste_mandat.dart';

/// Carte d'affichage d'un mandat d'avaliste — présente le demandeur,
/// le montant + durée du crédit demandé, l'analyse de couverture (épargne
/// avaliste vs montant), et 2 boutons d'action si le mandat est pending.
class MandatCard extends StatelessWidget {
  const MandatCard({
    super.key,
    required this.mandat,
    required this.onAccept,
    required this.onRefuse,
    this.busy = false,
  });

  final AvalisteMandat mandat;
  final VoidCallback onAccept;
  final VoidCallback onRefuse;
  final bool busy;

  @override
  Widget build(BuildContext context) {
    final lr = mandat.loanRequest;
    final couvOk = mandat.couverture.ratio >= 1;
    return PaCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // ── En-tête : demandeur + statut ───────────────────────────────
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                width: 40,
                height: 40,
                decoration: BoxDecoration(
                  gradient: LinearGradient(
                    colors: const [PaColors.teal, PaColors.tealDark],
                    begin: Alignment.topLeft,
                    end: Alignment.bottomRight,
                  ),
                  borderRadius: BorderRadius.circular(20),
                ),
                child: Center(
                  child: Text(
                    _initials(mandat.demandeur.fullName),
                    style: PaText.heading(size: 14)
                        .copyWith(color: PaColors.onTeal),
                  ),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      mandat.demandeur.fullName,
                      style: PaText.heading(size: 16),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      '${mandat.demandeur.numeroMembre} · '
                      '${date_fmt.AppDateFormatter.short(mandat.createdAt)}',
                      style: PaText.body().copyWith(
                        color: PaColors.inkSecondary,
                        fontSize: 12,
                      ),
                    ),
                  ],
                ),
              ),
              PaStatusChip(
                label: mandat.statutDisplay,
                color: _colorFor(mandat.statut),
              ),
            ],
          ),
          const SizedBox(height: 16),
          // ── Demande de crédit ──────────────────────────────────────────
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: PaColors.canvas,
              borderRadius: BorderRadius.circular(12),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Expanded(
                      child: _Stat(
                        label: 'Montant demandé',
                        value: xaf_fmt.XAFFormatter.format(lr.montantDemande),
                        emphasize: true,
                      ),
                    ),
                    _Stat(
                      label: 'Durée',
                      value: '${lr.dureeMois} mois',
                    ),
                  ],
                ),
                if (lr.motif.isNotEmpty) ...[
                  const SizedBox(height: 8),
                  Text(
                    'Motif : ${lr.motif}',
                    style: PaText.body().copyWith(fontSize: 13),
                  ),
                ],
              ],
            ),
          ),
          const SizedBox(height: 12),
          // ── Couverture épargne ────────────────────────────────────────
          Row(
            children: [
              Icon(
                couvOk ? Icons.shield_outlined : Icons.warning_amber_rounded,
                size: 16,
                color: couvOk ? PaColors.teal : Colors.orange.shade700,
              ),
              const SizedBox(width: 6),
              Expanded(
                child: Text(
                  'Ton épargne : '
                  '${xaf_fmt.XAFFormatter.format(mandat.couverture.epargneAvaliste)} '
                  '(ratio ${mandat.couverture.ratio.toStringAsFixed(2)})',
                  style: PaText.body().copyWith(
                    fontSize: 12,
                    color: couvOk
                        ? PaColors.inkSecondary
                        : Colors.orange.shade900,
                  ),
                ),
              ),
            ],
          ),
          // ── Actions (uniquement si pending) ────────────────────────────
          if (mandat.isPending) ...[
            const SizedBox(height: 16),
            Row(
              children: [
                Expanded(
                  child: PaButton(
                    label: 'Refuser',
                    variant: PaButtonVariant.outline,
                    onPressed: busy ? null : onRefuse,
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: PaButton(
                    label: 'Accepter',
                    loading: busy,
                    onPressed: busy ? null : onAccept,
                  ),
                ),
              ],
            ),
          ] else if (mandat.isRefused && mandat.refusMotif.isNotEmpty) ...[
            const SizedBox(height: 12),
            Container(
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: Colors.red.shade50,
                borderRadius: BorderRadius.circular(8),
              ),
              child: Text(
                'Ton motif : ${mandat.refusMotif}',
                style: PaText.body().copyWith(
                  fontSize: 12,
                  color: Colors.red.shade900,
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }
}

class _Stat extends StatelessWidget {
  const _Stat({
    required this.label,
    required this.value,
    this.emphasize = false,
  });
  final String label;
  final String value;
  final bool emphasize;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          label.toUpperCase(),
          style: PaText.eyebrow().copyWith(fontSize: 10),
        ),
        const SizedBox(height: 2),
        Text(
          value,
          style: emphasize
              ? PaText.heading(size: 18)
              : PaText.heading(size: 14),
        ),
      ],
    );
  }
}

String _initials(String name) {
  final parts = name.trim().split(RegExp(r'\s+'));
  if (parts.isEmpty) return '?';
  if (parts.length == 1) return parts.first.substring(0, 1).toUpperCase();
  return (parts.first[0] + parts.last[0]).toUpperCase();
}

Color _colorFor(AvalisteStatut s) {
  switch (s) {
    case AvalisteStatut.accepted:
      return PaColors.teal;
    case AvalisteStatut.refused:
      return Colors.red.shade700;
    case AvalisteStatut.pending:
      return Colors.orange.shade700;
  }
}
