import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../../../app/theme/app_radii.dart';
import '../../../../app/theme/paysika/pa_colors.dart';
import '../../../../core/widgets/brand_loader.dart';
import '../../../../l10n/gen/app_localizations.dart';

enum _Step { form, loading, success }

/// Statut professionnel — aligné sur `MembershipRequest.StatutPro` backend.
enum _StatutPro { salarie, commercant, artisan, sansEmploi, autre }

/// Formulaire d'adhésion — recueille les 8 informations de l'Article 2 du
/// Règlement Intérieur pour soumettre une `MembershipRequest`.
///
/// Identité (nom complet, email), téléphone + WhatsApp, ville + lieu précis,
/// statut pro, contact d'urgence (nom + lien + téléphone), motivation.
/// Pièces (CNI, plan de localisation) remises à l'entretien (Art. 3).
///
/// Mock-only : flow visuel complet, persistance branchée plus tard via
/// `SubmitMembershipRequest`.
class MembershipFormSheet extends StatefulWidget {
  const MembershipFormSheet({super.key});

  static Future<void> show(BuildContext context) {
    return showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      constraints: BoxConstraints(
        maxHeight: MediaQuery.sizeOf(context).height * 0.9,
      ),
      backgroundColor: PaColors.canvas,
      barrierColor: PaColors.navyDeep.withValues(alpha: 0.55),
      shape: const RoundedRectangleBorder(borderRadius: AppRadii.sheet),
      builder: (_) => const MembershipFormSheet(),
    );
  }

  @override
  State<MembershipFormSheet> createState() => _MembershipFormSheetState();
}

