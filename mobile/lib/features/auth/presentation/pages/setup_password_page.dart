import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../../app/theme/paysika/pa_colors.dart';
import '../../../../core/di/providers.dart';
import '../../../../core/network/api_config.dart';
import '../../../../core/widgets/paysika/pa_button.dart';
import '../../data/datasources/auth_remote_datasource.dart';

/// Flow "Définir mon mot de passe initial" (PWD Option B).
///
/// Le membre vient d'etre approuve, a recu un email avec un lien
/// `https://gathe-finance.horus-lab.com/fr/definir-mot-de-passe?token=XXX`.
/// Le portail web fait deja le job. Cette page mobile est un duplicat pour les
/// membres qui prefèrent tout faire dans l'app (ou qui n'ont pas de
/// navigateur fiable).
///
/// 3 etapes :
///   1. Saisie/collage du token recu par email (`/auth/setup-password/verify/`)
///   2. Affichage email mask + nouveau mot de passe + confirmation
///      (`/auth/setup-password/confirm/`)
///   3. Confirmation visuelle + retour login
///
/// Le token peut etre pre-rempli via `?token=XXX` dans la route (utile pour
/// un futur deep link mobile, ou pour des tests).
class SetupPasswordPage extends ConsumerStatefulWidget {
  const SetupPasswordPage({super.key, this.initialToken});

  final String? initialToken;

  @override
  ConsumerState<SetupPasswordPage> createState() => _SetupPasswordPageState();
}

enum _Step { token, password, done }

class _SetupPasswordPageState extends ConsumerState<SetupPasswordPage> {
  final _tokenCtrl = TextEditingController();
  final _pwCtrl = TextEditingController();
  final _pwConfirmCtrl = TextEditingController();
  _Step _step = _Step.token;
  bool _loading = false;
  String? _error;
  PasswordSetupTokenInfo? _tokenInfo;

  @override
  void initState() {
    super.initState();
    final t = widget.initialToken?.trim();
    if (t != null && t.isNotEmpty) {
      _tokenCtrl.text = t;
      // Verify automatiquement si un token est passe en argument (deep link
      // futur). En attendant, l'utilisateur copie-colle depuis l'email.
      WidgetsBinding.instance.addPostFrameCallback((_) => _verifyToken());
    }
  }

  @override
  void dispose() {
    _tokenCtrl.dispose();
    _pwCtrl.dispose();
    _pwConfirmCtrl.dispose();
    super.dispose();
  }

