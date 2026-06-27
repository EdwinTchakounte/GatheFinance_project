import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../../app/theme/paysika/pa_colors.dart';
import '../../../../app/theme/paysika/pa_typography.dart';
import '../../../../core/widgets/paysika/pa_brand_hero.dart';
import '../../../../core/widgets/paysika/pa_pattern_background.dart';
import '../../../../l10n/gen/app_localizations.dart';
import '../state/auth_notifier.dart';
import '../widgets/membership_form_sheet.dart';
import '../widgets/member_info_sheet.dart';

/// Page de connexion . refonte **stricte** d'après `capture_rh.jpeg`
/// (2026-06-18 itération 3, ref user) :
///
/// - **Hero bleu gradient** pleine largeur + coins bas arrondis (vague).
/// - Cercle blanc contenant le logo Gathe, centré dans le hero.
/// - Titre + baseline en blanc.
/// - **Zone crème doodle** dessous avec : titre "Connexion à votre espace"
///   + sub + card blanche aérée (labels w600 + inputs).
/// - **CTA bleu gradient** avec icône flèche et "Se connecter".
/// - 2 pills sous le CTA : "Mot de passe oublié" + "Devenir membre".
/// - Footer faint "Gathe Finance · coopérative".
class LoginPage extends ConsumerStatefulWidget {
  const LoginPage({super.key});

  @override
  ConsumerState<LoginPage> createState() => _LoginPageState();
}

class _LoginPageState extends ConsumerState<LoginPage> {
  final _formKey = GlobalKey<FormState>();
  final _emailCtrl = TextEditingController();
  final _passCtrl = TextEditingController();
  bool _obscure = true;
  bool _submitting = false;

  @override
  void dispose() {
    _emailCtrl.dispose();
    _passCtrl.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    debugPrint('[LOGIN] _submit tapped . email="${_emailCtrl.text.trim()}" pwd_len=${_passCtrl.text.length}');
    if (!_formKey.currentState!.validate()) {
      debugPrint('[LOGIN] validation FAILED');
      return;
    }
    setState(() => _submitting = true);
    try {
      unawaited(HapticFeedback.lightImpact());
    } catch (_) {
      // Vibrate permission absente sur certains devices (Tecno) . non-bloquant.
    }
    try {
      await ref.read(authProvider.notifier).signIn(
            email: _emailCtrl.text.trim(),
            password: _passCtrl.text,
          );
    } catch (e, st) {
      debugPrint('[LOGIN] signIn threw: $e');
      debugPrint('$st');
    }
    if (!mounted) return;
    setState(() => _submitting = false);
    final state = ref.read(authProvider);
    debugPrint('[LOGIN] post-signIn state: $state');
    state.whenOrNull(
      data: (member) {
        if (member != null) {
          context.go('/home');
        } else {
          // signIn() a réussi côté HTTP mais le payload n'a pas de Member.
          // Le serveur a renvoyé un compte staff/sans profil membre.
          _showErrorToast(context, 'Ce compte n\'a pas de profil membre.');
        }
      },
    );
  }

