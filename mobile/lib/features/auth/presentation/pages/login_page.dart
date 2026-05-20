import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../../app/theme/app_radii.dart';
import '../../../../app/theme/app_spacing.dart';
import '../../../../app/theme/app_typography.dart';
import '../../../../app/theme/paysika/pa_colors.dart';
import '../../../../core/widgets/brand_loader.dart';
import '../../../../core/widgets/eyebrow.dart';
import '../../../../core/widgets/logo_mark.dart';
import '../../../../l10n/gen/app_localizations.dart';
import '../state/auth_notifier.dart';
import '../widgets/membership_form_sheet.dart';
import '../widgets/member_info_sheet.dart';

class LoginPage extends ConsumerStatefulWidget {
  const LoginPage({super.key});

  @override
  ConsumerState<LoginPage> createState() => _LoginPageState();
}

class _LoginPageState extends ConsumerState<LoginPage> {
  final _formKey = GlobalKey<FormState>();
  final _emailCtrl = TextEditingController(text: 'jean.kamga@test.local');
  final _passCtrl = TextEditingController(text: 'test1234');
  bool _obscure = true;

  @override
  void dispose() {
    _emailCtrl.dispose();
    _passCtrl.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    HapticFeedback.lightImpact();
    await ref.read(authProvider.notifier).signIn(
          email: _emailCtrl.text.trim(),
          password: _passCtrl.text,
        );
    // Le redirect du router peut disposer cette page pendant l'await :
    // on vérifie `mounted` AVANT de retoucher `ref`.
    if (!mounted) return;
    final state = ref.read(authProvider);
    state.whenOrNull(
      data: (member) {
        if (member != null) context.go('/home');
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    final auth = ref.watch(authProvider);
    final loading = auth.isLoading;
    final l = AppL10n.of(context);
    final scheme = Theme.of(context).colorScheme;

    // Affiche un SnackBar discret en cas d'erreur
    ref.listen<AsyncValue<dynamic>>(authProvider, (prev, next) {
      next.whenOrNull(
        error: (err, _) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text(err.toString())),
          );
        },
      );
    });

