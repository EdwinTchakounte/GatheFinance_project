import 'package:flutter/material.dart';

import '../../app/theme/app_colors.dart';
import '../../app/theme/app_radii.dart';
import '../../app/theme/app_typography.dart';
import '../../features/savings/domain/entities/savings_transaction.dart';
import '../../l10n/gen/app_localizations.dart';
import '../formatters/date_formatter.dart';
import '../formatters/xaf_formatter.dart';

/// Ligne d'opération d'épargne : icône colorée à gauche, libellé + date,
/// montant à droite (signé). Réutilisable dans la home et la page historique.
class TransactionTile extends StatelessWidget {
  const TransactionTile({super.key, required this.tx});

  final SavingsTransaction tx;

  @override
  Widget build(BuildContext context) {
    final l = AppL10n.of(context);
    final scheme = Theme.of(context).colorScheme;
    final muted = scheme.onSurface.withValues(alpha: 0.5);

    final ({IconData icon, Color tint, String label, bool positive}) v;
    switch (tx.type) {
      case SavingsType.depot:
        v = (
          icon: Icons.arrow_downward_rounded,
          tint: AppColors.emerald,
          label: l.tx_deposit,
          positive: true,
        );
        break;
      case SavingsType.retrait:
        v = (
          icon: Icons.arrow_upward_rounded,
          tint: AppColors.terraDark,
          label: l.tx_withdrawal,
          positive: false,
        );
        break;
      case SavingsType.interet:
        v = (
          icon: Icons.auto_awesome_rounded,
          tint: AppColors.cobalt,
          label: l.tx_interest,
          positive: true,
        );
        break;
    }

    // Le SIGNE vient de isOutflow (retrait OU frais/débit) — pas seulement du
    // type : un frais (frais_demande_credit, interets_reconduction…) fait
    // SORTIR de l'argent et doit s'afficher en négatif.
    final positive = !tx.isOutflow;
    // Libellé précis fourni par le backend quand dispo (ex. « Frais d'étude »).
    final label = tx.typeDisplay.isNotEmpty ? tx.typeDisplay : v.label;
    // Icône/teinte cohérentes avec le sens (un frais n'est pas un dépôt).
    final icon = tx.isOutflow ? Icons.arrow_upward_rounded : v.icon;
    final tint = tx.isOutflow ? AppColors.terraDark : v.tint;

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 12),
      child: Row(
        children: [
          Container(
            width: 40,
            height: 40,
            decoration: BoxDecoration(
              color: v.tint.withValues(alpha: 0.12),
              borderRadius: const BorderRadius.all(AppRadii.r12),
            ),
            child: Icon(icon, color: tint, size: 20),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  label,
                  style: AppTypography.labelLarge
                      .copyWith(color: scheme.onSurface),
                ),
                const SizedBox(height: 2),
                Text(
                  AppDateFormatter.withTime(tx.date),
                  style:
                      AppTypography.bodySmall.copyWith(color: muted),
                ),
              ],
            ),
          ),
          Column(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Text(
                '${positive ? '+' : '−'} ${XAFFormatter.formatNumber(tx.montant)}',
                style: AppTypography.labelLarge.copyWith(
                  color: positive ? AppColors.emeraldDark : AppColors.terraDark,
                  fontFeatures: const [FontFeature.tabularFigures()],
                ),
              ),
              const SizedBox(height: 2),
              Text(
                l.tx_balance_after(XAFFormatter.formatNumber(tx.soldeApres)),
                style: AppTypography.bodySmall.copyWith(color: muted),
              ),
            ],
          ),
        ],
      ),
    );
  }
}
