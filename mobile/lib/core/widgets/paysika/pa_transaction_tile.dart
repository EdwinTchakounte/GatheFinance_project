import 'package:flutter/material.dart';

import '../../../app/theme/paysika/pa_colors.dart';
import '../../formatters/xaf_formatter.dart';

/// Catégorie de transaction → couleur d'avatar + icône.
enum PaTxKind {
  /// Dépôt épargne (in) . vert succès
  depot,
  /// Intérêts crédités (in) . vert succès
  interet,
  /// Frais carnet, frais adhésion, frais reconduction (out) . orange chaud
  frais,
  /// Remboursement crédit (out) . teal (lié au crédit)
  remboursement,
  /// Décaissement crédit reçu (in) . teal
  decaissement,
  /// Retrait (out) . rouge soft
  retrait,
  /// Catch-all
  autre,
}

/// Row de transaction Paysika . **avatar coloré rond** + libellé + montant.
///
/// Style observé dans capture_paysika/ (transactions list) :
///   - Avatar rond 40 px, fond pastel pâle de la couleur catégorielle,
///     icône au centre dans la couleur sat
///   - Libellé bold 15pt navy
///   - Sous-ligne heure 12pt gris
///   - Montant à droite, taille 16pt, couleur (success vert / danger rouge /
///     navy sinon)
///
/// La row n'est PAS dans une card individuelle . elle vit dans une PaCard
/// parent qui regroupe N rows séparées par un Divider très fin.
class PaTransactionTile extends StatelessWidget {
  const PaTransactionTile({
    super.key,
    required this.kind,
    required this.label,
    required this.time,
    required this.amount,
    this.signedAmount = true,
    this.onTap,
  });

  final PaTxKind kind;
  final String label;
  final String time;
  final num amount;
  final bool signedAmount;
  final VoidCallback? onTap;

  bool get _isIncoming => switch (kind) {
        PaTxKind.depot || PaTxKind.interet || PaTxKind.decaissement => true,
        _ => false,
      };

  IconData get _icon => switch (kind) {
        PaTxKind.depot => Icons.south_west_rounded,
        PaTxKind.interet => Icons.trending_up_rounded,
        PaTxKind.frais => Icons.receipt_long_rounded,
        PaTxKind.remboursement => Icons.replay_rounded,
        PaTxKind.decaissement => Icons.account_balance_wallet_rounded,
        PaTxKind.retrait => Icons.north_east_rounded,
        PaTxKind.autre => Icons.swap_horiz_rounded,
      };

  Color get _color => switch (kind) {
        PaTxKind.depot || PaTxKind.interet => PaColors.success,
        PaTxKind.frais => PaColors.warning,
        PaTxKind.remboursement || PaTxKind.decaissement => PaColors.teal,
        PaTxKind.retrait => PaColors.danger,
        PaTxKind.autre => PaColors.catNeutral,
      };

  @override
  Widget build(BuildContext context) {
    final amountStr = XAFFormatter.format(amount);
    final amountText =
        signedAmount ? '${_isIncoming ? '+ ' : '− '}$amountStr' : amountStr;
    final amountColor = signedAmount
        ? (_isIncoming ? PaColors.success : PaColors.danger)
        : PaColors.inkPrimary;

    return InkWell(
      onTap: onTap,
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 12, horizontal: 4),
        child: Row(
          children: [
            // Avatar rond coloré 40 px
            Container(
              width: 40,
              height: 40,
              decoration: BoxDecoration(
                color: _color.withValues(alpha: 0.14),
                shape: BoxShape.circle,
              ),
              alignment: Alignment.center,
              child: Icon(_icon, color: _color, size: 20),
            ),
            const SizedBox(width: 14),

            // Libellé + heure
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    label,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    // Tonalité réduite : le libellé d'opération est un rappel
                    // secondaire, le montant reste le point focal.
                    style: const TextStyle(
                      color: PaColors.inkSecondary,
                      fontSize: 14.5,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    time,
                    style: const TextStyle(
                      color: PaColors.inkMuted,
                      fontSize: 12.5,
                      fontWeight: FontWeight.w500,
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(width: 10),

            // Montant aligné droite
            Text(
              amountText,
              style: TextStyle(
                color: amountColor,
                fontSize: 15.5,
                fontWeight: FontWeight.w700,
                fontFeatures: const [FontFeature.tabularFigures()],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
