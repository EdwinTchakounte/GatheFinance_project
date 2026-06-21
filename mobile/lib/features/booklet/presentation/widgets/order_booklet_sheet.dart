import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../app/theme/paysika/pa_colors.dart';
import '../../../../app/theme/app_radii.dart';
import '../../../../app/theme/app_spacing.dart';
import '../../../../app/theme/app_typography.dart';
import '../../../../core/widgets/brand_loader.dart';
import '../../../../core/widgets/paysika/pa_button.dart';
import '../../../../l10n/gen/app_localizations.dart';
import '../state/booklet_notifier.dart';

enum _Network { mtn, orange }
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
  final _phoneCtrl = TextEditingController(text: '699 11 22 33');
  _Network _network = _Network.mtn;
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
    _checkCtrl.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    HapticFeedback.mediumImpact();
    setState(() => _step = _Step.loading);
    try {
      await ref.read(bookletProvider.notifier).order(
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
    final netLabel = _network == _Network.mtn ? 'MTN Mobile Money' : 'Orange Money';
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
            l.bko_waiting_body(netLabel),
            style: AppTypography.headingSmall,
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 8),
          Text(
            'pour valider 1 000 XAF.',
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
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
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
                  size: 18, color: PaColors.teal,),
          ],
        ),
      ),
    );
  }
}
