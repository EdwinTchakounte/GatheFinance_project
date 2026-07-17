import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../app/theme/paysika/pa_colors.dart';
import '../../../../core/di/providers.dart';
import '../../../../core/error/error_message.dart';
import '../../../../core/formatters/xaf_formatter.dart';
import '../../../../core/widgets/paysika/pa_button.dart';
import '../../../../core/widgets/paysika/pa_card.dart';
import '../../../../l10n/gen/app_localizations.dart';
import '../../domain/entities/loan.dart';
import '../state/loans_notifier.dart';

/// Sheet **Transfert** — rembourser un crédit en cours depuis l'argent
/// disponible (épargne classique retirable + collecte), sans Mobile Money.
class TransferSheet extends ConsumerStatefulWidget {
  const TransferSheet({super.key});

  static Future<void> show(BuildContext context) => showModalBottomSheet<void>(
        context: context,
        isScrollControlled: true,
        backgroundColor: PaColors.canvas,
        shape: const RoundedRectangleBorder(
          borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
        ),
        builder: (_) => const TransferSheet(),
      );

  @override
  ConsumerState<TransferSheet> createState() => _TransferSheetState();
}

class _TransferSheetState extends ConsumerState<TransferSheet> {
  final _amountCtrl = TextEditingController();
  num _available = 0;
  bool _loadingAvail = true;
  bool _submitting = false;
  Loan? _selected;

  @override
  void initState() {
    super.initState();
    _loadAvailable();
  }

  @override
  void dispose() {
    _amountCtrl.dispose();
    super.dispose();
  }

  Future<void> _loadAvailable() async {
    try {
      final dio = ref.read(apiClientProvider).dio;
      final res = await dio.get<Map<String, dynamic>>(
        '/loans/transfer/available/',
      );
      _available = num.tryParse('${res.data?['total'] ?? 0}') ?? 0;
    } catch (_) {
      _available = 0;
    } finally {
      if (mounted) setState(() => _loadingAvail = false);
    }
  }

