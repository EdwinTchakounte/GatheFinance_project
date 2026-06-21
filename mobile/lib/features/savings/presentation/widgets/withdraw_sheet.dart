import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../app/theme/paysika/pa_colors.dart';
import '../../../../core/di/providers.dart';
import '../../../../core/formatters/xaf_formatter.dart';
import '../../../../core/widgets/brand_loader.dart';
import '../../../../core/widgets/paysika/pa_button.dart';
import '../../../../core/widgets/paysika/pa_card.dart';
import '../../../../l10n/gen/app_localizations.dart';
import '../../domain/entities/withdrawal_request.dart';
import '../../domain/usecases/request_withdrawal.dart';
import '../state/savings_notifier.dart';

enum _WithdrawStep { form, loading, success }

enum _MomoNet { mtn, orange, wave, airtel }

extension on _MomoNet {
  MomoNetwork toDomain() => switch (this) {
        _MomoNet.mtn => MomoNetwork.mtn,
        _MomoNet.orange => MomoNetwork.orange,
        _MomoNet.wave => MomoNetwork.wave,
        _MomoNet.airtel => MomoNetwork.airtel,
      };

  String get label => switch (this) {
        _MomoNet.mtn => 'MTN Mobile Money',
        _MomoNet.orange => 'Orange Money',
        _MomoNet.wave => 'Wave',
        _MomoNet.airtel => 'Airtel Money',
      };
}

/// Modale de demande de retrait — solde débité atomiquement côté backend dès
/// soumission, puis attente de validation admin.
class WithdrawSheet extends ConsumerStatefulWidget {
  const WithdrawSheet({super.key, required this.soldeDisponible});

  /// Solde actuel de la cotisation — affiché en hint pour borner la saisie.
  final num soldeDisponible;

  @override
  ConsumerState<WithdrawSheet> createState() => _WithdrawSheetState();
}

class _WithdrawSheetState extends ConsumerState<WithdrawSheet> {
  final _formKey = GlobalKey<FormState>();
  final _amountCtrl = TextEditingController();
  final _motifCtrl = TextEditingController();
  final _phoneCtrl = TextEditingController();
  WithdrawalChannel _channel = WithdrawalChannel.presentiel;
  _MomoNet _network = _MomoNet.mtn;
  _WithdrawStep _step = _WithdrawStep.form;
  WithdrawalRequest? _result;
  String? _error;

