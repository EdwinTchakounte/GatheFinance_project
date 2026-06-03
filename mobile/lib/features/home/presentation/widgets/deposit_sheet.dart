import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../app/theme/paysika/pa_colors.dart';
import '../../../../app/theme/paysika/pa_typography.dart';
import '../../../../core/formatters/xaf_formatter.dart';
import '../../../../core/widgets/brand_loader.dart';
import '../../../../core/widgets/paysika/pa_button.dart';
import '../../../../core/widgets/paysika/pa_card.dart';
import '../../../../l10n/gen/app_localizations.dart';
import '../../../savings/presentation/state/classic_savings_notifier.dart';
import '../../../savings/presentation/state/savings_notifier.dart';

enum _Network { mtn, orange }

extension _NetworkX on _Network {
  String get label => switch (this) {
        _Network.mtn => 'MTN Mobile Money',
        _Network.orange => 'Orange Money',
      };

  Color get accent => switch (this) {
        _Network.mtn => const Color(0xFFFFCC00),
        _Network.orange => const Color(0xFFFF7900),
      };
}


/// Modale de cotisation — style **Paysika** (palette navy/teal, cards soft).
///
/// 5 étapes :
///   1. channelChoice — 2 PaCard (Mobile Money / Agence)
///   2a. agencyInfo — rappel Akwa Bercy
///   2b. form — montant 48pt + opérateur + numéro + CTA pill cyan
///   3. loading — BrandLoader + sub texte
///   4. success — check icon + sub + bouton fermer
class DepositSheet extends ConsumerStatefulWidget {
  const DepositSheet({super.key, this.classic = false});

  /// `true` → dépôt sur l'**épargne classique** (compte dissocié de la
  /// cotisation). Démarre directement au formulaire (Mobile Money).
  final bool classic;

  @override
  ConsumerState<DepositSheet> createState() => _DepositSheetState();
}