  /// Toast d'erreur . rouge, icône warning, durée 4 s, dismissible.
  /// Mappe les messages techniques (NetworkException, CredentialsException…)
  /// vers des chaînes lisibles pour l'utilisateur final.
  void _showErrorToast(BuildContext context, Object err) {
    final messenger = ScaffoldMessenger.of(context);
    messenger.clearSnackBars();
    final raw = err.toString();
    final human = _humanizeError(raw);
    messenger.showSnackBar(
      SnackBar(
        content: Row(
          children: [
            const Icon(Icons.error_outline_rounded, color: Colors.white, size: 22),
            const SizedBox(width: 12),
            Expanded(
              child: Text(
                human,
                style: const TextStyle(
                  color: Colors.white,
                  fontSize: 14,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ),
          ],
        ),
        backgroundColor: PaColors.danger,
        behavior: SnackBarBehavior.floating,
        margin: const EdgeInsets.fromLTRB(16, 0, 16, 20),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(12),
        ),
        duration: const Duration(seconds: 4),
        action: SnackBarAction(
          label: 'OK',
          textColor: Colors.white,
          onPressed: messenger.hideCurrentSnackBar,
        ),
      ),
    );
  }

  /// Toast de succès . vert, icône check, court (2 s).
  void _showSuccessToast(BuildContext context) {
    final messenger = ScaffoldMessenger.of(context);
    messenger.clearSnackBars();
    messenger.showSnackBar(
      SnackBar(
        content: const Row(
          children: [
            Icon(Icons.check_circle_outline_rounded, color: Colors.white, size: 22),
            SizedBox(width: 12),
            Expanded(
              child: Text(
                'Connexion réussie.',
                style: TextStyle(
                  color: Colors.white,
                  fontSize: 14,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ),
          ],
        ),
        backgroundColor: PaColors.success,
        behavior: SnackBarBehavior.floating,
        margin: const EdgeInsets.fromLTRB(16, 0, 16, 20),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(12),
        ),
        duration: const Duration(seconds: 2),
      ),
    );
  }

  /// Traduit les exceptions internes en messages parlants pour le sociétaire.
  String _humanizeError(Object err) {
    final s = err.toString().toLowerCase();
    if (s.contains('credentials') ||
        s.contains('identifiants invalides') ||
        s.contains('401')) {
      return 'Email ou mot de passe incorrect.';
    }
    if (s.contains('failed host lookup') ||
        s.contains('socket') ||
        s.contains('connection') ||
        s.contains('réseau') ||
        s.contains('network')) {
      return 'Pas de connexion . vérifie ton réseau et réessaie.';
    }
    if (s.contains('timeout') || s.contains('délai')) {
      return 'Le serveur met trop de temps à répondre. Réessaie.';
    }
    if (s.contains('certificat') || s.contains('certificate')) {
      return 'Connexion sécurisée impossible (certificat).';
    }
    if (s.contains('500') || s.contains('serveur')) {
      return 'Erreur serveur. Réessaie dans un instant.';
    }
    // Fallback : afficher le message brut s'il est court, sinon générique.
    final raw = err.toString().replaceFirst('Exception: ', '');
    if (raw.length <= 90) return raw;
    return 'Connexion impossible. Réessaie.';
  }

  @override
  Widget build(BuildContext context) {
    ref.watch(authProvider);
    // Le bouton est désactivé UNIQUEMENT pendant la soumission de l'utilisateur,
    // pas pendant le bootstrap initial du provider (qui peut prendre
    // jusqu'à 25 s sur réseau lent et bloquerait l'UI sinon).
    final loading = _submitting;
    final l = AppL10n.of(context);

    ref.listen<AsyncValue<dynamic>>(authProvider, (prev, next) {
      next.whenOrNull(
        error: (err, _) => _showErrorToast(context, err),
        data: (member) {
          // Connexion réussie ET le provider passe de loading→data avec member.
          if (member != null && (prev?.isLoading ?? false)) {
            _showSuccessToast(context);
          }
        },
      );
    });

    return AnnotatedRegion<SystemUiOverlayStyle>(
      value: const SystemUiOverlayStyle(
        statusBarColor: Colors.transparent,
        statusBarIconBrightness: Brightness.light,
        statusBarBrightness: Brightness.dark,
      ),
      child: Scaffold(
      extendBodyBehindAppBar: true,
      backgroundColor: PaColors.canvas,
      body: PaPatternBackground(
        patternOpacity: 0.34,
        child: GestureDetector(
          onTap: () => FocusScope.of(context).unfocus(),
          behavior: HitTestBehavior.opaque,
          child: SingleChildScrollView(
            child: Form(
              key: _formKey,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  // ── Hero aurore + logo pont qui chevauche la frontière ──
                  Stack(
                    clipBehavior: Clip.none,
                    alignment: Alignment.bottomCenter,
                    children: [
                      PaBrandHero(
                        contentPadding: const EdgeInsets.fromLTRB(20, 16, 20, 64),
                        child: _HeroContent(title: l.appTitle, baseline: l.login_subtitle),
                      ),
                      const Positioned(
                        bottom: -42,
                        child: PaBrandHeroBridgeLogo(size: 84),
                      ),
                    ],
                  ),
                  const SizedBox(height: 60),

                  // ── Titre "Connexion à votre espace" ─────────────────────
                  Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 22),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          l.login_title,
                          style: PaText.display(
                            size: 23,
                            weight: FontWeight.w700,
                            color: PaColors.inkPrimary,
                            letterSpacing: -0.4,
                          ),
                        ),
                        const SizedBox(height: 6),
                        Text(
                          l.login_sub_under_title,
                          style: PaText.body(
                            size: 13.5,
                            color: PaColors.inkSecondary,
                            height: 1.4,
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 18),

                  // ── Card blanche avec form ──────────────────────────────
                  Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 18),
                    child: Container(
                      padding: const EdgeInsets.fromLTRB(18, 22, 18, 22),
                      decoration: BoxDecoration(
                        color: PaColors.paper,
                        borderRadius: BorderRadius.circular(18),
                        boxShadow: [
                          BoxShadow(
                            color: Colors.black.withValues(alpha: 0.06),
                            blurRadius: 24,
                            offset: const Offset(0, 8),
                          ),
                        ],
                      ),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          _Label(l.login_email_label),
                          const SizedBox(height: 8),
                          _BoxField(
                            controller: _emailCtrl,
                            hint: l.login_email_hint,
                            icon: Icons.person_outline_rounded,
                            keyboardType: TextInputType.emailAddress,
                            autofillHints: const [AutofillHints.email],
                            enabled: !loading,
                            validator: (v) {
                              final t = (v ?? '').trim();
                              if (t.isEmpty) return l.login_email_required;
                              if (!t.contains('@')) return l.login_email_invalid;
                              return null;
                            },
                          ),
                          const SizedBox(height: 16),
                          _Label(l.login_password_label),
                          const SizedBox(height: 8),
                          _BoxField(
                            controller: _passCtrl,
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
                                color: PaColors.inkMuted,
                                size: 19,
                              ),
                              onPressed: () =>
                                  setState(() => _obscure = !_obscure),
                            ),
                            validator: (v) {
                              if ((v ?? '').isEmpty) {
                                return l.login_password_required;
                              }
                              return null;
                            },
                          ),
                          const SizedBox(height: 22),
                          // ── CTA bleu gradient pleine largeur ──
                          _BlueCta(
                            label: l.login_submit,
                            loading: loading,
                            onPressed: loading ? null : _submit,
                          ),
                        ],
                      ),
                    ),
                  ),

                  const SizedBox(height: 18),

                  // ── 2 pills sous le CTA . Row + Expanded sur 1 ligne ──
                  Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 18),
                    child: Row(
                      children: [
                        Expanded(
                          child: _Pill(
                            icon: Icons.lock_reset_outlined,
                            label: l.login_forgot_password,
                            onTap: loading
                                ? null
                                : () => context.push('/auth/forgot-password'),
                          ),
                        ),
                        const SizedBox(width: 10),
                        Expanded(
                          child: _Pill(
                            icon: Icons.person_add_alt_1_outlined,
                            label: l.login_become_member,
                            onTap: loading
                                ? null
                                : () => MemberInfoSheet.show(
                                      context,
                                      onJoin: () =>
                                          MembershipFormSheet.show(context),
                                    ),
                          ),
                        ),
                      ],
                    ),
                  ),

