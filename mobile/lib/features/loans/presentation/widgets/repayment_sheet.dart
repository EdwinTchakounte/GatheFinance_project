import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../app/theme/paysika/pa_colors.dart';
import '../../../../app/theme/app_radii.dart';
import '../../../../app/theme/app_spacing.dart';
import '../../../../app/theme/app_typography.dart';
import '../../../../core/formatters/xaf_formatter.dart';
import '../../../../core/widgets/brand_loader.dart';
import '../../../../core/widgets/paysika/pa_button.dart';
import '../../../../l10n/gen/app_localizations.dart';
import '../../domain/entities/loan.dart';
import '../state/loans_notifier.dart';

enum _Network { mtn, orange }
enum _Step { form, loading, success }

/// Modale de remboursement échéance — 3 étapes (form → loader → success).
class RepaymentSheet extends ConsumerStatefulWidget {
  const RepaymentSheet({super.key, required this.loan});

  final Loan loan;

  static Future<void> show(BuildContext context, Loan loan) {
    return showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      // Plafonne le sheet pour qu'il flotte avec une marge sous la status bar
      // au lieu de grimper plein écran ; scroll interne si le contenu dépasse.
      constraints: BoxConstraints(
        maxHeight: MediaQuery.sizeOf(context).height * 0.9,
      ),
      backgroundColor: Theme.of(context).colorScheme.surface,
      barrierColor: Colors.black.withValues(alpha: 0.45),
      shape: const RoundedRectangleBorder(borderRadius: AppRadii.sheet),
      builder: (_) => RepaymentSheet(loan: loan),
    );
  }

  @override
  ConsumerState<RepaymentSheet> createState() => _RepaymentSheetState();
}