  @override
  void dispose() {
    _amountCtrl.dispose();
    _motifCtrl.dispose();
    _phoneCtrl.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    final amount = num.parse(_amountCtrl.text.replaceAll(' ', ''));
    if (amount > widget.soldeDisponible) {
      setState(() => _error = AppL10n.of(context).wd_err_over_balance);
      return;
    }
    HapticFeedback.mediumImpact();
    setState(() {
      _step = _WithdrawStep.loading;
      _error = null;
    });
    try {
      final wr = await ref.read(requestWithdrawalUseCaseProvider).call(
            RequestWithdrawalParams(
              amount: amount,
              motif: _motifCtrl.text,
              channel: _channel,
              recipientPhone:
                  _channel == WithdrawalChannel.momo ? _phoneCtrl.text : '',
              network: _channel == WithdrawalChannel.momo
                  ? _network.toDomain()
                  : null,
            ),
          );
      if (!mounted) return;
      // Refresh solde + liste retraits — backend a déjà débité.
      ref.invalidate(savingsProvider);
      setState(() {
        _result = wr;
        _step = _WithdrawStep.success;
      });
      HapticFeedback.heavyImpact();
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _step = _WithdrawStep.form;
        _error = e.toString().replaceFirst('Exception: ', '');
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedSize(
      duration: const Duration(milliseconds: 240),
      curve: Curves.easeOutCubic,
      alignment: Alignment.topCenter,
      child: Padding(
        padding:
            EdgeInsets.only(bottom: MediaQuery.viewInsetsOf(context).bottom),
        child: SafeArea(
          top: false,
          child: switch (_step) {
            _WithdrawStep.form => _formStep(),
            _WithdrawStep.loading => _loadingStep(),
            _WithdrawStep.success => _successStep(),
          },
        ),
      ),
    );
  }

  Widget _formStep() {
    final l = AppL10n.of(context);
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 10, 20, 26),
      child: SingleChildScrollView(
        child: Form(
          key: _formKey,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const _Grabber(),
              const SizedBox(height: 18),
              Text(
                l.wd_title,
                style: const TextStyle(
                  color: PaColors.inkPrimary,
                  fontSize: 22,
                  fontWeight: FontWeight.w700,
                ),
              ),
              const SizedBox(height: 4),
              Text(
                l.wd_subtitle(XAFFormatter.format(widget.soldeDisponible)),
                style: const TextStyle(color: PaColors.inkMuted, fontSize: 14),
              ),
              const SizedBox(height: 18),

              // Canal — Présentiel vs MOMO
              Row(
                children: [
                  Expanded(
                    child: _ChannelChip(
                      label: l.wd_channel_presentiel,
                      icon: Icons.store_outlined,
                      selected: _channel == WithdrawalChannel.presentiel,
                      onTap: () => setState(
                          () => _channel = WithdrawalChannel.presentiel,),
                    ),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: _ChannelChip(
                      label: l.wd_channel_momo,
                      icon: Icons.phone_iphone_rounded,
                      selected: _channel == WithdrawalChannel.momo,
                      onTap: () =>
                          setState(() => _channel = WithdrawalChannel.momo),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 18),

              TextFormField(
                controller: _amountCtrl,
                keyboardType: TextInputType.number,
                decoration: InputDecoration(
                  labelText: l.wd_field_amount,
                  prefixText: 'XAF ',
                  border: const OutlineInputBorder(),
                ),
                validator: (v) {
                  final s = (v ?? '').replaceAll(' ', '');
                  if (s.isEmpty) return l.wd_err_required;
                  final n = num.tryParse(s);
                  if (n == null || n < 500) return l.wd_err_min_500;
                  return null;
                },
              ),
              const SizedBox(height: 14),
              TextFormField(
                controller: _motifCtrl,
                maxLines: 2,
                decoration: InputDecoration(
                  labelText: l.wd_field_motif,
                  hintText: l.wd_field_motif_hint,
                  border: const OutlineInputBorder(),
                ),
              ),
              if (_channel == WithdrawalChannel.momo) ...[
                const SizedBox(height: 14),
                TextFormField(
                  controller: _phoneCtrl,
                  keyboardType: TextInputType.phone,
                  decoration: InputDecoration(
                    labelText: l.wd_field_phone,
                    prefixIcon: const Icon(Icons.phone_outlined),
                    border: const OutlineInputBorder(),
                  ),
                  validator: (v) {
                    if (_channel != WithdrawalChannel.momo) return null;
                    if ((v ?? '').trim().length < 8) return l.wd_err_phone;
                    return null;
                  },
                ),
                const SizedBox(height: 12),
                DropdownButtonFormField<_MomoNet>(
                  initialValue: _network,
                  decoration: InputDecoration(
                    labelText: l.wd_field_network,
                    border: const OutlineInputBorder(),
                  ),
                  items: _MomoNet.values
                      .map((n) => DropdownMenuItem(value: n, child: Text(n.label)))
                      .toList(),
                  onChanged: (v) =>
                      setState(() => _network = v ?? _MomoNet.mtn),
                ),
              ],
              if (_error != null) ...[
                const SizedBox(height: 12),
                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: const Color(0xFFFDECEA),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Row(
                    children: [
                      const Icon(Icons.error_outline,
                          color: Color(0xFFB3261E), size: 18,),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          _error!,
                          style: const TextStyle(
                              color: Color(0xFFB3261E), fontSize: 13,),
                        ),
                      ),
                    ],
                  ),
                ),
              ],
              const SizedBox(height: 22),
              PaButton(
                label: l.wd_cta_submit,
                onPressed: _submit,
                fullWidth: true,
              ),
              const SizedBox(height: 8),
              Text(
                l.wd_disclaimer,
                style: const TextStyle(color: PaColors.inkMuted, fontSize: 11),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _loadingStep() {
    final l = AppL10n.of(context);
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 30, 20, 60),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const _Grabber(),
          const SizedBox(height: 30),
          const BrandLoader(),
          const SizedBox(height: 18),
          Text(
            l.wd_loading,
            style: const TextStyle(color: PaColors.inkMuted, fontSize: 14),
          ),
        ],
      ),
    );
  }