                  const SizedBox(height: 22),

                  // ── Footer faint ───────────────────────────────────────
                  Center(
                    child: Text(
                      'Gathe Finance · coopérative',
                      style: PaText.body(
                        size: 11.5,
                        color: PaColors.inkMuted,
                      ),
                    ),
                  ),
                  const SizedBox(height: 24),
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


/// Contenu posé dans le hero . juste titre + baseline. Le logo est posé
/// en chevauchement via PaBrandHeroBridgeLogo, en dehors de ce widget.
class _HeroContent extends StatelessWidget {
  const _HeroContent({required this.title, required this.baseline});
  final String title;
  final String baseline;

  @override
  Widget build(BuildContext context) {
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        const SizedBox(height: 14),
        Text(
          title,
          textAlign: TextAlign.center,
          style: PaText.display(
            size: 28,
            weight: FontWeight.w700,
            color: Colors.white,
            letterSpacing: -0.4,
          ),
        ),
        const SizedBox(height: 6),
        Text(
          baseline,
          textAlign: TextAlign.center,
          style: PaText.body(
            size: 13.5,
            color: Colors.white70,
            height: 1.4,
          ),
        ),
      ],
    );
  }
}


class _Label extends StatelessWidget {
  const _Label(this.text);
  final String text;

  @override
  Widget build(BuildContext context) {
    return Text(
      text,
      style: PaText.label(
        size: 13.5,
        weight: FontWeight.w700,
        color: PaColors.inkPrimary,
      ),
    );
  }
}


/// Input boxé : icône à gauche, hint gris, fond paper, bordure subtile,
/// focus border bleu. Hauteur 52, radius 12.
class _BoxField extends StatefulWidget {
  const _BoxField({
    required this.controller,
    required this.hint,
    required this.icon,
    this.keyboardType,
    this.obscureText = false,
    this.trailing,
    this.validator,
    this.autofillHints,
    this.onSubmitted,
    this.enabled = true,
  });

  final TextEditingController controller;
  final String hint;
  final IconData icon;
  final TextInputType? keyboardType;
  final bool obscureText;
  final Widget? trailing;
  final String? Function(String?)? validator;
  final Iterable<String>? autofillHints;
  final void Function(String)? onSubmitted;
  final bool enabled;

