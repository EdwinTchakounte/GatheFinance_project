import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

import '../../../../app/theme/app_typography.dart';
import '../../../../app/theme/paysika/pa_colors.dart';
import '../../../../core/error/error_message.dart';
import '../../../../core/formatters/xaf_formatter.dart';
import '../../../../core/services/payment_rates_provider.dart';
import '../../../../core/widgets/paysika/pa_card.dart';
import '../../../../core/widgets/paysika/pa_error_state.dart';
import '../../../../core/widgets/paysika/pa_shimmer.dart';
import '../../../auth/domain/entities/member.dart';
import '../../../auth/presentation/state/auth_notifier.dart';
import '../../data/recu_pdf_service.dart';
import '../../domain/payment_receipt.dart';
import '../state/receipts_provider.dart';
import 'recu_preview_page.dart';

/// Page « Mes reçus de versement » — liste tous les versements du membre, chaque
/// ligne pouvant générer une mini-facture GATHE (PDF) téléchargeable/partageable.
class ReceiptsPage extends ConsumerWidget {
  const ReceiptsPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(receiptsProvider);
    return Scaffold(
      backgroundColor: PaColors.appBg,
      appBar: AppBar(
        title: const Text('Mes reçus'),
        backgroundColor: PaColors.appBg,
        elevation: 0,
        scrolledUnderElevation: 0,
      ),
      body: async.when(
        loading: () => const Padding(
          padding: EdgeInsets.fromLTRB(16, 16, 16, 24),
          child: PaCard(
            padding: EdgeInsets.all(16),
            child: PaShimmerList(count: 5),
          ),
        ),
        error: (err, _) => PaErrorState(
          message: friendlyError(err),
          onRetry: () => ref.invalidate(receiptsProvider),
        ),
        data: (items) => items.isEmpty
            ? const _EmptyView()
            : RefreshIndicator(
                onRefresh: () async => ref.invalidate(receiptsProvider),
                child: ListView.separated(
                  padding: const EdgeInsets.fromLTRB(16, 12, 16, 24),
                  itemCount: items.length + 1,
                  separatorBuilder: (_, __) => const SizedBox(height: 10),
                  itemBuilder: (context, index) {
                    if (index == 0) return const _IntroNote();
                    return _ReceiptTile(receipt: items[index - 1]);
                  },
                ),
              ),
      ),
    );
  }
}

class _IntroNote extends StatelessWidget {
  const _IntroNote();

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 4, top: 2),
      child: Text(
        'Télécharge le reçu de chaque versement effectué.',
        style: AppTypography.bodySmall.copyWith(
          color: PaColors.inkSecondary,
          fontSize: 12,
        ),
      ),
    );
  }
}

