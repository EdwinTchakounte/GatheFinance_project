import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../app/theme/paysika/pa_colors.dart';
import '../../../../core/error/error_message.dart';
import '../../../../core/formatters/xaf_formatter.dart';
import '../../../../core/services/tara_checkout_launcher.dart';
import '../../../../core/widgets/paysika/pa_button.dart';
import '../../../../core/widgets/paysika/pa_card.dart';
import '../../../../l10n/gen/app_localizations.dart';
import '../state/membership_fees_notifier.dart';

/// Sheet de paiement d'un frais membre (adhésion / inscription).
/// Deux canaux : depuis le compte (si solvable) OU Mobile Money.
class MembershipFeeSheet extends ConsumerStatefulWidget {
  const MembershipFeeSheet({
    super.key,
    required this.code,
    required this.title,
    required this.amount,
    required this.solvable,
  });

  final String code; // 'ADHESION' | 'INSCRIPTION'
  final String title;
  final num amount;
  final bool solvable;

  static Future<void> show(
    BuildContext context, {
    required String code,
    required String title,
    required num amount,
    required bool solvable,
  }) =>
      showModalBottomSheet<void>(
        context: context,
        isScrollControlled: true,
        backgroundColor: PaColors.canvas,
        shape: const RoundedRectangleBorder(
          borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
        ),
        builder: (_) => MembershipFeeSheet(
          code: code,
          title: title,
          amount: amount,
          solvable: solvable,
        ),
      );

  @override
  ConsumerState<MembershipFeeSheet> createState() => _State();
}

class _State extends ConsumerState<MembershipFeeSheet> {
  final _phoneCtrl = TextEditingController();
  bool _busy = false;
  bool _momo = false; // affiche le champ numéro

  @override
  void dispose() {
    _phoneCtrl.dispose();
    super.dispose();
  }

  Future<void> _payFromAccount() async {
    final l = AppL10n.of(context);
    setState(() => _busy = true);
    try {
      await ref
          .read(membershipFeesProvider.notifier)
          .payFromAccount(widget.code);
      unawaited(HapticFeedback.mediumImpact());
      if (!mounted) return;
      Navigator.of(context).pop();
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(l.fee_paid_success)),
      );
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(friendlyError(e))));
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _payMobileMoney() async {
    final l = AppL10n.of(context);
    final phone = _phoneCtrl.text.replaceAll(RegExp(r'\D'), '');
    if (phone.length < 8) {
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text(l.err_number_incomplete)));
      return;
    }
    setState(() => _busy = true);
    try {
      final data = await ref
          .read(membershipFeesProvider.notifier)
          .initMobileMoney(code: widget.code, phone: phone);
      if (!mounted) return;
      Navigator.of(context).pop();
      await TaraCheckoutLauncher.launchFromInitResponse(data);
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(friendlyError(e))));
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final l = AppL10n.of(context);
    return Padding(
      padding: EdgeInsets.only(bottom: MediaQuery.viewInsetsOf(context).bottom),
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
                widget.title,
                style: const TextStyle(
                  color: PaColors.inkPrimary,
                  fontSize: 19,
                  fontWeight: FontWeight.w700,
                ),
              ),
              const SizedBox(height: 4),
              Text(
                '${XAFFormatter.format(widget.amount)} XAF',
                style: const TextStyle(
                  color: PaColors.teal,
                  fontSize: 22,
                  fontWeight: FontWeight.w800,
                ),
              ),
              const SizedBox(height: 18),

              // Canal 1 — depuis le compte (si solvable)
              if (widget.solvable && !_momo) ...[
                PaCard(
                  padding: const EdgeInsets.all(16),
                  onTap: _busy ? null : _payFromAccount,
                  child: Row(
                    children: [
                      const Icon(Icons.account_balance_wallet_outlined,
                          color: PaColors.teal,),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(l.fee_from_account,
                                style: const TextStyle(
                                    color: PaColors.inkPrimary,
                                    fontSize: 14.5,
                                    fontWeight: FontWeight.w700,),),
                            const SizedBox(height: 2),
                            Text(l.fee_from_account_desc,
                                style: const TextStyle(
                                    color: PaColors.inkMuted, fontSize: 12.5,),),
                          ],
                        ),
                      ),
                      const Icon(Icons.chevron_right_rounded,
                          color: PaColors.inkMuted,),
                    ],
                  ),
                ),
                const SizedBox(height: 10),
              ],

              // Canal 2 — Mobile Money
              if (!_momo)
                PaCard(
                  padding: const EdgeInsets.all(16),
                  onTap: _busy ? null : () => setState(() => _momo = true),
                  child: Row(
                    children: [
                      const Icon(Icons.smartphone_outlined,
                          color: PaColors.navy,),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(l.fee_mobile_money,
                                style: const TextStyle(
                                    color: PaColors.inkPrimary,
                                    fontSize: 14.5,
                                    fontWeight: FontWeight.w700,),),
                            const SizedBox(height: 2),
                            Text(l.fee_mobile_money_desc,
                                style: const TextStyle(
                                    color: PaColors.inkMuted, fontSize: 12.5,),),
                          ],
                        ),
                      ),
                      const Icon(Icons.chevron_right_rounded,
                          color: PaColors.inkMuted,),
                    ],
                  ),
                ),

              // Formulaire Mobile Money
              if (_momo) ...[
                Text(l.common_number,
                    style: const TextStyle(
                      color: PaColors.inkSecondary,
                      fontSize: 12,
                      fontWeight: FontWeight.w700,
                      letterSpacing: 1.2,
                    ),),
                const SizedBox(height: 8),
                TextField(
                  controller: _phoneCtrl,
                  keyboardType: TextInputType.phone,
                  cursorColor: PaColors.teal,
                  decoration: InputDecoration(
                    prefixText: '+237 ',
                    hintText: '6 XX XX XX XX',
                    filled: true,
                    fillColor: PaColors.cardBg,
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(12),
                      borderSide: BorderSide.none,
                    ),
                  ),
                ),
                const SizedBox(height: 20),
                PaButton(
                  label: _busy ? '…' : l.fee_pay_cta,
                  onPressed: _busy ? null : _payMobileMoney,
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}