  @override
  State<_BoxField> createState() => _BoxFieldState();
}

class _BoxFieldState extends State<_BoxField> {
  final _focus = FocusNode();
  bool _focused = false;

  @override
  void initState() {
    super.initState();
    _focus.addListener(() {
      if (_focus.hasFocus != _focused) {
        setState(() => _focused = _focus.hasFocus);
      }
    });
  }

  @override
  void dispose() {
    _focus.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return TextFormField(
      controller: widget.controller,
      focusNode: _focus,
      keyboardType: widget.keyboardType,
      obscureText: widget.obscureText,
      enabled: widget.enabled,
      autofillHints: widget.autofillHints,
      onFieldSubmitted: widget.onSubmitted,
      validator: widget.validator,
      style: PaText.body(
        size: 15,
        color: PaColors.inkPrimary,
        weight: FontWeight.w500,
      ),
      decoration: InputDecoration(
        isDense: true,
        filled: true,
        fillColor: PaColors.paper,
        contentPadding: const EdgeInsets.symmetric(horizontal: 0, vertical: 16),
        hintText: widget.hint,
        hintStyle: PaText.body(size: 14, color: PaColors.inkMuted),
        prefixIcon: Padding(
          padding: const EdgeInsets.only(left: 16, right: 10),
          child: Icon(widget.icon, size: 20, color: PaColors.inkSecondary),
        ),
        prefixIconConstraints:
            const BoxConstraints(minWidth: 0, minHeight: 0),
        suffixIcon: widget.trailing,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: PaColors.line, width: 1),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: PaColors.line, width: 1),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: PaColors.blue, width: 1.4),
        ),
        errorBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: PaColors.danger, width: 1),
        ),
        focusedErrorBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: PaColors.danger, width: 1.4),
        ),
        errorStyle: PaText.body(size: 11.5, color: PaColors.danger),
      ),
    );
  }
}


/// CTA bleu gradient pleine largeur avec icône flèche + label blanc.
class _BlueCta extends StatelessWidget {
  const _BlueCta({
    required this.label,
    required this.onPressed,
    this.loading = false,
  });

  final String label;
  final VoidCallback? onPressed;
  final bool loading;

  @override
  Widget build(BuildContext context) {
    final disabled = onPressed == null || loading;
    return SizedBox(
      width: double.infinity,
      height: 52,
      child: Material(
        color: Colors.transparent,
        borderRadius: BorderRadius.circular(12),
        child: InkWell(
          onTap: disabled ? null : onPressed,
          borderRadius: BorderRadius.circular(12),
          child: Ink(
            decoration: BoxDecoration(
              gradient: LinearGradient(
                begin: Alignment.centerLeft,
                end: Alignment.centerRight,
                colors: disabled
                    ? [PaColors.line, PaColors.line]
                    : const [PaColors.blue, PaColors.navy],
              ),
              borderRadius: BorderRadius.circular(12),
            ),
            child: Center(
              child: loading
                  ? const SizedBox(
                      width: 22,
                      height: 22,
                      child: CircularProgressIndicator(
                        strokeWidth: 2.4,
                        color: Colors.white,
                      ),
                    )
                  : Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        const Icon(
                          Icons.login_rounded,
                          color: Colors.white,
                          size: 19,
                        ),
                        const SizedBox(width: 10),
                        Text(
                          label,
                          style: const TextStyle(
                            color: Colors.white,
                            fontSize: 15,
                            fontWeight: FontWeight.w700,
                            letterSpacing: 0.2,
                          ),
                        ),
                      ],
                    ),
            ),
          ),
        ),
      ),
    );
  }
}


/// Pill compacte fond paper bordure hairline, icône bleu + label.
class _Pill extends StatelessWidget {
  const _Pill({required this.icon, required this.label, required this.onTap});

  final IconData icon;
  final String label;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final disabled = onTap == null;
    return Material(
      color: Colors.transparent,
      borderRadius: BorderRadius.circular(10),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(10),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 9),
          decoration: BoxDecoration(
            color: PaColors.paper,
            borderRadius: BorderRadius.circular(10),
            border: Border.all(color: PaColors.line, width: 1),
          ),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.center,
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(
                icon,
                size: 14,
                color: disabled ? PaColors.inkMuted : PaColors.blue,
              ),
              const SizedBox(width: 6),
              Flexible(
                child: Text(
                  label,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(
                    color: disabled ? PaColors.inkMuted : PaColors.inkPrimary,
                    fontSize: 11.5,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
