import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../app/theme/paysika/pa_colors.dart';
import '../../../../app/theme/app_radii.dart';
import '../../../../app/theme/app_spacing.dart';
import '../../../../app/theme/app_typography.dart';
import '../../../../core/services/tara_checkout_launcher.dart';
import '../../../../core/widgets/brand_loader.dart';
import '../../../../core/widgets/paysika/pa_button.dart';
import '../../../../l10n/gen/app_localizations.dart';
import '../state/booklet_notifier.dart';

enum _Step { form, loading, success }

class OrderBookletSheet extends ConsumerStatefulWidget {
  const OrderBookletSheet({super.key});

  static Future<void> show(BuildContext context) {
    return showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      constraints: BoxConstraints(
        maxHeight: MediaQuery.sizeOf(context).height * 0.9,
      ),
      backgroundColor: Theme.of(context).colorScheme.surface,
      barrierColor: Colors.black.withValues(alpha: 0.45),
      shape: const RoundedRectangleBorder(borderRadius: AppRadii.sheet),
      builder: (_) => const OrderBookletSheet(),
    );
  }

  @override
  ConsumerState<OrderBookletSheet> createState() => _OrderBookletSheetState();
}

class _OrderBookletSheetState extends ConsumerState<OrderBookletSheet>
    with TickerProviderStateMixin {
  final _formKey = GlobalKey<FormState>();
  final _phoneCtrl = TextEditingController();
  // TODO: REMOVE_FOR_PROD — montant éditable pour tester STK Push à 100 XAF.
  // En prod, le backend pioche le tarif dans FeeType (carnet = 1 000 XAF).
  final _amountCtrl = TextEditingController(text: '100');
  _Step _step = _Step.form;
  late final AnimationController _checkCtrl;

  @override
  void initState() {
    super.initState();
    _checkCtrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 700),
    );
  }

  @override
  void dispose() {
    _phoneCtrl.dispose();
    _amountCtrl.dispose();
    _checkCtrl.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    HapticFeedback.mediumImpact();
    setState(() => _step = _Step.loading);
    try {
      final amount = int.tryParse(_amountCtrl.text.trim()) ?? 1000;
      await ref.read(bookletProvider.notifier).order(
            phone: _phoneCtrl.text,
            network: '',
            montant: amount,
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
            _Step.form => _form(),
            _Step.loading => _loading(),
            _Step.success => _success(context),
          },
        ),
      ),
    );
  }

  Widget _form() {
    final l = AppL10n.of(context);
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 8, 20, 24),
      child: Form(
        key: _formKey,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const _Grabber(),
            const SizedBox(height: AppSpacing.l),
            Text(l.bko_title,
                style: AppTypography.headingMedium,),
            const SizedBox(height: 4),
            Text(
              l.bko_sub,
              style: AppTypography.bodyMedium.copyWith(
                color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.7),
              ),
            ),
            const SizedBox(height: AppSpacing.xl),

            Text(l.common_number, style: AppTypography.labelMedium),
            const SizedBox(height: AppSpacing.s),
            TextFormField(
              controller: _phoneCtrl,
              keyboardType: TextInputType.phone,
              style: AppTypography.bodyLarge,
              decoration: InputDecoration(
                hintText: '6XX XX XX XX',
                prefixIcon: Padding(
                  padding: const EdgeInsets.only(left: 14, right: 8),
                  child: Text('+237  ', style: TextStyle(
                    color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.7),
                    fontWeight: FontWeight.w600,
                  ),),
                ),
                prefixIconConstraints:
                    const BoxConstraints(minWidth: 0, minHeight: 0),
              ),
              validator: (v) {
                final digits = (v ?? '').replaceAll(RegExp(r'\D'), '');
                if (digits.length < 8) return l.err_number_incomplete;
                return null;
              },
            ),

            const SizedBox(height: AppSpacing.l),

            // TODO: REMOVE_FOR_PROD — montant éditable mode test.
            Text('Montant (XAF) — mode test', style: AppTypography.labelMedium),
            const SizedBox(height: AppSpacing.s),
            TextFormField(
              controller: _amountCtrl,
              keyboardType: TextInputType.number,
              style: AppTypography.bodyLarge,
              decoration: const InputDecoration(
                hintText: '100',
                suffixText: 'XAF',
              ),
              validator: (v) {
                final n = int.tryParse((v ?? '').trim());
                if (n == null || n < 100) return 'Montant min : 100 XAF.';
                return null;
              },
            ),

            const SizedBox(height: AppSpacing.l),

            Container(
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                color: PaColors.warningSurface,
                borderRadius: BorderRadius.circular(14),
              ),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Icon(Icons.menu_book_rounded,
                      size: 18, color: PaColors.warning,),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      l.bko_after_note,
                      style: const TextStyle(
                        color: PaColors.warning,
                        fontSize: 12.5,
                        height: 1.5,
                      ),
                    ),
                  ),
                ],
              ),
            ),

            const SizedBox(height: AppSpacing.xl),

            PaButton(label: l.bko_pay, onPressed: _submit),
          ],
        ),
      ),
    );
  }

  Widget _loading() {
    final l = AppL10n.of(context);
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 8, 20, 36),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const _Grabber(),
          const SizedBox(height: 36),
          const BrandLoader(size: BrandLoaderSize.large),
          const SizedBox(height: 24),
          Text(
            l.bko_waiting_body('Mobile Money'),
            style: AppTypography.headingSmall,
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 8),
          Text(
            'Tara confirme la transaction…',
            style: AppTypography.bodyMedium.copyWith(color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.7)),
          ),
        ],
      ),
    );
  }

  Widget _success(BuildContext context) {
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
                Icons.menu_book_rounded,
                color: PaColors.success,
                size: 36,
              ),
            ),
          ),
          const SizedBox(height: 18),
          Text(l.bko_done_title, style: AppTypography.headingMedium),
          const SizedBox(height: 6),
          Text(
            'L\'agence va imprimer ton carnet sous 48 h.\nTu recevras une notification au retrait.',
            textAlign: TextAlign.center,
            style: AppTypography.bodyMedium.copyWith(
              color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.7),
              height: 1.45,
            ),
          ),
          if (LastTaraResponse.vendor != null || LastTaraResponse.status != null) ...[
            const SizedBox(height: 14),
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: PaColors.teal.withValues(alpha: 0.08),
                borderRadius: BorderRadius.circular(12),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  if (LastTaraResponse.prettyVendor != null)
                    Row(
                      children: [
                        const Icon(Icons.check_circle_outline_rounded,
                            size: 16, color: PaColors.teal,),
                        const SizedBox(width: 8),
                        Text(
                          'Confirmé : ${LastTaraResponse.prettyVendor}',
                          style: AppTypography.labelMedium.copyWith(
                            color: PaColors.teal,
                          ),
                        ),
                      ],
                    ),
                  if (LastTaraResponse.message != null) ...[
                    const SizedBox(height: 6),
                    Text(
                      'Statut Tara : ${LastTaraResponse.status} '
                      '(${LastTaraResponse.message})',
                      style: AppTypography.bodySmall.copyWith(
                        color: Theme.of(context).colorScheme.onSurface
                            .withValues(alpha: 0.7),
                      ),
                    ),
                  ],
                ],
              ),
            ),
          ],
          const SizedBox(height: 24),
          PaButton(
            label: l.common_understood,
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
