import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../../app/theme/app_radii.dart';
import '../../../../app/theme/app_spacing.dart';
import '../../../../app/theme/app_typography.dart';
import '../../../../app/theme/paysika/pa_colors.dart';
import '../../../security/data/biometric_service.dart';
import '../../../security/presentation/state/pin_notifier.dart';
import '../../../../core/widgets/app_card.dart';
import '../../../../core/widgets/logo_mark.dart';
import '../../../../core/widgets/paysika/pa_button.dart';
import '../../../../core/widgets/paysika/pa_gradient_header_band.dart';
import '../../../../core/widgets/paysika/pa_pattern_background.dart';
import '../../../../l10n/gen/app_localizations.dart';
import '../../../auth/presentation/state/auth_notifier.dart';
import '../../../preferences/presentation/state/locale_notifier.dart';
import '../../../preferences/presentation/widgets/language_choice_sheet.dart';

class ProfilePage extends ConsumerWidget {
  const ProfilePage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final member = ref.watch(authProvider).valueOrNull;
    final locale = ref.watch(localeProvider).valueOrNull ?? const Locale('fr');
    final languageLabel =
        locale.languageCode == 'en' ? 'English' : 'Français';
    final l = AppL10n.of(context);

    return Scaffold(
      backgroundColor: PaColors.canvas,
      body: PaPatternBackground(
        child: SafeArea(
        bottom: false,
        child: Column(
          children: [
            // Header compact . band gradient soft vert→bleu
            PaGradientHeaderBand(title: l.profile_title),
            Expanded(
              child: ListView(
                padding: const EdgeInsets.fromLTRB(
                  AppSpacing.l,
                  AppSpacing.l,
                  AppSpacing.l,
                  AppSpacing.huge,
                ),
                children: [
              // ── Hero identité . gradient cobalt + avatar lumineux ──
              _IdentityHero(
                fullName: member?.fullName ?? l.profile_member_badge,
                email: member?.email ?? '.',
                memberNumber: member?.numeroMembre ?? 'GF-XXXX-XXXX',
                initials: _initials(member?.prenom, member?.nom),
              ),

              const SizedBox(height: AppSpacing.l),

              // ── Données financières ──────────────────────────────
              _SectionLabel(l.profile_section_finances),
              const SizedBox(height: AppSpacing.s),
              AppCard(
                variant: AppCardVariant.glass,
                padding: EdgeInsets.zero,
                child: Column(
                  children: [
                    _Tile(
                      icon: Icons.summarize_outlined,
                      tint: PaColors.teal,
                      label: l.profile_tile_states,
                      subtitle: l.profile_tile_states_sub,
                      onTap: () => context.push('/states'),
                    ),
                    const _TileDivider(),
                    _Tile(
                      icon: Icons.receipt_long_outlined,
                      tint: PaColors.warning,
                      label: l.profile_tile_contributions,
                      subtitle: l.profile_tile_contributions_sub,
                      onTap: () => context.push('/contributions'),
                    ),
                    const _TileDivider(),
                    // LOT 19 . Espace prêteur complet (convention, tranches,
                    // funding 24h). Distinct de /me/lender-payouts (CH-12)
                    // qui n'affiche que l'historique des intérêts touchés.
                    _Tile(
                      icon: Icons.handshake_outlined,
                      tint: PaColors.blue,
                      label: l.profile_tile_lender,
                      subtitle: l.profile_tile_lender_sub,
                      onTap: () => context.push('/me/lender'),
                    ),
                  ],
                ),
              ),

              const SizedBox(height: AppSpacing.l),

              // ── Compte & sécurité ────────────────────────────────
              _SectionLabel(l.profile_section_security),
              const SizedBox(height: AppSpacing.s),
              AppCard(
                variant: AppCardVariant.glass,
                padding: EdgeInsets.zero,
                child: Column(
                  children: [
                    _Tile(
                      icon: Icons.person_outline_rounded,
                      tint: PaColors.tealLight,
                      label: l.profile_tile_info,
                      subtitle: l.profile_tile_info_sub,
                      onTap: () => _MyInfoSheet.show(
                        context,
                        prenom: member?.prenom ?? '',
                        nom: member?.nom ?? '',
                        email: member?.email ?? '',
                        phone: member?.phone ?? '',
                      ),
                    ),
                    const _TileDivider(),
                    _Tile(
                      icon: Icons.lock_outline_rounded,
                      tint: PaColors.success,
                      label: l.profile_tile_password,
                      subtitle: l.profile_tile_password_sub,
                      onTap: () => _PasswordSheet.show(context),
                    ),
                    const _TileDivider(),
                    _Tile(
                      icon: Icons.pin_outlined,
                      tint: PaColors.blue,
                      label: l.profile_tile_pin,
                      subtitle: l.profile_tile_pin_sub,
                      onTap: () => context.push('/pin/change'),
                    ),
                    const _BiometricTile(),
                    const _TileDivider(),
                    _Tile(
                      icon: Icons.notifications_none_rounded,
                      tint: PaColors.warning,
                      label: l.profile_tile_notifications,
                      subtitle: l.profile_tile_notifications_sub,
                      onTap: () => context.push('/preferences/notifications'),
                    ),
                  ],
                ),
              ),

              const SizedBox(height: AppSpacing.l),

              // ── Préférences (Thème + Langue + Aide) ──────────────
              _SectionLabel(l.profile_section_preferences),
              const SizedBox(height: AppSpacing.s),
              AppCard(
                variant: AppCardVariant.glass,
                padding: EdgeInsets.zero,
                child: Column(
                  children: [
                    _Tile(
                      icon: Icons.language_outlined,
                      tint: PaColors.success,
                      label: l.profile_tile_language,
                      subtitle: l.profile_tile_language_sub,
                      trailing: languageLabel,
                      onTap: () => LanguageChoiceSheet.show(context),
                    ),
                    const _TileDivider(),
                    _Tile(
                      icon: Icons.help_outline_rounded,
                      tint: PaColors.warning,
                      label: l.profile_tile_help,
                      subtitle: l.profile_tile_help_sub,
                      onTap: () => context.push('/help'),
                    ),
                  ],
                ),
              ),

              const SizedBox(height: AppSpacing.l),

              // ── Déconnexion . surface neutre, accent danger soft ──
              AppCard(
                variant: AppCardVariant.glass,
                padding: EdgeInsets.zero,
                onTap: () => _confirmLogout(context, ref),
                child: Row(
                  children: [
                    const SizedBox(width: AppSpacing.l),
                    Container(
                      width: 36,
                      height: 36,
                      margin: const EdgeInsets.symmetric(vertical: 12),
                      decoration: const BoxDecoration(
                        color: PaColors.dangerSurface,
                        borderRadius: BorderRadius.all(AppRadii.r12),
                      ),
                      child: const Icon(
                        Icons.logout_rounded,
                        size: 18,
                        color: PaColors.danger,
                      ),
                    ),
                    const SizedBox(width: 14),
                    Expanded(
                      child: Padding(
                        padding: const EdgeInsets.symmetric(vertical: 18),
                        child: Text(
                          l.profile_logout,
                          style: const TextStyle(
                            color: PaColors.danger,
                            fontWeight: FontWeight.w600,
                            fontSize: 15,
                          ),
                        ),
                      ),
                    ),
                    const Padding(
                      padding: EdgeInsets.only(right: AppSpacing.l),
                      child: Icon(
                        Icons.chevron_right_rounded,
                        color: PaColors.inkFaint,
                        size: 22,
                      ),
                    ),
                  ],
                ),
              ),

              const SizedBox(height: AppSpacing.xxl),

              // Footer marque
              const Center(
                child: Opacity(
                  opacity: 0.55,
                  child: Column(
                    children: [
                      LogoMark(size: LogoSize.small),
                      SizedBox(height: 6),
                      Text(
                        'v0.1.0 · MVP',
                        style: TextStyle(
                          color: PaColors.inkMuted,
                          fontSize: 11,
                          letterSpacing: 1.2,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
                ],
              ),
            ),
          ],
        ),
      ),
      ),
    );
  }

  static String _initials(String? prenom, String? nom) {
    final p = (prenom ?? '').trim();
    final n = (nom ?? '').trim();
    final a = p.isNotEmpty ? p[0] : '';
    final b = n.isNotEmpty ? n[0] : '';
    final initials = (a + b).toUpperCase();
    return initials.isEmpty ? 'GF' : initials;
  }

  static Future<void> _confirmLogout(BuildContext context, WidgetRef ref) async {
    unawaited(HapticFeedback.lightImpact());
    final ok = await showModalBottomSheet<bool>(
      context: context,
      backgroundColor: PaColors.paper,
      shape: const RoundedRectangleBorder(borderRadius: AppRadii.sheet),
      builder: (ctx) => SafeArea(
        top: false,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(20, 18, 20, 24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(
                width: 36,
                height: 4,
                decoration: BoxDecoration(
                  color: PaColors.line,
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
              const SizedBox(height: AppSpacing.l),
              Text(
                AppL10n.of(ctx).prof_logout_q,
                style: AppTypography.headingMedium,
              ),
              const SizedBox(height: 6),
              Text(
                AppL10n.of(ctx).prof_logout_body,
                textAlign: TextAlign.center,
                style: AppTypography.bodyMedium.copyWith(
                  color: PaColors.inkSecondary,
                ),
              ),
              const SizedBox(height: AppSpacing.xl),
              SizedBox(
                width: double.infinity,
                child: FilledButton.tonal(
                  style: FilledButton.styleFrom(
                    backgroundColor: PaColors.dangerSurface,
                    foregroundColor: PaColors.danger,
                    minimumSize: const Size(0, 52),
                    shape: const RoundedRectangleBorder(borderRadius: AppRadii.button),
                  ),
                  onPressed: () => Navigator.of(ctx).pop(true),
                  child: Text(AppL10n.of(ctx).prof_logout_confirm),
                ),
              ),
              const SizedBox(height: 8),
              SizedBox(
                width: double.infinity,
                child: TextButton(
                  onPressed: () => Navigator.of(ctx).pop(false),
                  child: Text(AppL10n.of(ctx).common_cancel),
                ),
              ),
            ],
          ),
        ),
      ),
    );
    if (ok == true) {
      await ref.read(authProvider.notifier).signOut();
      if (!context.mounted) return;
      context.go('/login');
    }
  }
}


/// Petit label de section au-dessus d'un groupe de tiles.
class _SectionLabel extends StatelessWidget {
  const _SectionLabel(this.label);
  final String label;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(left: 4),
      child: Text(
        label.toUpperCase(),
        style: AppTypography.eyebrow.copyWith(
          color: PaColors.inkMuted,
          letterSpacing: 1.4,
          fontSize: 11,
        ),
      ),
    );
  }
}


/// Séparateur fin entre 2 tiles dans une AppCard glass.
class _TileDivider extends StatelessWidget {
  const _TileDivider();

  @override
  Widget build(BuildContext context) {
    return const Padding(
      padding: EdgeInsets.only(left: 66),
      child: Divider(height: 1, color: PaColors.line),
    );
  }
}


/// Tile moderne avec icône colorée (squircle tinted), libellé,
/// sous-titre optionnel et valeur trailing optionnelle.
class _Tile extends StatelessWidget {
  const _Tile({
    required this.icon,
    required this.tint,
    required this.label,
    required this.onTap,
    this.subtitle,
    this.trailing,
  });

  final IconData icon;
  final Color tint;
  final String label;
  final String? subtitle;
  final String? trailing;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      child: Padding(
        padding: const EdgeInsets.symmetric(
          horizontal: AppSpacing.l,
          vertical: 14,
        ),
        child: Row(
          children: [
            Container(
              width: 36,
              height: 36,
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                  colors: [
                    tint.withValues(alpha: 0.18),
                    tint.withValues(alpha: 0.08),
                  ],
                ),
                borderRadius: const BorderRadius.all(AppRadii.r12),
              ),
              child: Icon(icon, size: 18, color: tint),
            ),
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(label, style: AppTypography.labelLarge),
                  if (subtitle != null) ...[
                    const SizedBox(height: 2),
                    Text(
                      subtitle!,
                      style: AppTypography.bodySmall.copyWith(
                        color: PaColors.inkMuted,
                        fontSize: 12,
                      ),
                    ),
                  ],
                ],
              ),
            ),
            if (trailing != null)
              Padding(
                padding: const EdgeInsets.only(right: 6),
                child: Text(
                  trailing!,
                  style: AppTypography.labelMedium.copyWith(
                    color: PaColors.inkSecondary,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ),
            const Icon(
              Icons.chevron_right_rounded,
              color: PaColors.inkFaint,
              size: 22,
            ),
          ],
        ),
      ),
    );
  }
}