class _RepaymentSheetState extends ConsumerState<RepaymentSheet>
    with TickerProviderStateMixin {
  final _formKey = GlobalKey<FormState>();
  late final TextEditingController _amountCtrl;
  final _phoneCtrl = TextEditingController(text: '699 11 22 33');
  _Network _network = _Network.mtn;
  _Step _step = _Step.form;
  late final AnimationController _checkCtrl;
  num? _commited;

  @override
  void initState() {
    super.initState();
    // Pré-remplit avec le restant dû de la prochaine échéance.
    final next = widget.loan.nextDue;
    final defaultAmount = next != null ? next.restantDu.round() : 0;
    _amountCtrl = TextEditingController(text: '$defaultAmount');
    _checkCtrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 700),
    );
  }

  @override
  void dispose() {
    _amountCtrl.dispose();
    _phoneCtrl.dispose();
    _checkCtrl.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    final amount = num.parse(_amountCtrl.text.replaceAll(' ', ''));
    HapticFeedback.mediumImpact();
    setState(() {
      _commited = amount;
      _step = _Step.loading;
    });
    try {
      await ref.read(loansProvider.notifier).repay(
            loanId: widget.loan.id,
            montant: amount,
            phone: _phoneCtrl.text,
            network: _network == _Network.mtn ? 'MTN' : 'ORANGE',
          );
      if (!mounted) return;
      setState(() => _step = _Step.success);
      HapticFeedback.heavyImpact();
      _checkCtrl.forward();
    } catch (err) {
      if (!mounted) return;
      setState(() => _step = _Step.form);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(err.toString())),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedSize(
      duration: const Duration(milliseconds: 280),
      curve: Curves.easeOutCubic,
      alignment: Alignment.topCenter,
      child: Padding(
        padding: EdgeInsets.only(
          bottom: MediaQuery.viewInsetsOf(context).bottom,
        ),
        child: SafeArea(
          top: false,
          child: switch (_step) {
            _Step.form => _formStep(),
            _Step.loading => _loadingStep(),
            _Step.success => _successStep(context),
          },
        ),
      ),
    );
  }

  Widget _formStep() {
    final next = widget.loan.nextDue;
    final l = AppL10n.of(context);
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 8, 20, 24),
      child: SingleChildScrollView(
        child: Form(
        key: _formKey,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const _Grabber(),
            const SizedBox(height: AppSpacing.l),
            Text(l.rep_title, style: AppTypography.headingMedium),
            const SizedBox(height: 4),
            Text(
              widget.loan.numeroDossier,
              style: AppTypography.bodySmall.copyWith(
                color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.5),
                fontFeatures: const [FontFeature.tabularFigures()],
              ),
            ),
            const SizedBox(height: AppSpacing.l),
            // Info prochaine échéance
            if (next != null)
              Container(
                padding: const EdgeInsets.all(14),
                decoration: BoxDecoration(
                  color: PaColors.tealSurface,
                  borderRadius: BorderRadius.circular(16),
                ),
                child: Row(
                  children: [
                    Container(
                      width: 36,
                      height: 36,
                      decoration: BoxDecoration(
                        color: PaColors.teal.withValues(alpha: 0.18),
                        borderRadius: BorderRadius.circular(10),
                      ),
                      alignment: Alignment.center,
                      child: const Icon(
                        Icons.schedule_rounded,
                        size: 18,
                        color: PaColors.teal,
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            l.rep_installment_n('${next.numero}'),
                            style: AppTypography.labelMedium.copyWith(
                              color: PaColors.teal,
                            ),
                          ),
                          const SizedBox(height: 2),
                          Text(
                            l.rep_remaining_due(
                                XAFFormatter.format(next.restantDu)),
                            style: AppTypography.bodySmall.copyWith(
                              color: PaColors.navyDeep,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),

            const SizedBox(height: AppSpacing.l),

            Text(l.common_amount, style: AppTypography.labelMedium),
            const SizedBox(height: AppSpacing.s),
            TextFormField(
              controller: _amountCtrl,
              keyboardType: const TextInputType.numberWithOptions(decimal: false),
              inputFormatters: [FilteringTextInputFormatter.digitsOnly],
              style: AppTypography.displayLarge.copyWith(
                fontSize: 32,
                color: Theme.of(context).colorScheme.onSurface,
              ),
              decoration: InputDecoration(
                hintText: '0',
                hintStyle: AppTypography.displayLarge.copyWith(
                  fontSize: 32,
                  color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.35),
                ),
                suffixIcon: Padding(
                  padding: const EdgeInsets.only(right: 18),
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Text(
                        'XAF',
                        style: AppTypography.labelMedium.copyWith(
                          color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.5),
                          letterSpacing: 1.2,
                        ),
                      ),
                    ],
                  ),
                ),
                suffixIconConstraints:
                    const BoxConstraints(minWidth: 0, minHeight: 0),
              ),
              validator: (v) {
                final t = (v ?? '').trim();
                if (t.isEmpty) return l.err_enter_amount;
                final n = num.tryParse(t);
                if (n == null || n < 100) return l.err_min_100;
                return null;
              },
            ),

            const SizedBox(height: AppSpacing.l),

            Text(l.rep_operator_mm, style: AppTypography.labelMedium),
            const SizedBox(height: AppSpacing.s),
            Row(
              children: [
                for (final n in _Network.values) ...[
                  Expanded(
                    child: _NetworkChip(
                      network: n,
                      selected: _network == n,
                      onTap: () => setState(() => _network = n),
                    ),
                  ),
                  if (n != _Network.values.last) const SizedBox(width: 8),
                ],
              ],
            ),

            const SizedBox(height: AppSpacing.l),

            Text(l.common_number, style: AppTypography.labelMedium),
            const SizedBox(height: AppSpacing.s),
            TextFormField(
              controller: _phoneCtrl,
              keyboardType: TextInputType.phone,
              decoration: InputDecoration(
                hintText: '6XX XX XX XX',
                prefixIcon: Padding(
                  padding: const EdgeInsets.only(left: 14, right: 8),
                  child: Text('+237  ', style: TextStyle(
                    color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.7),
                    fontWeight: FontWeight.w600,
                  )),
                ),
                prefixIconConstraints:
                    const BoxConstraints(minWidth: 0, minHeight: 0),
              ),
              style: AppTypography.bodyLarge,
              validator: (v) {
                final digits = (v ?? '').replaceAll(RegExp(r'\D'), '');
                if (digits.length < 8) return l.err_number_incomplete;
                return null;
              },
            ),

            const SizedBox(height: AppSpacing.xxl),

            PaButton(label: l.rep_confirm, onPressed: _submit),
          ],
        ),
      ),
      ),
    );
  }

  Widget _loadingStep() {
    final l = AppL10n.of(context);
    final netLabel =
        _network == _Network.mtn ? 'MTN Mobile Money' : 'Orange Money';
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 8, 20, 36),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const _Grabber(),
          const SizedBox(height: 36),
          const BrandLoader(size: BrandLoaderSize.large),
          const SizedBox(height: 28),
          Text(
            l.dep_waiting_title,
            style: AppTypography.headingSmall,
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 10),
          Text(
            l.rep_waiting_body(netLabel),
            textAlign: TextAlign.center,
            style: AppTypography.bodyMedium.copyWith(
              color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.7),
              height: 1.45,
            ),
          ),
        ],
      ),
    );
  }

  Widget _successStep(BuildContext context) {
    final l = AppL10n.of(context);
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 8, 20, 28),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const _Grabber(),
          const SizedBox(height: 28),
          ScaleTransition(
            scale: CurvedAnimation(
              parent: _checkCtrl,
              curve: Curves.elasticOut,
            ),
            child: Container(
              width: 72,
              height: 72,
              decoration: BoxDecoration(
                color: PaColors.success.withValues(alpha: 0.14),
                shape: BoxShape.circle,
              ),
              alignment: Alignment.center,
              child: const Icon(
                Icons.check_rounded,
                color: PaColors.success,
                size: 38,
              ),
            ),
          ),
          const SizedBox(height: 18),
          Text(l.rep_done_title, style: AppTypography.headingMedium),
          const SizedBox(height: 6),
          Text(
            l.rep_done_body(XAFFormatter.format(_commited ?? 0)),
            textAlign: TextAlign.center,
            style: AppTypography.bodyMedium.copyWith(
              color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.7),
              height: 1.45,
            ),
          ),
          const SizedBox(height: 24),
          PaButton(
            label: l.common_done,
            onPressed: () => Navigator.of(context).pop(),
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
        width: 36,
        height: 4,
        decoration: BoxDecoration(
          color: Theme.of(context).colorScheme.outline,
          borderRadius: BorderRadius.circular(2),
        ),
      ),
    );
  }
}