class _ReceiptTile extends ConsumerWidget {
  const _ReceiptTile({required this.receipt});
  final PaymentReceipt receipt;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final signed = _isCredit(receipt.type);
    return PaCard(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      child: Row(
        children: [
          Container(
            width: 38,
            height: 38,
            decoration: BoxDecoration(
              color: PaColors.teal.withValues(alpha: 0.10),
              borderRadius: BorderRadius.circular(10),
            ),
            child: const Icon(
              Icons.receipt_long_rounded,
              color: PaColors.teal,
              size: 20,
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  receipt.typeDisplay.isEmpty
                      ? 'Versement'
                      : receipt.typeDisplay,
                  style: const TextStyle(
                    color: PaColors.inkPrimary,
                    fontSize: 14,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                const SizedBox(height: 2),
                Row(
                  children: [
                    Text(
                      _shortDate(receipt.date),
                      style: const TextStyle(
                        color: PaColors.inkMuted,
                        fontSize: 11,
                      ),
                    ),
                    const SizedBox(width: 8),
                    _StatusDot(statut: receipt.statut),
                  ],
                ),
              ],
            ),
          ),
          const SizedBox(width: 8),
          Column(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Text(
                '${signed ? '- ' : ''}${XAFFormatter.format(receipt.montant)}',
                style: const TextStyle(
                  color: PaColors.inkPrimary,
                  fontSize: 14,
                  fontWeight: FontWeight.w700,
                ),
              ),
              const SizedBox(height: 4),
              InkWell(
                borderRadius: BorderRadius.circular(8),
                onTap: () => _openReceipt(context, ref),
                child: const Padding(
                  padding: EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(
                        Icons.download_rounded,
                        size: 15,
                        color: PaColors.teal,
                      ),
                      SizedBox(width: 4),
                      Text(
                        'Reçu',
                        style: TextStyle(
                          color: PaColors.teal,
                          fontSize: 12,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Future<void> _openReceipt(BuildContext context, WidgetRef ref) async {
    final member = ref.read(authProvider).valueOrNull;
    final rates = ref.read(paymentRatesProvider).valueOrNull ?? const {};
    final data = _buildRecuData(receipt, member, rates);
    if (!context.mounted) return;
    await Navigator.of(context).push(
      MaterialPageRoute<void>(builder: (_) => RecuPreviewPage(data: data)),
    );
  }
}

class _StatusDot extends StatelessWidget {
  const _StatusDot({required this.statut});
  final String statut;

  @override
  Widget build(BuildContext context) {
    final (color, label) = switch (statut) {
      'valide' => (PaColors.success, 'Validé'),
      'rejete' || 'annule' => (PaColors.danger, 'Échec'),
      _ => (PaColors.warning, 'En attente'),
    };
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          width: 6,
          height: 6,
          decoration: BoxDecoration(color: color, shape: BoxShape.circle),
        ),
        const SizedBox(width: 4),
        Text(
          label,
          style: TextStyle(
            color: color,
            fontSize: 11,
            fontWeight: FontWeight.w600,
          ),
        ),
      ],
    );
  }
}

class _EmptyView extends StatelessWidget {
  const _EmptyView();

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(28),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const SizedBox(height: 40),
          Container(
            width: 64,
            height: 64,
            decoration: BoxDecoration(
              color: PaColors.teal.withValues(alpha: 0.08),
              shape: BoxShape.circle,
            ),
            child: const Icon(
              Icons.receipt_long_rounded,
              size: 30,
              color: PaColors.teal,
            ),
          ),
          const SizedBox(height: 16),
          const Text(
            'Aucun versement pour l\'instant',
            style: TextStyle(
              color: PaColors.inkPrimary,
              fontSize: 16,
              fontWeight: FontWeight.w700,
            ),
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 8),
          const Text(
            'Dès que tu effectues un versement, tu pourras télécharger ici son '
            'reçu au format PDF.',
            textAlign: TextAlign.center,
            style: TextStyle(
              color: PaColors.inkSecondary,
              fontSize: 13,
              height: 1.45,
            ),
          ),
        ],
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────
// Mapping reçu → RecuData (variables importantes selon le type d'action)
// ─────────────────────────────────────────────────────────────────────────

bool _isCredit(String type) => type == 'remboursement';

String _shortDate(DateTime d) {
  const mois = [
    'janv',
    'févr',
    'mars',
    'avril',
    'mai',
    'juin',
    'juil',
    'août',
    'sept',
    'oct',
    'nov',
    'déc',
  ];
  return '${d.day} ${mois[d.month - 1]} ${d.year}';
}

RecuData _buildRecuData(
  PaymentReceipt r,
  Member? member,
  Map<String, double> rates,
) {
  final dfLong = DateFormat('dd/MM/yyyy à HH:mm', 'fr_FR');
  final statusLabel = switch (r.statut) {
    'valide' => 'Validé',
    'rejete' => 'Rejeté',
    'annule' => 'Annulé',
    _ => 'En attente',
  };

  final lines = <RecuLine>[
    RecuLine('Montant versé', XAFFormatter.format(r.montant)),
  ];
  if (r.fraisTransaction > 0) {
    lines.add(
      RecuLine(
        'Frais de transaction',
        XAFFormatter.format(r.fraisTransaction),
      ),
    );
    lines.add(
      RecuLine(
        'Total débité',
        XAFFormatter.format(r.totalDebite),
        emphasize: true,
      ),
    );
  }

  // Taux « importants » selon l'action.
  final taux = _rateLineFor(r.type, rates);
  if (taux != null) lines.add(taux);

  // Spécifiques.
  if (r.type == 'epargne' && r.nbJoursCouverts > 1) {
    lines.add(RecuLine('Jours de collecte couverts', '${r.nbJoursCouverts}'));
  }
  if (r.type == 'epargne_classique') {
    lines.add(RecuLine('Sous-canal', r.isPlacement ? 'Placement' : 'Libre'));
  }

  lines.add(RecuLine('Date du versement', dfLong.format(r.date)));
  if (r.dateValidation != null) {
    lines.add(RecuLine('Date de validation', dfLong.format(r.dateValidation!)));
  }
  if ((r.reference ?? '').isNotEmpty) {
    lines.add(RecuLine('Référence', r.reference!));
  }

  final memberName = member?.fullName ?? 'Membre GATHE';
  final memberNumber = member?.numeroMembre ?? '—';

  return RecuData(
    title: 'Reçu de versement',
    receiptRef: 'Reçu N° ${r.id.toString().padLeft(6, '0')}',
    issuedOn:
        'Émis le ${DateFormat('dd/MM/yyyy', 'fr_FR').format(DateTime.now())}',
    memberName: memberName,
    memberNumber: memberNumber,
    operationLabel: r.typeDisplay.isEmpty ? 'Versement' : r.typeDisplay,
    amountValue: XAFFormatter.format(r.montant),
    statusLabel: statusLabel,
    lines: lines,
    footer: 'Document généré par l\'application GATHE Finance. Ce reçu atteste '
        'du versement ci-dessus enregistré au nom du membre. Conservez-le.',
    fileName: 'recu_gathe_${r.id}',
  );
}

/// Ligne « taux » pertinente selon le type de versement (ratios → %).
RecuLine? _rateLineFor(String type, Map<String, double> rates) {
  String? pct(String code) {
    final v = rates[code];
    if (v == null || v <= 0) return null;
    final p = v * 100;
    final s =
        p == p.roundToDouble() ? p.toStringAsFixed(0) : p.toStringAsFixed(2);
    return '$s %';
  }

  switch (type) {
    case 'remboursement':
      final v = pct('LOAN_INTEREST');
      return v == null ? null : RecuLine('Taux d\'intérêt du crédit', v);
    case 'epargne_classique':
    case 'epargne':
      final v = pct('SAVINGS_INTEREST_MONTHLY');
      return v == null
          ? null
          : RecuLine('Taux d\'intérêt épargne (mensuel)', v);
    default:
      return null;
  }
}