/// Ligne « Déverrouillage par empreinte » avec interrupteur.
///
/// Masquée si le device n'a pas de capteur biométrique exploitable. L'activation
/// déclenche un prompt empreinte de confirmation (cf. [PinNotifier]).
class _BiometricTile extends ConsumerWidget {
  const _BiometricTile();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = AppL10n.of(context);
    final st = ref.watch(pinProvider).valueOrNull;
    if (st == null || !st.biometricAvailable) return const SizedBox.shrink();

    Future<void> toggle(bool v) async {
      final ok = await ref.read(pinProvider.notifier).setBiometricEnabled(
            v,
            labels: BiometricLabels(
              reason: l.biometric_reason_enable,
              signInTitle: l.biometric_signin_title,
              hint: l.biometric_hint,
              cancelButton: l.biometric_cancel_button,
            ),
          );
      if (!context.mounted) return;
      if (!ok && v) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(l.biometric_cancelled)),
        );
      }
    }

    return Column(
      children: [
        const _TileDivider(),
        Padding(
          padding: const EdgeInsets.symmetric(
            horizontal: AppSpacing.l,
            vertical: 8,
          ),
          child: Row(
            children: [
              Container(
                width: 36,
                height: 36,
                decoration: BoxDecoration(
                  gradient: LinearGradient(
                    begin: Alignment.topLeft,
                    end: Alignment.bottomRight,
                    colors: [
                      PaColors.teal.withValues(alpha: 0.18),
                      PaColors.teal.withValues(alpha: 0.08),
                    ],
                  ),
                  borderRadius: const BorderRadius.all(AppRadii.r12),
                ),
                child: const Icon(Icons.fingerprint_rounded,
                    size: 18, color: PaColors.teal,),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(l.profile_tile_biometric,
                        style: AppTypography.labelLarge,),
                    const SizedBox(height: 2),
                    Text(
                      l.profile_tile_biometric_sub,
                      style: AppTypography.bodySmall.copyWith(
                        color: PaColors.inkMuted,
                        fontSize: 12,
                      ),
                    ),
                  ],
                ),
              ),
              Switch.adaptive(
                value: st.biometricEnabled,
                activeTrackColor: PaColors.teal,
                onChanged: toggle,
              ),
            ],
          ),
        ),
      ],
    );
  }
}