    return Scaffold(
      backgroundColor: PaColors.appBg,
      body: ColoredBox(
        color: PaColors.appBg,
        child: SafeArea(
          child: GestureDetector(
            onTap: () => FocusScope.of(context).unfocus(),
            behavior: HitTestBehavior.opaque,
            child: SingleChildScrollView(
              padding: const EdgeInsets.fromLTRB(
                AppSpacing.screenH,
                AppSpacing.l,
                AppSpacing.screenH,
                AppSpacing.xxxl,
              ),
              child: Form(
                key: _formKey,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // Header avec logo
                    Row(
                      children: [
                        const LogoBadge(size: LogoSize.medium),
                        const SizedBox(width: AppSpacing.m),
                        Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Eyebrow(l.home_eyebrow),
                            const SizedBox(height: 2),
                            Text(
                              l.appTitle,
                              style: AppTypography.headingSmall
                                  .copyWith(color: scheme.onSurface),
                            ),
                          ],
                        ),
                      ],
                    ),

                    const SizedBox(height: AppSpacing.huge),

                    // Title
                    Text(
                      l.login_title,
                      style: AppTypography.displayLarge
                          .copyWith(color: scheme.onSurface),
                    ),
                    const SizedBox(height: AppSpacing.s),
                    Text(
                      l.login_subtitle,
                      style: AppTypography.bodyLarge.copyWith(
                        color: scheme.onSurface.withValues(alpha: 0.7),
                        height: 1.45,
                      ),
                    ),

                    const SizedBox(height: AppSpacing.xxxl),

                    // Email
                    _Field(
                      controller: _emailCtrl,
                      label: l.login_email_label,
                      hint: l.login_email_hint,
                      keyboardType: TextInputType.emailAddress,
                      autofillHints: const [AutofillHints.email],
                      icon: Icons.mail_outline_rounded,
                      enabled: !loading,
                      validator: (v) {
                        final t = (v ?? '').trim();
                        if (t.isEmpty) return l.login_email_required;
                        if (!t.contains('@')) return l.login_email_invalid;
                        return null;
                      },
                    ),
                    const SizedBox(height: AppSpacing.m),

                    // Password
                    _Field(
                      controller: _passCtrl,
                      label: l.login_password_label,
                      hint: '•••••••••',
                      icon: Icons.lock_outline_rounded,
                      obscureText: _obscure,
                      autofillHints: const [AutofillHints.password],
                      enabled: !loading,
                      onSubmitted: (_) => _submit(),
                      trailing: IconButton(
                        tooltip: _obscure
                            ? l.login_show_password
                            : l.login_hide_password,
                        icon: Icon(
                          _obscure
                              ? Icons.visibility_outlined
                              : Icons.visibility_off_outlined,
                          color: scheme.onSurface.withValues(alpha: 0.5),
                          size: 20,
                        ),
                        onPressed: () => setState(() => _obscure = !_obscure),
                      ),
                      validator: (v) {
                        if ((v ?? '').isEmpty) return l.login_password_required;
                        return null;
                      },
                    ),

                    // Mot de passe oublié
                    Align(
                      alignment: Alignment.centerRight,
                      child: TextButton(
                        onPressed: loading ? null : () {},
                        style: TextButton.styleFrom(
                          padding: const EdgeInsets.symmetric(
                              horizontal: 4, vertical: 4),
                          minimumSize: Size.zero,
                          tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                        ),
                        child: Text(l.login_forgot_password),
                      ),
                    ),

                    const SizedBox(height: AppSpacing.xl),

                    // CTA principal
                    SizedBox(
                      width: double.infinity,
                      child: FilledButton(
                        onPressed: loading ? null : _submit,
                        child: loading
                            ? const Row(
                                mainAxisAlignment: MainAxisAlignment.center,
                                children: [
                                  SizedBox(
                                    width: 20,
                                    height: 20,
                                    child: BrandPulseDots(
                                      size: 5,
                                      color: Colors.white,
                                    ),
                                  ),
                                ],
                              )
                            : Text(l.login_submit),
                      ),
                    ),

                    const SizedBox(height: AppSpacing.l),

                    // Divider with text
                    Row(
                      children: [
                        Expanded(child: Divider(color: scheme.outline)),
                        const SizedBox(width: AppSpacing.s),
                        Text(
                          l.common_or,
                          style: TextStyle(
                            color: scheme.onSurface.withValues(alpha: 0.5),
                            fontSize: 12,
                            letterSpacing: 1.5,
                          ),
                        ),
                        const SizedBox(width: AppSpacing.s),
                        Expanded(child: Divider(color: scheme.outline)),
                      ],
                    ),

                    const SizedBox(height: AppSpacing.l),

                    // Secondary CTA — ouvre la modale d'explication + flow
                    SizedBox(
                      width: double.infinity,
                      child: OutlinedButton(
                        onPressed: loading
                            ? null
                            : () => MemberInfoSheet.show(
                                  context,
                                  onJoin: () =>
                                      MembershipFormSheet.show(context),
                                ),
                        child: Text(l.login_become_member),
                      ),
                    ),

                    const SizedBox(height: AppSpacing.xxl),

                    // Tip — fond cobalt soft, dark-aware
                    Container(
                      padding: const EdgeInsets.all(AppSpacing.l),
                      decoration: BoxDecoration(
                        color: scheme.surfaceContainerHighest,
                        borderRadius: AppRadii.card,
                        border: Border.all(
                          color: scheme.primary.withValues(alpha: 0.10),
                        ),
                      ),
                      child: Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Icon(
                            Icons.shield_outlined,
                            size: 18,
                            color: scheme.primary,
                          ),
                          const SizedBox(width: AppSpacing.s),
                          Expanded(
                            child: Text(
                              l.login_security_tip,
                              style: AppTypography.bodySmall.copyWith(
                                color: scheme.onSurface
                                    .withValues(alpha: 0.85),
                                height: 1.5,
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
          ),
        ),
      ),
    );
  }
}


/// Champ de saisie standardisé pour le login — icône à gauche, label flottant,
/// trailing optionnel (toggle visibility du password).
class _Field extends StatelessWidget {
  const _Field({
    required this.controller,
    required this.label,
    required this.icon,
    this.hint,
    this.keyboardType,
    this.obscureText = false,
    this.trailing,
    this.validator,
    this.autofillHints,
    this.onSubmitted,
    this.enabled = true,
  });

  final TextEditingController controller;
  final String label;
  final String? hint;
  final IconData icon;
  final TextInputType? keyboardType;
  final bool obscureText;
  final Widget? trailing;
  final String? Function(String?)? validator;
  final Iterable<String>? autofillHints;
  final void Function(String)? onSubmitted;
  final bool enabled;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return TextFormField(
      controller: controller,
      keyboardType: keyboardType,
      obscureText: obscureText,
      enabled: enabled,
      autofillHints: autofillHints,
      onFieldSubmitted: onSubmitted,
      validator: validator,
      style: AppTypography.bodyLarge.copyWith(color: scheme.onSurface),
      decoration: InputDecoration(
        labelText: label,
        hintText: hint,
        prefixIcon: Padding(
          padding: const EdgeInsets.only(left: 14, right: 8),
          child: Icon(
            icon,
            size: 20,
            color: scheme.onSurface.withValues(alpha: 0.65),
          ),
        ),
        prefixIconConstraints: const BoxConstraints(minWidth: 0, minHeight: 0),
        suffixIcon: trailing,
      ),
    );
  }
}