  Future<void> _verifyToken() async {
    final token = _tokenCtrl.text.trim();
    if (token.isEmpty) {
      setState(() => _error = 'Colle ici le code du lien recu par email.');
      return;
    }
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final info = await ref.read(authDataSourceProvider).verifySetupToken(token);
      if (!mounted) return;
      setState(() {
        _tokenInfo = info;
        _step = _Step.password;
        _loading = false;
      });
      unawaited(HapticFeedback.selectionClick());
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = e.toString().replaceFirst('Exception: ', '');
        _loading = false;
      });
    }
  }

  Future<void> _confirmPassword() async {
    final pw = _pwCtrl.text;
    final confirm = _pwConfirmCtrl.text;
    if (pw.length < 4) {
      setState(() => _error = 'Le mot de passe doit faire au moins 4 caracteres.');
      return;
    }
    if (pw != confirm) {
      setState(() => _error = 'Les deux mots de passe ne correspondent pas.');
      return;
    }
    setState(() {
      _loading = true;
      _error = null;
    });
    final err = await ref.read(authDataSourceProvider).confirmPasswordSetup(
          token: _tokenCtrl.text.trim(),
          newPassword: pw,
        );
    if (!mounted) return;
    if (err != null) {
      setState(() {
        _error = err;
        _loading = false;
      });
      return;
    }
    unawaited(HapticFeedback.mediumImpact());
    setState(() {
      _step = _Step.done;
      _loading = false;
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: PaColors.canvas,
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_rounded, color: PaColors.inkPrimary),
          onPressed: () => context.pop(),
        ),
        title: const Text(
          'Definir mon mot de passe',
          style: TextStyle(color: PaColors.inkPrimary, fontSize: 16, fontWeight: FontWeight.w600),
        ),
      ),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.fromLTRB(24, 8, 24, 32),
          child: switch (_step) {
            _Step.token => _tokenStep(),
            _Step.password => _passwordStep(),
            _Step.done => _doneStep(),
          },
        ),
      ),
    );
  }

  Widget _tokenStep() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _StepHeader(
          eyebrow: 'Etape 1 / 2',
          title: 'Colle le code recu par email',
          subtitle:
              'Apres ton approbation, tu as recu un lien ${ApiConfig.siteBaseUrl}/fr/definir-mot-de-passe?token=XXX. Copie la partie apres token= et colle-la ici.',
        ),
        const SizedBox(height: 24),
        TextField(
          controller: _tokenCtrl,
          autocorrect: false,
          enableSuggestions: false,
          decoration: const InputDecoration(
            labelText: 'Code du lien (token)',
            hintText: 'Par exemple : aB3xY9...',
            border: OutlineInputBorder(),
          ),
        ),
        if (_error != null) _ErrorBanner(message: _error!),
        const SizedBox(height: 18),
        PaButton(
          label: _loading ? 'Verification…' : 'Verifier le lien',
          onPressed: _loading ? null : _verifyToken,
        ),
        const SizedBox(height: 12),
        const Text(
          "Plus pratique : ouvre le lien directement depuis ton email — il t'amenera sur la page web qui fait la meme chose.",
          style: TextStyle(color: PaColors.inkSecondary, fontSize: 12, height: 1.4),
        ),
      ],
    );
  }

  Widget _passwordStep() {
    final mask = _tokenInfo?.emailMask ?? '';
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _StepHeader(
          eyebrow: 'Etape 2 / 2',
          title: 'Choisis ton mot de passe',
          subtitle: mask.isEmpty
              ? 'Token verifie. Definis ton mot de passe initial ci-dessous.'
              : 'Compte associe : $mask. Definis ton mot de passe initial ci-dessous.',
        ),
        const SizedBox(height: 24),
        TextField(
          controller: _pwCtrl,
          obscureText: true,
          autocorrect: false,
          enableSuggestions: false,
          decoration: const InputDecoration(
            labelText: 'Nouveau mot de passe',
            hintText: '4 caracteres minimum',
            border: OutlineInputBorder(),
          ),
        ),
        const SizedBox(height: 12),
        TextField(
          controller: _pwConfirmCtrl,
          obscureText: true,
          autocorrect: false,
          enableSuggestions: false,
          decoration: const InputDecoration(
            labelText: 'Confirme le mot de passe',
            border: OutlineInputBorder(),
          ),
        ),
        if (_error != null) _ErrorBanner(message: _error!),
        const SizedBox(height: 18),
        PaButton(
          label: _loading ? 'Enregistrement…' : 'Definir mon mot de passe',
          onPressed: _loading ? null : _confirmPassword,
        ),
      ],
    );
  }

  Widget _doneStep() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.center,
      children: [
        const SizedBox(height: 32),
        Container(
          width: 72,
          height: 72,
          decoration: BoxDecoration(
            color: PaColors.success.withValues(alpha: 0.15),
            shape: BoxShape.circle,
          ),
          alignment: Alignment.center,
          child: const Icon(Icons.check_rounded, color: PaColors.success, size: 38),
        ),
        const SizedBox(height: 22),
        const Text(
          'Mot de passe defini !',
          style: TextStyle(color: PaColors.inkPrimary, fontSize: 22, fontWeight: FontWeight.w700),
        ),
        const SizedBox(height: 10),
        const Text(
          'Tu peux maintenant te connecter avec ton email et ton nouveau mot de passe.',
          textAlign: TextAlign.center,
          style: TextStyle(color: PaColors.inkSecondary, fontSize: 14, height: 1.45),
        ),
        const SizedBox(height: 28),
        PaButton(
          label: 'Aller a la connexion',
          onPressed: () => context.go('/login'),
        ),
      ],
    );
  }
}

class _StepHeader extends StatelessWidget {
  const _StepHeader({
    required this.eyebrow,
    required this.title,
    required this.subtitle,
  });

  final String eyebrow;
  final String title;
  final String subtitle;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          eyebrow.toUpperCase(),
          style: const TextStyle(
            color: PaColors.teal,
            fontSize: 11,
            fontWeight: FontWeight.w700,
            letterSpacing: 1.4,
          ),
        ),
        const SizedBox(height: 6),
        Text(
          title,
          style: const TextStyle(color: PaColors.inkPrimary, fontSize: 22, fontWeight: FontWeight.w700, height: 1.2),
        ),
        const SizedBox(height: 8),
        Text(
          subtitle,
          style: const TextStyle(color: PaColors.inkSecondary, fontSize: 13, height: 1.45),
        ),
      ],
    );
  }
}

class _ErrorBanner extends StatelessWidget {
  const _ErrorBanner({required this.message});
  final String message;

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(top: 14),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: PaColors.danger.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: PaColors.danger.withValues(alpha: 0.3)),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Icon(Icons.error_outline_rounded, color: PaColors.danger, size: 18),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              message,
              style: const TextStyle(color: PaColors.danger, fontSize: 13, height: 1.35),
            ),
          ),
        ],
      ),
    );
  }
}