/// Hero identité . surface gradient cobalt avec halo blanc, avatar
/// circulaire surdimensionné et badge membre glow. Premier contact
/// visuel de la page Profil.
class _IdentityHero extends StatelessWidget {
  const _IdentityHero({
    required this.fullName,
    required this.email,
    required this.memberNumber,
    required this.initials,
  });

  final String fullName;
  final String email;
  final String memberNumber;
  final String initials;

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        gradient: PaGradients.heroAurore,
        borderRadius: BorderRadius.circular(18),
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(18),
        child: Stack(
        children: [
          // Halo lumineux top-right pour la profondeur premium
          Positioned(
            top: -50,
            right: -40,
            child: IgnorePointer(
              child: Container(
                width: 200,
                height: 200,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  gradient: RadialGradient(
                    colors: [
                      Colors.white.withValues(alpha: 0.18),
                      Colors.white.withValues(alpha: 0),
                    ],
                  ),
                ),
              ),
            ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(22, 22, 22, 20),
            child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  // Avatar . anneau dégradé + initiales
                  Container(
                    width: 68,
                    height: 68,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      gradient: LinearGradient(
                        begin: Alignment.topLeft,
                        end: Alignment.bottomRight,
                        colors: [
                          Colors.white.withValues(alpha: 0.26),
                          Colors.white.withValues(alpha: 0.08),
                        ],
                      ),
                      border: Border.all(
                        color: Colors.white.withValues(alpha: 0.32),
                        width: 1.6,
                      ),
                    ),
                    alignment: Alignment.center,
                    child: Text(
                      initials,
                      style: AppTypography.headingMedium.copyWith(
                        color: Colors.white,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ),
                  const SizedBox(width: AppSpacing.m),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          fullName,
                          style: AppTypography.headingMedium.copyWith(
                            color: Colors.white,
                          ),
                        ),
                        const SizedBox(height: 2),
                        Text(
                          email,
                          style: AppTypography.bodySmall.copyWith(
                            color: Colors.white.withValues(alpha: 0.78),
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
              const SizedBox(height: AppSpacing.l),
              // Badge membre . glow soft
              Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 12,
                  vertical: 7,
                ),
                decoration: BoxDecoration(
                  color: Colors.white.withValues(alpha: 0.14),
                  borderRadius: BorderRadius.circular(999),
                  border: Border.all(
                    color: Colors.white.withValues(alpha: 0.24),
                  ),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Icon(
                      Icons.workspace_premium_outlined,
                      size: 14,
                      color: Color(0xFFFFE4A8),
                    ),
                    const SizedBox(width: 6),
                    Text(
                      AppL10n.of(context).prof_member_num(memberNumber),
                      style: AppTypography.monoSmall.copyWith(
                        color: Colors.white,
                        fontWeight: FontWeight.w700,
                        letterSpacing: 0.3,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
        ],
        ),
      ),
    );
  }
}


// ---------------------------------------------------------------------------
// Modale « Mes informations » . édition prénom/nom/téléphone (email read-only).
// ---------------------------------------------------------------------------

class _MyInfoSheet extends ConsumerStatefulWidget {
  const _MyInfoSheet({
    required this.prenom,
    required this.nom,
    required this.email,
    required this.phone,
  });

  final String prenom;
  final String nom;
  final String email;
  final String phone;

  static Future<void> show(
    BuildContext context, {
    required String prenom,
    required String nom,
    required String email,
    required String phone,
  }) {
    return showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      constraints: BoxConstraints(
        maxHeight: MediaQuery.sizeOf(context).height * 0.9,
      ),
      backgroundColor: PaColors.paper,
      barrierColor: PaColors.navy.withValues(alpha: 0.5),
      shape: const RoundedRectangleBorder(borderRadius: AppRadii.sheet),
      builder: (_) => _MyInfoSheet(
        prenom: prenom,
        nom: nom,
        email: email,
        phone: phone,
      ),
    );
  }

  @override
  ConsumerState<_MyInfoSheet> createState() => _MyInfoSheetState();
}

class _MyInfoSheetState extends ConsumerState<_MyInfoSheet> {
  late final TextEditingController _prenomCtrl;
  late final TextEditingController _nomCtrl;
  late final TextEditingController _phoneCtrl;
  final _formKey = GlobalKey<FormState>();
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    _prenomCtrl = TextEditingController(text: widget.prenom);
    _nomCtrl = TextEditingController(text: widget.nom);
    _phoneCtrl = TextEditingController(text: widget.phone);
  }