class _NetworkChip extends StatelessWidget {
  const _NetworkChip({
    required this.network,
    required this.selected,
    required this.onTap,
  });

  final _Network network;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final accent = network == _Network.mtn
        ? const Color(0xFFFFCC00)
        : const Color(0xFFFF7900);
    final label = network == _Network.mtn ? 'MTN Mobile Money' : 'Orange Money';
    return InkWell(
      onTap: onTap,
      borderRadius: const BorderRadius.all(AppRadii.r16),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 180),
        padding:
            const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
        decoration: BoxDecoration(
          color: Theme.of(context).colorScheme.surface,
          borderRadius: const BorderRadius.all(AppRadii.r16),
          border: Border.all(
            color: selected ? PaColors.teal : Theme.of(context).colorScheme.outline,
            width: selected ? 1.8 : 1,
          ),
        ),
        child: Row(
          children: [
            Container(
              width: 10,
              height: 10,
              decoration: BoxDecoration(
                color: accent,
                shape: BoxShape.circle,
              ),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: Text(
                label,
                style: AppTypography.labelMedium,
                overflow: TextOverflow.ellipsis,
              ),
            ),
            if (selected)
              const Icon(Icons.check_circle_rounded,
                  size: 18, color: PaColors.teal),
          ],
        ),
      ),
    );
  }
}