class _MembershipFormSheetState extends State<MembershipFormSheet>
    with TickerProviderStateMixin {
  final _formKey = GlobalKey<FormState>();

  final _prenomCtrl = TextEditingController();
  final _nomCtrl = TextEditingController();
  final _emailCtrl = TextEditingController();
  final _phoneCtrl = TextEditingController();
  final _whatsappCtrl = TextEditingController();
  final _cityCtrl = TextEditingController();
  final _quartierCtrl = TextEditingController();
  final _urgenceNomCtrl = TextEditingController();
  final _urgenceLienCtrl = TextEditingController();
  final _urgencePhoneCtrl = TextEditingController();
  final _motivationCtrl = TextEditingController();
  _StatutPro? _statutPro;

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
    for (final c in [
      _prenomCtrl,
      _nomCtrl,
      _emailCtrl,
      _phoneCtrl,
      _whatsappCtrl,
      _cityCtrl,
      _quartierCtrl,
      _urgenceNomCtrl,
      _urgenceLienCtrl,
      _urgencePhoneCtrl,
      _motivationCtrl,
    ]) {
      c.dispose();
    }
    _checkCtrl.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    FocusScope.of(context).unfocus();
    HapticFeedback.mediumImpact();
    setState(() => _step = _Step.loading);
    await Future<void>.delayed(const Duration(milliseconds: 1400));
    if (!mounted) return;
    setState(() => _step = _Step.success);
    HapticFeedback.heavyImpact();
    _checkCtrl.forward();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedSize(
      duration: const Duration(milliseconds: 280),
      curve: Curves.easeOutCubic,
      alignment: Alignment.topCenter,
      child: Padding(
        padding: EdgeInsets.only(bottom: MediaQuery.viewInsetsOf(context).bottom),
        child: ConstrainedBox(
          constraints: BoxConstraints(
            maxHeight: MediaQuery.sizeOf(context).height * 0.92,
          ),
          child: SafeArea(
            top: false,
            child: switch (_step) {
              _Step.form => _formStep(),
              _Step.loading => _loadingStep(),
              _Step.success => _successStep(),
            },
          ),
        ),
      ),
    );
  }

  // ── Étape formulaire ────────────────────────────────────────────────────
  Widget _formStep() {
    final l = AppL10n.of(context);
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        const SizedBox(height: 10),
        const _Grabber(),
        Padding(
          padding: const EdgeInsets.fromLTRB(20, 16, 20, 6),
          child: Align(
            alignment: Alignment.centerLeft,
            child: Text(
              l.mf_title,
              style: const TextStyle(
                color: PaColors.inkPrimary,
                fontSize: 22,
                fontWeight: FontWeight.w700,
              ),
            ),
          ),
        ),
        Padding(
          padding: const EdgeInsets.fromLTRB(20, 0, 20, 4),
          child: Align(
            alignment: Alignment.centerLeft,
            child: Text(
              l.mf_intro,
              style: const TextStyle(color: PaColors.inkMuted, fontSize: 13.5, height: 1.4),
            ),
          ),
        ),
        Flexible(
          child: Form(
            key: _formKey,
            child: ListView(
              padding: const EdgeInsets.fromLTRB(20, 12, 20, 16),
              children: [
                _section(l.mf_section_identity),
                Row(
                  children: [
                    Expanded(child: _field(_prenomCtrl, l.common_firstname, required: true)),
                    const SizedBox(width: 10),
                    Expanded(child: _field(_nomCtrl, 'Nom', required: true)),
                  ],
                ),
                _field(_emailCtrl, l.common_email,
                    required: true,
                    keyboard: TextInputType.emailAddress,
                    validator: _emailValidator),

                _section(l.mf_section_contact),
                _field(_phoneCtrl, l.common_phone,
                    required: true, keyboard: TextInputType.phone, prefix: '+237 '),
                _field(_whatsappCtrl, l.mf_whatsapp,
                    keyboard: TextInputType.phone, prefix: '+237 '),

                _section(l.mf_section_location),
                _field(_cityCtrl, l.mf_city, required: true),
                _field(_quartierCtrl, l.mf_quartier, required: true),

                _section(l.mf_section_statut),
                _statutProField(),

                _section(l.mf_section_urgence),
                _field(_urgenceNomCtrl, l.mf_urgence_nom, required: true),
                Row(
                  children: [
                    Expanded(
                        child: _field(_urgenceLienCtrl, l.mf_urgence_lien,
                            required: true)),
                    const SizedBox(width: 10),
                    Expanded(
                        child: _field(_urgencePhoneCtrl, l.common_phone,
                            required: true, keyboard: TextInputType.phone)),
                  ],
                ),

                _section(l.mf_section_motivation),
                _field(_motivationCtrl, l.mf_motivation_q,
                    maxLines: 3),

                const SizedBox(height: 14),
                _feesNote(),
                const SizedBox(height: 18),
                _PrimaryButton(label: l.mf_submit, onTap: _submit),
              ],
            ),
          ),
        ),
      ],
    );
  }

  Widget _section(String title) => Padding(
        padding: const EdgeInsets.only(top: 18, bottom: 8),
        child: Text(
          title.toUpperCase(),
          style: const TextStyle(
            color: PaColors.inkMuted,
            fontSize: 11,
            fontWeight: FontWeight.w700,
            letterSpacing: 1.4,
          ),
        ),
      );

  Widget _field(
    TextEditingController ctrl,
    String label, {
    bool required = false,
    int maxLines = 1,
    TextInputType? keyboard,
    String? prefix,
    String? Function(String?)? validator,
  }) {
    final l = AppL10n.of(context);
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: TextFormField(
        controller: ctrl,
        keyboardType: keyboard,
        maxLines: maxLines,
        style: const TextStyle(color: PaColors.inkPrimary, fontSize: 15),
        decoration: InputDecoration(
          labelText: label,
          labelStyle: const TextStyle(color: PaColors.inkMuted, fontSize: 14),
          prefixText: prefix,
          prefixStyle: const TextStyle(
            color: PaColors.inkSecondary,
            fontWeight: FontWeight.w600,
          ),
          filled: true,
          fillColor: PaColors.cardBg,
          contentPadding:
              const EdgeInsets.symmetric(horizontal: 14, vertical: 14),
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
        validator: validator ??
            (required
                ? (v) => (v == null || v.trim().isEmpty) ? l.common_required : null
                : null),
      ),
    );
  }

  Widget _statutProField() {
    final l = AppL10n.of(context);
    String statutLabel(_StatutPro s) => switch (s) {
          _StatutPro.salarie => l.mf_statut_salarie,
          _StatutPro.commercant => l.mf_statut_commercant,
          _StatutPro.artisan => l.mf_statut_artisan,
          _StatutPro.sansEmploi => l.mf_statut_sansemploi,
          _StatutPro.autre => l.mf_statut_autre,
        };
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: DropdownButtonFormField<_StatutPro>(
        initialValue: _statutPro,
        isExpanded: true,
        decoration: InputDecoration(
          labelText: l.mf_statut,
          labelStyle: const TextStyle(color: PaColors.inkMuted, fontSize: 14),
          filled: true,
          fillColor: PaColors.cardBg,
          contentPadding:
              const EdgeInsets.symmetric(horizontal: 14, vertical: 14),
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
        items: [
          for (final s in _StatutPro.values)
            DropdownMenuItem(value: s, child: Text(statutLabel(s))),
        ],
        onChanged: (v) => setState(() => _statutPro = v),
        validator: (v) => v == null ? l.common_required : null,
      ),
    );
  }

  Widget _feesNote() {
    final l = AppL10n.of(context);
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: PaColors.tealSurface,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Icon(Icons.info_outline, color: PaColors.teal, size: 18),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              l.mf_fees_note,
              style: const TextStyle(
                color: PaColors.inkSecondary,
                fontSize: 12.5,
                height: 1.45,
              ),
            ),
          ),
        ],
      ),
    );
  }

  String? _emailValidator(String? v) {
    final l = AppL10n.of(context);
    final t = (v ?? '').trim();
    if (t.isEmpty) return l.common_required;
    if (!RegExp(r'^[^\s@]+@[^\s@]+\.[^\s@]+$').hasMatch(t)) {
      return l.mf_email_invalid;
    }
    return null;
  }

  // ── Étape loading ────────────────────────────────────────────────────────
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
          const SizedBox(height: 26),
          Text(
            l.mf_sending,
            style: const TextStyle(
              color: PaColors.inkPrimary,
              fontSize: 17,
              fontWeight: FontWeight.w700,
            ),
          ),
        ],
      ),
    );
  }

  // ── Étape succès ───────────────────────────────────────────────────────
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
              child: const Icon(Icons.check_rounded,
                  color: PaColors.success, size: 40),
            ),
          ),
          const SizedBox(height: 20),
          Text(
            l.mf_sent_title,
            style: const TextStyle(
              color: PaColors.inkPrimary,
              fontSize: 21,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 6),
          Text(
            l.mf_sent_body,
            textAlign: TextAlign.center,
            style: const TextStyle(color: PaColors.inkMuted, fontSize: 14, height: 1.5),
          ),
          const SizedBox(height: 24),
          _PrimaryButton(
            label: l.common_done,
            onTap: () => Navigator.of(context).pop(),
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


class _PrimaryButton extends StatelessWidget {
  const _PrimaryButton({required this.label, required this.onTap});
  final String label;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: double.infinity,
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(999),
          child: Container(
            height: 52,
            decoration: BoxDecoration(
              gradient: PaGradients.ctaPill,
              borderRadius: BorderRadius.circular(999),
            ),
            alignment: Alignment.center,
            child: Text(
              label,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(
                color: PaColors.onTeal,
                fontSize: 15,
                fontWeight: FontWeight.w700,
              ),
            ),
          ),
        ),
      ),
    );
  }
}