  Future<void> _submit() async {
    final loan = _selected;
    final amount = num.tryParse(_amountCtrl.text.replaceAll(' ', '')) ?? 0;
    final l = AppL10n.of(context);
    if (loan == null || amount <= 0) return;
    if (amount > _available) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(l.transfer_insufficient)),
      );
      return;
    }
    setState(() => _submitting = true);
    try {
      final dio = ref.read(apiClientProvider).dio;
      await dio.post<Map<String, dynamic>>(
        '/loans/me/loans/${loan.id}/repay-from-savings/',
        data: {'montant': amount},
      );
      unawaited(HapticFeedback.mediumImpact());
      await ref.read(loansProvider.notifier).refresh();
      if (!mounted) return;
      Navigator.of(context).pop();
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(l.transfer_success)),
      );
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(friendlyError(e))),
        );
      }
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final l = AppL10n.of(context);
    final loansAsync = ref.watch(loansProvider);
    final loans = loansAsync.valueOrNull ?? const <Loan>[];
    // Auto-sélection s'il n'y a qu'un crédit.
    if (_selected == null && loans.length == 1) _selected = loans.first;

    return Padding(
      padding: EdgeInsets.only(
        bottom: MediaQuery.viewInsetsOf(context).bottom,
      ),
      child: SafeArea(
        top: false,
        child: SingleChildScrollView(
          padding: const EdgeInsets.fromLTRB(20, 12, 20, 24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Center(
                child: Container(
                  width: 40,
                  height: 4,
                  decoration: BoxDecoration(
                    color: PaColors.line,
                    borderRadius: BorderRadius.circular(2),
                  ),
                ),
              ),
              const SizedBox(height: 18),
              Text(
                l.transfer_title,
                style: const TextStyle(
                  color: PaColors.inkPrimary,
                  fontSize: 19,
                  fontWeight: FontWeight.w700,
                ),
              ),
              const SizedBox(height: 4),
              Text(
                l.transfer_sub,
                style: const TextStyle(color: PaColors.inkMuted, fontSize: 13),
              ),
              const SizedBox(height: 16),

              // Disponible
              PaCard(
                padding: const EdgeInsets.all(14),
                child: Row(
                  children: [
                    const Icon(Icons.account_balance_wallet_outlined,
                        size: 20, color: PaColors.teal,),
                    const SizedBox(width: 10),
                    Text(
                      l.transfer_available_label,
                      style: const TextStyle(
                          color: PaColors.inkMuted, fontSize: 13,),
                    ),
                    const Spacer(),
                    Text(
                      _loadingAvail
                          ? '…'
                          : '${XAFFormatter.format(_available)} XAF',
                      style: const TextStyle(
                        color: PaColors.inkPrimary,
                        fontSize: 15,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 16),

              if (loans.isEmpty) ...[
                const SizedBox(height: 8),
                Center(
                  child: Text(
                    l.transfer_no_loan,
                    style: const TextStyle(
                        color: PaColors.inkMuted, fontSize: 13.5,),
                  ),
                ),
                const SizedBox(height: 8),
              ] else ...[
                // Sélecteur de crédit (si plusieurs)
                if (loans.length > 1) ...[
                  Text(
                    l.transfer_pick_loan,
                    style: const TextStyle(
                      color: PaColors.inkSecondary,
                      fontSize: 12,
                      fontWeight: FontWeight.w700,
                      letterSpacing: 1.2,
                    ),
                  ),
                  const SizedBox(height: 8),
                  for (final loan in loans)
                    _LoanRow(
                      loan: loan,
                      selected: _selected?.id == loan.id,
                      onTap: () => setState(() => _selected = loan),
                    ),
                  const SizedBox(height: 8),
                ] else ...[
                  _LoanRow(loan: loans.first, selected: true, onTap: () {}),
                  const SizedBox(height: 8),
                ],

                Text(
                  l.transfer_amount,
                  style: const TextStyle(
                    color: PaColors.inkSecondary,
                    fontSize: 12,
                    fontWeight: FontWeight.w700,
                    letterSpacing: 1.2,
                  ),
                ),
                const SizedBox(height: 6),
                TextField(
                  controller: _amountCtrl,
                  keyboardType: TextInputType.number,
                  inputFormatters: [FilteringTextInputFormatter.digitsOnly],
                  cursorColor: PaColors.teal,
                  style: const TextStyle(
                    color: PaColors.inkPrimary,
                    fontSize: 30,
                    fontWeight: FontWeight.w700,
                  ),
                  decoration: const InputDecoration(
                    hintText: '0',
                    suffix: Text(' XAF',
                        style: TextStyle(
                            color: PaColors.inkMuted,
                            fontSize: 13,
                            fontWeight: FontWeight.w700,),),
                    enabledBorder: UnderlineInputBorder(
                      borderSide: BorderSide(color: PaColors.line),
                    ),
                    focusedBorder: UnderlineInputBorder(
                      borderSide: BorderSide(color: PaColors.teal, width: 2),
                    ),
                  ),
                ),
                const SizedBox(height: 24),
                PaButton(
                  label: _submitting ? '…' : l.transfer_cta,
                  onPressed: _submitting ? null : _submit,
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

class _LoanRow extends StatelessWidget {
  const _LoanRow({
    required this.loan,
    required this.selected,
    required this.onTap,
  });
  final Loan loan;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final l = AppL10n.of(context);
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(14),
        child: Container(
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(
            color: selected ? PaColors.tealSurface : PaColors.paper,
            borderRadius: BorderRadius.circular(14),
            border: Border.all(
              color: selected ? PaColors.teal : PaColors.line,
              width: selected ? 1.5 : 1,
            ),
          ),
          child: Row(
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      loan.numeroDossier,
                      style: const TextStyle(
                        color: PaColors.inkPrimary,
                        fontSize: 13.5,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      '${l.transfer_remaining}: '
                      '${XAFFormatter.format(loan.soldeRestant)} XAF',
                      style: const TextStyle(
                          color: PaColors.inkMuted, fontSize: 12,),
                    ),
                  ],
                ),
              ),
              if (selected)
                const Icon(Icons.check_circle_rounded,
                    size: 20, color: PaColors.teal,),
            ],
          ),
        ),
      ),
    );
  }
}
