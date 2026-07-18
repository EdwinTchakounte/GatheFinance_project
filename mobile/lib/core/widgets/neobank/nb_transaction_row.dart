import 'package:flutter/material.dart';

import '../../../app/theme/app_typography.dart';
import '../../formatters/xaf_formatter.dart';

/// Catégorie de transaction → icône + couleur soft du badge.
enum NbTxKind {
  /// Dépôt épargne (in) . vert
  depot,
  /// Intérêts crédités (in) . vert
  interet,
  /// Frais carnet, frais adhésion, frais reconduction (out) . orange
  frais,
  /// Remboursement crédit (out) . bleu
  remboursement,
  /// Décaissement crédit reçu (in) . bleu
  decaissement,
  /// Retrait (out) . rouge soft
  retrait,
  /// Catch-all
  autre,
}

/// Row de transaction . style néobanque (Paysika / Wave / Revolut).
///
///   ┌────────────────────────────────────────┐
///   │ ⚪40   Libellé bold 15pt        + 2 500│
///   │       Auj. 14h22                        │
///   └────────────────────────────────────────┘
///
/// Pas de Card, pas d'ombre. Le badge rond (40 × 40) catégorise par couleur.
/// Le montant est aligné à droite, coloré selon le signe.
///
/// La ligne est cliquable (détail) via [onTap].
class NbTransactionRow extends StatelessWidget {
  const NbTransactionRow({
    super.key,
    required this.kind,
    required this.label,
    required this.date,
    required this.amount,
    this.signedAmount = true,
    this.onTap,
  });

  final NbTxKind kind;
  final String label;
  final String date;

  /// Montant absolu. Le signe est dérivé de [kind] sauf si [signedAmount]
  /// est faux (utile pour afficher des montants neutres).
  final num amount;

  /// Si true (défaut), affiche ` + ` ou ` - ` selon la catégorie d'opération.
  final bool signedAmount;

  final VoidCallback? onTap;

  bool get _isIncoming => switch (kind) {
        NbTxKind.depot ||
        NbTxKind.interet ||
        NbTxKind.decaissement =>
          true,
        _ => false,
      };

  IconData get _icon => switch (kind) {
        NbTxKind.depot => Icons.south_west_rounded,
        NbTxKind.interet => Icons.trending_up_rounded,
        NbTxKind.frais => Icons.receipt_long_rounded,
        NbTxKind.remboursement => Icons.replay_rounded,
        NbTxKind.decaissement => Icons.account_balance_wallet_rounded,
        NbTxKind.retrait => Icons.north_east_rounded,
        NbTxKind.autre => Icons.swap_horiz_rounded,
      };

  Color _badgeColor(ColorScheme scheme) => switch (kind) {
        NbTxKind.depot => const Color(0xFF1B9B6E),       // emerald
        NbTxKind.interet => const Color(0xFF1B9B6E),     // emerald
        NbTxKind.frais => const Color(0xFFD97706),       // amber
        NbTxKind.remboursement => scheme.primary,         // cobalt
        NbTxKind.decaissement => scheme.primary,          // cobalt
        NbTxKind.retrait => const Color(0xFFC6463A),     // soft red
        NbTxKind.autre => scheme.onSurface.withValues(alpha: 0.55),
      };

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final muted = scheme.onSurface.withValues(alpha: 0.55);
    final badge = _badgeColor(scheme);

    final amountStr = XAFFormatter.format(amount);
    final amountText = signedAmount
        ? '${_isIncoming ? '+' : '−'} $amountStr'
        : amountStr;
    final amountColor = signedAmount
        ? (_isIncoming
            ? const Color(0xFF1B9B6E)
            : scheme.onSurface)
        : scheme.onSurface;

    return InkWell(
      onTap: onTap,
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 12, horizontal: 4),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.center,
          children: [
            Container(
              width: 40,
              height: 40,
              decoration: BoxDecoration(
                color: badge.withValues(alpha: 0.12),
                shape: BoxShape.circle,
              ),
              alignment: Alignment.center,
              child: Icon(_icon, color: badge, size: 20),
            ),
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    label,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: AppTypography.bodyLarge.copyWith(
                      fontSize: 14,
                      fontWeight: FontWeight.w700,
                      color: scheme.onSurface,
                    ),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    date,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: AppTypography.bodySmall.copyWith(
                      fontSize: 12,
                      color: muted,
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(width: 10),
            Text(
              amountText,
              style: AppTypography.bodyLarge.copyWith(
                fontSize: 16,
                fontWeight: FontWeight.w700,
                color: amountColor,
                fontFeatures: const [FontFeature.tabularFigures()],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