  @override
  void dispose() {
    _prenomCtrl.dispose();
    _nomCtrl.dispose();
    _phoneCtrl.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    if (!_formKey.currentState!.validate()) return;
    unawaited(HapticFeedback.lightImpact());
    setState(() => _saving = true);
    await ref.read(authProvider.notifier).updateProfile(
          prenom: _prenomCtrl.text,
          nom: _nomCtrl.text,
          phone: _phoneCtrl.text,
        );
    if (!mounted) return;
    setState(() => _saving = false);
    Navigator.of(context).pop();
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(AppL10n.of(context).myinfo_saved)),
    );
  }

  @override
  Widget build(BuildContext context) {
    final l = AppL10n.of(context);
    return Padding(
      padding: EdgeInsets.only(
        bottom: MediaQuery.viewInsetsOf(context).bottom,
      ),
      child: SafeArea(
        top: false,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(20, 8, 20, 24),
          child: Form(
            key: _formKey,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const _Grabber(),
                const SizedBox(height: AppSpacing.l),
                Text(l.myinfo_title, style: AppTypography.headingMedium),
                const SizedBox(height: 4),
                Text(
                  l.myinfo_sub,
                  style: AppTypography.bodyMedium.copyWith(
                    color: PaColors.inkSecondary,
                  ),
                ),
                const SizedBox(height: AppSpacing.xl),

                Text(l.common_firstname, style: AppTypography.labelMedium),
                const SizedBox(height: 6),
                TextFormField(
                  controller: _prenomCtrl,
                  enabled: !_saving,
                  style: AppTypography.bodyLarge,
                  decoration: InputDecoration(hintText: l.common_firstname),
                  validator: (v) =>
                      (v ?? '').trim().isEmpty ? l.myinfo_firstname_required : null,
                ),
                const SizedBox(height: AppSpacing.m),

                Text(l.common_lastname, style: AppTypography.labelMedium),
                const SizedBox(height: 6),
                TextFormField(
                  controller: _nomCtrl,
                  enabled: !_saving,
                  style: AppTypography.bodyLarge,
                  decoration: InputDecoration(hintText: l.common_lastname),
                  validator: (v) =>
                      (v ?? '').trim().isEmpty ? l.myinfo_lastname_required : null,
                ),
                const SizedBox(height: AppSpacing.m),

                Text(l.common_phone, style: AppTypography.labelMedium),
                const SizedBox(height: 6),
                TextFormField(
                  controller: _phoneCtrl,
                  enabled: !_saving,
                  keyboardType: TextInputType.phone,
                  style: AppTypography.bodyLarge,
                  decoration: const InputDecoration(
                    hintText: '+237 6XX XX XX XX',
                  ),
                  validator: (v) {
                    final digits =
                        (v ?? '').replaceAll(RegExp(r'\D'), '');
                    if (digits.length < 8) return l.err_number_incomplete;
                    return null;
                  },
                ),
                const SizedBox(height: AppSpacing.m),

                // Email read-only . pour changer, passer par le support
                Text(l.common_email, style: AppTypography.labelMedium),
                const SizedBox(height: 6),
                Container(
                  padding: const EdgeInsets.symmetric(
                      horizontal: 16, vertical: 14,),
                  decoration: BoxDecoration(
                    color: PaColors.appBg,
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: PaColors.line),
                  ),
                  child: Row(
                    children: [
                      Expanded(
                        child: Text(
                          widget.email,
                          style: AppTypography.bodyLarge.copyWith(
                            color: PaColors.inkSecondary,
                          ),
                        ),
                      ),
                      const Icon(Icons.lock_outline_rounded,
                          size: 16, color: PaColors.inkMuted,),
                    ],
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  l.myinfo_email_locked,
                  style: AppTypography.bodySmall.copyWith(
                    color: PaColors.inkMuted,
                  ),
                ),

                const SizedBox(height: AppSpacing.xl),

                PaButton(
                  label: l.common_save,
                  loading: _saving,
                  onPressed: _saving ? null : _save,
                ),
                const SizedBox(height: 6),
                SizedBox(
                  width: double.infinity,
                  child: TextButton(
                    onPressed:
                        _saving ? null : () => Navigator.of(context).pop(),
                    child: Text(l.common_cancel),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}


// ---------------------------------------------------------------------------
// Modale Mot de passe . formulaire à 3 champs avec validation et appel
// authNotifier.changePassword. Affiche un état succès en fin.
// ---------------------------------------------------------------------------

class _PasswordSheet extends ConsumerStatefulWidget {
  const _PasswordSheet();

  static Future<void> show(BuildContext context) {
    return showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      constraints: BoxConstraints(
        maxHeight: MediaQuery.sizeOf(context).height * 0.9,
      ),
      backgroundColor: PaColors.paper,
      barrierColor: PaColors.navy.withValues(alpha: 0.5),
      shape: const RoundedRectangleBorder(borderRadius: AppRadii.sheet),
      builder: (_) => const _PasswordSheet(),
    );
  }

  @override
  ConsumerState<_PasswordSheet> createState() => _PasswordSheetState();
}

class _PasswordSheetState extends ConsumerState<_PasswordSheet>
    with TickerProviderStateMixin {
  final _formKey = GlobalKey<FormState>();
  final _oldCtrl = TextEditingController();
  final _newCtrl = TextEditingController();
  final _confirmCtrl = TextEditingController();
  bool _hideOld = true;
  bool _hideNew = true;
  bool _saving = false;
  bool _success = false;
  String? _serverError;
  late final AnimationController _checkCtrl;

  @override
  void initState() {
    super.initState();
    _checkCtrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 600),
    );
  }

  @override
  void dispose() {
    _oldCtrl.dispose();
    _newCtrl.dispose();
    _confirmCtrl.dispose();
    _checkCtrl.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    if (!_formKey.currentState!.validate()) return;
    unawaited(HapticFeedback.lightImpact());
    setState(() {
      _saving = true;
      _serverError = null;
    });
    final err = await ref.read(authProvider.notifier).changePassword(
          oldPassword: _oldCtrl.text,
          newPassword: _newCtrl.text,
        );
    if (!mounted) return;
    if (err != null) {
      setState(() {
        _saving = false;
        _serverError = err;
      });
      unawaited(HapticFeedback.heavyImpact());
      return;
    }
    unawaited(HapticFeedback.heavyImpact());
    setState(() {
      _saving = false;
      _success = true;
    });
    unawaited(_checkCtrl.forward());
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.only(
        bottom: MediaQuery.viewInsetsOf(context).bottom,
      ),
      child: SafeArea(
        top: false,
        child: AnimatedSize(
          duration: const Duration(milliseconds: 280),
          curve: Curves.easeOutCubic,
          alignment: Alignment.topCenter,
          child: _success ? _successView() : _formView(),
        ),
      ),
    );
  }

  Widget _formView() {
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
            Text(l.pwd_title, style: AppTypography.headingMedium),
            const SizedBox(height: 4),
            Text(
              l.pwd_sub,
              style: AppTypography.bodyMedium.copyWith(
                color: PaColors.inkSecondary,
              ),
            ),
            const SizedBox(height: AppSpacing.xl),

            Text(l.pwd_old, style: AppTypography.labelMedium),
            const SizedBox(height: 6),
            TextFormField(
              controller: _oldCtrl,
              enabled: !_saving,
              obscureText: _hideOld,
              style: AppTypography.bodyLarge,
              decoration: InputDecoration(
                hintText: '••••••••',
                suffixIcon: IconButton(
                  icon: Icon(_hideOld
                      ? Icons.visibility_outlined
                      : Icons.visibility_off_outlined,),
                  color: PaColors.inkMuted,
                  onPressed: () => setState(() => _hideOld = !_hideOld),
                ),
              ),
              validator: (v) =>
                  (v ?? '').isEmpty ? l.pwd_old_required : null,
            ),
            const SizedBox(height: AppSpacing.m),

            Text(l.pwd_new, style: AppTypography.labelMedium),
            const SizedBox(height: 6),
            TextFormField(
              controller: _newCtrl,
              enabled: !_saving,
              obscureText: _hideNew,
              style: AppTypography.bodyLarge,
              decoration: InputDecoration(
                hintText: l.pwd_min_hint,
                suffixIcon: IconButton(
                  icon: Icon(_hideNew
                      ? Icons.visibility_outlined
                      : Icons.visibility_off_outlined,),
                  color: PaColors.inkMuted,
                  onPressed: () => setState(() => _hideNew = !_hideNew),
                ),
              ),
              validator: (v) {
                final t = v ?? '';
                if (t.length < 8) return l.pwd_min_err;
                if (t == _oldCtrl.text) return l.pwd_diff_err;
                return null;
              },
            ),
            const SizedBox(height: AppSpacing.m),

            Text(l.pwd_confirm, style: AppTypography.labelMedium),
            const SizedBox(height: 6),
            TextFormField(
              controller: _confirmCtrl,
              enabled: !_saving,
              obscureText: _hideNew,
              style: AppTypography.bodyLarge,
              decoration: InputDecoration(
                hintText: l.pwd_confirm_hint,
              ),
              validator: (v) =>
                  v != _newCtrl.text ? l.pwd_mismatch : null,
            ),

            if (_serverError != null) ...[
              const SizedBox(height: AppSpacing.m),
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: PaColors.dangerSurface,
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Row(
                  children: [
                    const Icon(Icons.error_outline,
                        color: PaColors.danger, size: 18,),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        _serverError!,
                        style: AppTypography.bodySmall.copyWith(
                          color: PaColors.danger,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ],

            const SizedBox(height: AppSpacing.xl),
            PaButton(
              label: l.common_modify,
              loading: _saving,
              onPressed: _saving ? null : _save,
            ),
            const SizedBox(height: 6),
            SizedBox(
              width: double.infinity,
              child: TextButton(
                onPressed: _saving ? null : () => Navigator.of(context).pop(),
                child: Text(l.common_cancel),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _successView() {
    final l = AppL10n.of(context);
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 8, 20, 28),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const _Grabber(),
          const SizedBox(height: 28),
          ScaleTransition(
            scale: CurvedAnimation(parent: _checkCtrl, curve: Curves.elasticOut),
            child: Container(
              width: 72,
              height: 72,
              decoration: BoxDecoration(
                color: PaColors.success.withValues(alpha: 0.14),
                shape: BoxShape.circle,
              ),
              child: const Icon(Icons.check_rounded,
                  color: PaColors.success, size: 36,),
            ),
          ),
          const SizedBox(height: 18),
          Text(l.pwd_done_title, style: AppTypography.headingMedium),
          const SizedBox(height: 6),
          Text(
            l.pwd_done_body,
            textAlign: TextAlign.center,
            style: AppTypography.bodyMedium.copyWith(color: PaColors.inkSecondary),
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
          color: PaColors.line,
          borderRadius: BorderRadius.circular(2),
        ),
      ),
    );
  }
}