  Widget _successStep() {
    final l = AppL10n.of(context);
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 10, 20, 26),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const _Grabber(),
          const SizedBox(height: 18),
          Center(
            child: Container(
              width: 64,
              height: 64,
              decoration: const BoxDecoration(
                color: PaColors.tealSurface,
                shape: BoxShape.circle,
              ),
              child: const Icon(
                Icons.check_rounded,
                color: PaColors.teal,
                size: 38,
              ),
            ),
          ),
          const SizedBox(height: 18),
          Text(
            l.wd_success_title,
            textAlign: TextAlign.center,
            style: const TextStyle(
              color: PaColors.inkPrimary,
              fontSize: 20,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 8),
          if (_result != null)
            PaCard(
              child: Padding(
                padding: const EdgeInsets.all(14),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    _SummaryLine(
                      label: l.wd_recap_amount,
                      value: XAFFormatter.format(_result!.montant),
                    ),
                    const SizedBox(height: 6),
                    _SummaryLine(
                      label: l.wd_recap_channel,
                      value: _result!.modePaiementDisplay,
                    ),
                    const SizedBox(height: 6),
                    _SummaryLine(
                      label: l.wd_recap_status,
                      value: _result!.statutDisplay,
                    ),
                  ],
                ),
              ),
            ),
          const SizedBox(height: 18),
          PaButton(
            label: l.wd_cta_close,
            onPressed: () => Navigator.of(context).pop(),
            fullWidth: true,
          ),
        ],
      ),
    );
  }
}

class _Grabber extends StatelessWidget {
  const _Grabber();

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Container(
        width: 38,
        height: 4,
        decoration: BoxDecoration(
          color: PaColors.inkMuted.withValues(alpha: 0.25),
          borderRadius: BorderRadius.circular(2),
        ),
      ),
    );
  }
}

class _ChannelChip extends StatelessWidget {
  const _ChannelChip({
    required this.label,
    required this.icon,
    required this.selected,
    required this.onTap,
  });

  final String label;
  final IconData icon;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(14),
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 14, horizontal: 12),
        decoration: BoxDecoration(
          color: selected ? PaColors.tealSurface : PaColors.paper,
          borderRadius: BorderRadius.circular(14),
          border: Border.all(
            color: selected ? PaColors.teal : PaColors.inkMuted.withValues(alpha: 0.2),
            width: selected ? 1.6 : 1,
          ),
        ),
        child: Column(
          children: [
            Icon(icon, color: selected ? PaColors.teal : PaColors.inkPrimary),
            const SizedBox(height: 6),
            Text(
              label,
              textAlign: TextAlign.center,
              style: TextStyle(
                color: selected ? PaColors.teal : PaColors.inkPrimary,
                fontSize: 13,
                fontWeight: FontWeight.w600,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _SummaryLine extends StatelessWidget {
  const _SummaryLine({required this.label, required this.value});
  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Text(label, style: const TextStyle(color: PaColors.inkMuted, fontSize: 13)),
        Flexible(
          child: Text(
            value,
            textAlign: TextAlign.end,
            style: const TextStyle(
              color: PaColors.inkPrimary,
              fontSize: 13,
              fontWeight: FontWeight.w600,
            ),
          ),
        ),
      ],
    );
  }
}