class _DepositSheetState extends ConsumerState<DepositSheet>
    with TickerProviderStateMixin {
  final _formKey = GlobalKey<FormState>();
  final _amountCtrl = TextEditingController(text: '1000');
  final _phoneCtrl = TextEditingController(text: '699 11 22 33');
  _Network _network = _Network.mtn;

  late _Step _step;
  num? _committedAmount;
  late final AnimationController _checkCtrl;

  @override
  void initState() {
    super.initState();
    // Cotisation : choix du canal d'abord. Épargne classique : formulaire direct.
    _step = widget.classic ? _Step.form : _Step.channelChoice;
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
      _committedAmount = amount;
      _step = _Step.loading;
    });

    final network = _network == _Network.mtn ? 'MTN' : 'ORANGE';
    if (widget.classic) {
      await ref.read(classicSavingsProvider.notifier).deposit(
            amount: amount,
            phone: _phoneCtrl.text,
            network: network,
          );
    } else {
      await ref.read(savingsProvider.notifier).deposit(
            amount: amount,
            phone: _phoneCtrl.text,
            network: network,
          );
    }
    if (!mounted) return;

    final result =
        widget.classic ? ref.read(classicSavingsProvider) : ref.read(savingsProvider);
    result.when(
      data: (_) {
        setState(() => _step = _Step.success);
        HapticFeedback.heavyImpact();
        _checkCtrl.forward();
      },
      loading: () {},
      error: (err, _) {
        setState(() => _step = _Step.form);
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(err.toString())),
        );
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedSize(
      duration: const Duration(milliseconds: 280),
      curve: Curves.easeOutCubic,
      alignment: Alignment.topCenter,
      child: Padding(
        padding: EdgeInsets.only(bottom: MediaQuery.viewInsetsOf(context).bottom),
        child: SafeArea(
          top: false,
          child: switch (_step) {
            _Step.channelChoice => _channelChoiceStep(),
            _Step.agencyInfo => _agencyInfoStep(),
            _Step.form => _formStep(),
            _Step.loading => _loadingStep(),
            _Step.success => _successStep(),
          },
        ),
      ),
    );
  }

  // ───────────────────────────────────────────────────────────────────────
  // Étape 1 — Choix canal (Mobile Money OU Agence)
  // ───────────────────────────────────────────────────────────────────────
  Widget _channelChoiceStep() {
    final l = AppL10n.of(context);
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 10, 20, 26),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const _Grabber(),
          const SizedBox(height: 18),
          Text(
            l.dep_title,
            style: const TextStyle(
              color: PaColors.inkPrimary,
              fontSize: 22,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            l.dep_how,
            style: const TextStyle(color: PaColors.inkMuted, fontSize: 14),
          ),
          const SizedBox(height: 22),

          _ChannelCard(
            icon: Icons.smartphone_outlined,
            title: l.dep_mobile_money,
            subtitle: l.dep_mobile_sub,
            primary: true,
            onTap: () => setState(() => _step = _Step.form),
          ),
          const SizedBox(height: 10),
          _ChannelCard(
            icon: Icons.storefront_outlined,
            title: l.dep_agency,
            subtitle: l.dep_agency_sub,
            primary: false,
            onTap: () => setState(() => _step = _Step.agencyInfo),
          ),

          const SizedBox(height: 16),
          _InfoStrip(text: l.dep_cutoff_note),
        ],
      ),
    );
  }

  // ───────────────────────────────────────────────────────────────────────
  // Étape 1b — Info agence
  // ───────────────────────────────────────────────────────────────────────
  Widget _agencyInfoStep() {
    final l = AppL10n.of(context);
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 10, 20, 30),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const _Grabber(),
          const SizedBox(height: 18),
          Container(
            width: 56,
            height: 56,
            decoration: const BoxDecoration(
              color: PaColors.tealSurface,
              shape: BoxShape.circle,
            ),
            alignment: Alignment.center,
            child: const Icon(
              Icons.storefront_outlined,
              color: PaColors.teal,
              size: 28,
            ),
          ),
          const SizedBox(height: 18),
          Text(
            l.dep_agency_title,
            style: const TextStyle(
              color: PaColors.inkPrimary,
              fontSize: 19,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            l.dep_agency_body,
            style: const TextStyle(
              color: PaColors.inkSecondary,
              fontSize: 14,
              height: 1.5,
            ),
          ),
          const SizedBox(height: 18),

          PaCard(
            child: Column(
              children: [
                _AgencyRow(
                    icon: Icons.place_outlined, label: l.dep_agency_place),
                const SizedBox(height: 10),
                _AgencyRow(
                    icon: Icons.schedule_outlined, label: l.dep_agency_hours),
                const SizedBox(height: 10),
                _AgencyRow(
                    icon: Icons.timer_outlined, label: l.dep_agency_cutoff),
              ],
            ),
          ),

          const SizedBox(height: 24),
          Row(
            children: [
              Expanded(
                child: PaButton(
                  label: l.common_back,
                  variant: PaButtonVariant.outline,
                  onPressed: () =>
                      setState(() => _step = _Step.channelChoice),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: PaButton(
                  label: l.common_understood,
                  onPressed: () => Navigator.of(context).pop(),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  // ───────────────────────────────────────────────────────────────────────
  // Étape 2 — Formulaire montant + opérateur + numéro
  // ───────────────────────────────────────────────────────────────────────
  Widget _formStep() {
    final l = AppL10n.of(context);
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 10, 20, 26),
      // Scrollable → pas d'overflow quand le clavier monte ou en grande police.
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
              widget.classic ? l.classic_dep_title : l.dep_title,
              style: const TextStyle(
                color: PaColors.inkPrimary,
                fontSize: 22,
                fontWeight: FontWeight.w700,
              ),
            ),
            const SizedBox(height: 4),
            Text(
              widget.classic ? l.classic_dep_sub : l.dep_suggestion,
              style: const TextStyle(color: PaColors.inkMuted, fontSize: 13.5),
            ),

            const SizedBox(height: 22),

            // Montant — input geant inline
            Text(
              l.common_amount,
              style: const TextStyle(
                color: PaColors.inkSecondary,
                fontSize: 12,
                fontWeight: FontWeight.w700,
                letterSpacing: 1.4,
              ),
            ),
            const SizedBox(height: 6),
            TextFormField(
              controller: _amountCtrl,
              keyboardType: const TextInputType.numberWithOptions(decimal: false),
              inputFormatters: [FilteringTextInputFormatter.digitsOnly],
              onChanged: (_) => setState(() {}),
              style: const TextStyle(
                color: PaColors.inkPrimary,
                fontSize: 44,
                fontWeight: FontWeight.w700,
                letterSpacing: -0.5,
                height: 1.1,
              ),
              cursorColor: PaColors.teal,
              decoration: InputDecoration(
                hintText: '0',
                hintStyle: TextStyle(
                  color: PaColors.inkPrimary.withValues(alpha: 0.18),
                  fontSize: 44,
                  fontWeight: FontWeight.w700,
                ),
                border: const UnderlineInputBorder(
                  borderSide: BorderSide(color: PaColors.line),
                ),
                enabledBorder: const UnderlineInputBorder(
                  borderSide: BorderSide(color: PaColors.line),
                ),
                focusedBorder: const UnderlineInputBorder(
                  borderSide: BorderSide(color: PaColors.teal, width: 2),
                ),
                suffix: const Text(
                  ' XAF',
                  style: TextStyle(
                    color: PaColors.inkMuted,
                    fontSize: 14,
                    fontWeight: FontWeight.w700,
                    letterSpacing: 1.2,
                  ),
                ),
                contentPadding: const EdgeInsets.symmetric(vertical: 8),
              ),
              validator: (v) {
                final t = (v ?? '').trim();
                if (t.isEmpty) return l.err_enter_amount;
                final n = num.tryParse(t);
                if (n == null || n < 100) return l.err_min_100;
                return null;
              },
            ),

            const SizedBox(height: 12),

            // Chips raccourcis
            Wrap(
              spacing: 8,
              children: [
                for (final v in [1000, 2000, 5000, 10000])
                  _AmountChip(
                    value: v,
                    selected: _amountCtrl.text == '$v',
                    onTap: () => setState(() => _amountCtrl.text = '$v'),
                  ),
              ],
            ),

            const SizedBox(height: 22),

            Text(
              l.common_operator,
              style: const TextStyle(
                color: PaColors.inkSecondary,
                fontSize: 12,
                fontWeight: FontWeight.w700,
                letterSpacing: 1.4,
              ),
            ),
            const SizedBox(height: 8),
            Row(
              children: [
                for (final n in _Network.values) ...[
                  Expanded(
                    child: _NetworkCard(
                      network: n,
                      selected: _network == n,
                      onTap: () => setState(() => _network = n),
                    ),
                  ),
                  if (n != _Network.values.last) const SizedBox(width: 8),
                ],
              ],
            ),

            const SizedBox(height: 18),

            Text(
              l.common_number,
              style: const TextStyle(
                color: PaColors.inkSecondary,
                fontSize: 12,
                fontWeight: FontWeight.w700,
                letterSpacing: 1.4,
              ),
            ),
            const SizedBox(height: 8),
            TextFormField(
              controller: _phoneCtrl,
              keyboardType: TextInputType.phone,
              style: const TextStyle(
                color: PaColors.inkPrimary,
                fontSize: 16,
                fontWeight: FontWeight.w600,
              ),
              cursorColor: PaColors.teal,
              decoration: InputDecoration(
                prefixIcon: const Padding(
                  padding: EdgeInsets.only(left: 14, right: 8),
                  child: Text(
                    '+237',
                    style: TextStyle(
                      color: PaColors.inkSecondary,
                      fontWeight: FontWeight.w700,
                      fontSize: 16,
                    ),
                  ),
                ),
                prefixIconConstraints: const BoxConstraints(minWidth: 0, minHeight: 0),
                hintText: '6 XX XX XX XX',
                hintStyle: const TextStyle(color: PaColors.inkFaint),
                filled: true,
                fillColor: PaColors.cardBg,
                contentPadding: const EdgeInsets.symmetric(vertical: 14, horizontal: 8),
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12),
                  borderSide: BorderSide.none,
                ),
                enabledBorder: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12),
                  borderSide: BorderSide.none,
                ),
                focusedBorder: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12),
                  borderSide: const BorderSide(color: PaColors.teal, width: 1.5),
                ),
              ),
              validator: (v) {
                final digits = (v ?? '').replaceAll(RegExp(r'\D'), '');
                if (digits.length < 8) return l.err_number_incomplete;
                return null;
              },
            ),

            const SizedBox(height: 28),

            PaButton(label: _ctaLabel(), onPressed: _submit),
            ],
          ),
        ),
      ),
    );
  }

  String _ctaLabel() {
    final l = AppL10n.of(context);
    final n = num.tryParse(_amountCtrl.text.replaceAll(' ', ''));
    if (n == null || n <= 0) return l.dep_confirm_default;
    return l.dep_confirm_amount(XAFFormatter.format(n));
  }

  // ───────────────────────────────────────────────────────────────────────
  // Étape 3 — Loading
  // ───────────────────────────────────────────────────────────────────────
  Widget _loadingStep() {
    final l = AppL10n.of(context);
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 10, 20, 40),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const _Grabber(),
          const SizedBox(height: 36),
          const BrandLoader(size: BrandLoaderSize.large),
          const SizedBox(height: 28),
          Text(
            l.dep_waiting_title,
            style: PaText.heading(size: 17),
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 8),
          Text(
            l.dep_waiting_body(
                _network.label, XAFFormatter.format(_committedAmount ?? 0)),
            textAlign: TextAlign.center,
            style: const TextStyle(
              color: PaColors.inkMuted,
              fontSize: 13.5,
              height: 1.5,
            ),
          ),
          const SizedBox(height: 22),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 9),
            decoration: BoxDecoration(
              color: PaColors.tealSurface,
              borderRadius: BorderRadius.circular(999),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Icon(Icons.timer_outlined, size: 15, color: PaColors.teal),
                const SizedBox(width: 6),
                Text(
                  l.dep_waiting_hint,
                  style: const TextStyle(
                    color: PaColors.teal,
                    fontSize: 12,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  // ───────────────────────────────────────────────────────────────────────
  // Étape 4 — Success
  // ───────────────────────────────────────────────────────────────────────
  Widget _successStep() {
    final l = AppL10n.of(context);
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 10, 20, 30),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const _Grabber(),
          const SizedBox(height: 28),
          ScaleTransition(
            scale: CurvedAnimation(parent: _checkCtrl, curve: Curves.elasticOut),
            child: Container(
              width: 76,
              height: 76,
              decoration: const BoxDecoration(
                color: PaColors.successSurface,
                shape: BoxShape.circle,
              ),
              alignment: Alignment.center,
              child: const Icon(
                Icons.check_rounded,
                color: PaColors.success,
                size: 40,
              ),
            ),
          ),
          const SizedBox(height: 20),
          Text(
            l.dep_done_title,
            style: const TextStyle(
              color: PaColors.inkPrimary,
              fontSize: 21,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 6),
          Text(
            l.dep_done_body(XAFFormatter.format(_committedAmount ?? 0)),
            textAlign: TextAlign.center,
            style: const TextStyle(
              color: PaColors.inkMuted,
              fontSize: 14,
              height: 1.5,
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

enum _Step { channelChoice, agencyInfo, form, loading, success }


// ───────────────────────────────────────────────────────────────────────────
// Composants internes
// ───────────────────────────────────────────────────────────────────────────

class _Grabber extends StatelessWidget {
  const _Grabber();
  @override
  Widget build(BuildContext context) {
    return Center(
      child: Container(
        width: 40,
        height: 4,
        decoration: BoxDecoration(
          color: PaColors.line,
          borderRadius: BorderRadius.circular(2),
        ),
      ),
    );
  }
}


class _ChannelCard extends StatelessWidget {
  const _ChannelCard({
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.primary,
    required this.onTap,
  });

  final IconData icon;
  final String title;
  final String subtitle;
  final bool primary;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return PaCard(
      onTap: onTap,
      padding: const EdgeInsets.all(16),
      background: PaColors.cardBg,
      child: Row(
        children: [
          Container(
            width: 44,
            height: 44,
            decoration: BoxDecoration(
              color: primary
                  ? PaColors.tealSurface
                  : PaColors.paper,
              shape: BoxShape.circle,
              border: primary
                  ? null
                  : Border.all(color: PaColors.line, width: 1),
            ),
            alignment: Alignment.center,
            child: Icon(
              icon,
              color: primary ? PaColors.teal : PaColors.navy,
              size: 22,
            ),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: const TextStyle(
                    color: PaColors.inkPrimary,
                    fontSize: 15,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                const SizedBox(height: 3),
                Text(
                  subtitle,
                  style: const TextStyle(
                    color: PaColors.inkMuted,
                    fontSize: 12.5,
                    height: 1.3,
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(width: 8),
          const Icon(Icons.chevron_right_rounded, color: PaColors.inkMuted, size: 20),
        ],
      ),
    );
  }
}


class _InfoStrip extends StatelessWidget {
  const _InfoStrip({required this.text});
  final String text;
  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(
        color: PaColors.tealSurface,
        borderRadius: BorderRadius.circular(10),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Icon(Icons.info_outline, size: 16, color: PaColors.teal),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              text,
              style: const TextStyle(
                color: PaColors.inkSecondary,
                fontSize: 12,
                height: 1.4,
              ),
            ),
          ),
        ],
      ),
    );
  }
}


class _AgencyRow extends StatelessWidget {
  const _AgencyRow({required this.icon, required this.label});
  final IconData icon;
  final String label;
  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Icon(icon, size: 18, color: PaColors.teal),
        const SizedBox(width: 10),
        Expanded(
          child: Text(
            label,
            style: const TextStyle(
              color: PaColors.inkPrimary,
              fontSize: 13.5,
              fontWeight: FontWeight.w500,
            ),
          ),
        ),
      ],
    );
  }
}


class _AmountChip extends StatelessWidget {
  const _AmountChip({
    required this.value,
    required this.selected,
    required this.onTap,
  });
  final int value;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(999),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 180),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
        decoration: BoxDecoration(
          color: selected ? PaColors.navy : PaColors.cardBg,
          borderRadius: BorderRadius.circular(999),
          border: Border.all(
            color: selected ? PaColors.navy : PaColors.line,
            width: 1,
          ),
        ),
        child: Text(
          '+ ${XAFFormatter.formatNumber(value)}',
          style: TextStyle(
            color: selected ? Colors.white : PaColors.inkPrimary,
            fontSize: 13,
            fontWeight: FontWeight.w700,
            fontFeatures: const [FontFeature.tabularFigures()],
          ),
        ),
      ),
    );
  }
}


class _NetworkCard extends StatelessWidget {
  const _NetworkCard({
    required this.network,
    required this.selected,
    required this.onTap,
  });
  final _Network network;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(12),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 180),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 14),
        decoration: BoxDecoration(
          color: selected ? PaColors.tealSurface : PaColors.cardBg,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(
            color: selected ? PaColors.teal : PaColors.line,
            width: selected ? 1.6 : 1,
          ),
        ),
        child: Row(
          children: [
            Container(
              width: 10,
              height: 10,
              decoration: BoxDecoration(
                color: network.accent,
                shape: BoxShape.circle,
              ),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: Text(
                network.label,
                style: const TextStyle(
                  color: PaColors.inkPrimary,
                  fontSize: 13.5,
                  fontWeight: FontWeight.w600,
                ),
                overflow: TextOverflow.ellipsis,
              ),
            ),
            if (selected)
              const Icon(
                Icons.check_circle_rounded,
                size: 18,
                color: PaColors.teal,
              ),
          ],
        ),
      ),
    );
  }
}


