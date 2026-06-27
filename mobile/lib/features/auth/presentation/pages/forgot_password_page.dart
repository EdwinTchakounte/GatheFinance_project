import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../../app/theme/paysika/pa_colors.dart';
import '../../../../core/di/providers.dart';
import '../../../../core/error/failures.dart';
import '../../../../core/widgets/paysika/pa_button.dart';
import '../../domain/usecases/confirm_password_reset.dart';
import '../../domain/usecases/request_password_reset.dart';

/// Flow "mot de passe oublié" . 3 étapes :
///   1. Saisie de l'e-mail → POST /auth/password-reset/request/
///   2. Saisie OTP 6 chiffres + nouveau mot de passe → POST .../confirm/
///   3. Confirmation visuelle + retour login
///
/// La réponse de l'étape 1 est opaque (anti-énumération côté backend) :
/// on affiche toujours « Si un compte existe, un code a été envoyé ».
class ForgotPasswordPage extends ConsumerStatefulWidget {
  const ForgotPasswordPage({super.key});

  @override
  ConsumerState<ForgotPasswordPage> createState() => _ForgotPasswordPageState();
}

enum _Step { email, code, done }

class _ForgotPasswordPageState extends ConsumerState<ForgotPasswordPage> {
  final _emailCtrl = TextEditingController();
  final _codeCtrl = TextEditingController();
  final _pwCtrl = TextEditingController();
  final _pwConfirmCtrl = TextEditingController();
  _Step _step = _Step.email;
  bool _loading = false;
  String? _error;

  @override
  void dispose() {
    _emailCtrl.dispose();
    _codeCtrl.dispose();
    _pwCtrl.dispose();
    _pwConfirmCtrl.dispose();
    super.dispose();
  }

  Future<void> _sendCode() async {
    final email = _emailCtrl.text.trim();
    if (email.isEmpty || !email.contains('@')) {
      setState(() => _error = 'Adresse e-mail invalide.');
      return;
    }
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      await ref.read(requestPasswordResetUseCaseProvider).call(
            RequestPasswordResetParams(email: email),
          );
      if (!mounted) return;
      unawaited(HapticFeedback.lightImpact());
      setState(() {
        _step = _Step.code;
        _loading = false;
      });
    } on Failure catch (f) {
      if (!mounted) return;
      setState(() {
        _error = f.message;
        _loading = false;
      });
    }
  }

  Future<void> _confirm() async {
    final pw = _pwCtrl.text;
    if (pw.length < 8) {
      setState(() => _error = 'Le mot de passe doit faire au moins 8 caractères.');
      return;
    }
    if (pw != _pwConfirmCtrl.text) {
      setState(() => _error = 'Les deux mots de passe ne correspondent pas.');
      return;
    }
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final err = await ref.read(confirmPasswordResetUseCaseProvider).call(
            ConfirmPasswordResetParams(
              email: _emailCtrl.text,
              code: _codeCtrl.text,
              newPassword: pw,
            ),
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
    } on Failure catch (f) {
      if (!mounted) return;
      setState(() {
        _error = f.message;
        _loading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: PaColors.appBg,
      appBar: AppBar(
        backgroundColor: PaColors.appBg,
        elevation: 0,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_rounded, color: PaColors.inkPrimary),
          onPressed: () {
            if (_step == _Step.code) {
              setState(() => _step = _Step.email);
            } else {
              context.go('/login');
            }
          },
        ),
      ),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(24, 8, 24, 24),
          child: switch (_step) {
            _Step.email => _emailStep(),
            _Step.code => _codeStep(),
            _Step.done => _doneStep(),
          },
        ),
      ),
    );
  }

  Widget _emailStep() {
    return SingleChildScrollView(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const SizedBox(height: 12),
          Container(
            width: 64,
            height: 64,
            decoration: const BoxDecoration(
              color: PaColors.tealSurface,
              shape: BoxShape.circle,
            ),
            alignment: Alignment.center,
            child: const Icon(Icons.lock_reset_rounded,
                color: PaColors.teal, size: 32,),
          ),
          const SizedBox(height: 22),
          const Text(
            'Mot de passe oublié ?',
            style: TextStyle(
              color: PaColors.inkPrimary,
              fontSize: 24,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 6),
          const Text(
            'Indique l\'adresse e-mail de ton compte. Tu recevras un code à 6 chiffres pour réinitialiser ton mot de passe.',
            style: TextStyle(
              color: PaColors.inkSecondary,
              fontSize: 14,
              height: 1.5,
            ),
          ),
          const SizedBox(height: 26),
          const Text('Adresse e-mail',
              style: TextStyle(
                  color: PaColors.inkSecondary,
                  fontSize: 12.5,
                  fontWeight: FontWeight.w700,
                  letterSpacing: 1.2,),),
          const SizedBox(height: 8),
          TextFormField(
            controller: _emailCtrl,
            keyboardType: TextInputType.emailAddress,
            autocorrect: false,
            autofocus: true,
            textInputAction: TextInputAction.send,
            onFieldSubmitted: (_) => _sendCode(),
            decoration: const InputDecoration(
              hintText: 'votre.email@example.com',
              prefixIcon: Icon(Icons.alternate_email_rounded, size: 20),
              contentPadding:
                  EdgeInsets.symmetric(horizontal: 14, vertical: 14),
            ),
          ),
          if (_error != null) ...[
            const SizedBox(height: 10),
            Text(_error!,
                style: const TextStyle(
                    color: PaColors.danger,
                    fontSize: 13,
                    fontWeight: FontWeight.w600,),),
          ],
          const SizedBox(height: 24),
          PaButton(
            label: _loading ? 'Envoi…' : 'Recevoir le code',
            onPressed: _loading ? null : _sendCode,
          ),
        ],
      ),
    );
  }

  Widget _codeStep() {
    return SingleChildScrollView(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const SizedBox(height: 12),
          Container(
            width: 64,
            height: 64,
            decoration: const BoxDecoration(
              color: PaColors.tealSurface,
              shape: BoxShape.circle,
            ),
            alignment: Alignment.center,
            child: const Icon(Icons.mark_email_unread_outlined,
                color: PaColors.teal, size: 30,),
          ),
          const SizedBox(height: 22),
          const Text(
            'Vérifie ta boîte e-mail',
            style: TextStyle(
              color: PaColors.inkPrimary,
              fontSize: 24,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 6),
          Text(
            'Si un compte existe pour ${_emailCtrl.text}, un code à 6 chiffres y a été envoyé. Il expire dans 15 minutes.',
            style: const TextStyle(
              color: PaColors.inkSecondary,
              fontSize: 14,
              height: 1.5,
            ),
          ),
          const SizedBox(height: 26),
          const Text('Code à 6 chiffres',
              style: TextStyle(
                  color: PaColors.inkSecondary,
                  fontSize: 12.5,
                  fontWeight: FontWeight.w700,
                  letterSpacing: 1.2,),),
          const SizedBox(height: 8),
          TextFormField(
            controller: _codeCtrl,
            keyboardType: TextInputType.number,
            inputFormatters: [
              FilteringTextInputFormatter.digitsOnly,
              LengthLimitingTextInputFormatter(6),
            ],
            autofocus: true,
            style: const TextStyle(
              fontSize: 22,
              letterSpacing: 8,
              fontWeight: FontWeight.w700,
              color: PaColors.inkPrimary,
            ),
            textAlign: TextAlign.center,
            decoration: const InputDecoration(
              hintText: '••••••',
              contentPadding:
                  EdgeInsets.symmetric(horizontal: 14, vertical: 14),
            ),
          ),
          const SizedBox(height: 18),
          const Text('Nouveau mot de passe',
              style: TextStyle(
                  color: PaColors.inkSecondary,
                  fontSize: 12.5,
                  fontWeight: FontWeight.w700,
                  letterSpacing: 1.2,),),
          const SizedBox(height: 8),
          TextFormField(
            controller: _pwCtrl,
            obscureText: true,
            decoration: const InputDecoration(
              hintText: '8 caractères minimum',
              prefixIcon: Icon(Icons.lock_outline_rounded, size: 20),
              contentPadding:
                  EdgeInsets.symmetric(horizontal: 14, vertical: 14),
            ),
          ),
          const SizedBox(height: 12),
          TextFormField(
            controller: _pwConfirmCtrl,
            obscureText: true,
            textInputAction: TextInputAction.done,
            onFieldSubmitted: (_) => _confirm(),
            decoration: const InputDecoration(
              hintText: 'Confirmation',
              prefixIcon: Icon(Icons.lock_outline_rounded, size: 20),
              contentPadding:
                  EdgeInsets.symmetric(horizontal: 14, vertical: 14),
            ),
          ),
          if (_error != null) ...[
            const SizedBox(height: 10),
            Text(_error!,
                style: const TextStyle(
                    color: PaColors.danger,
                    fontSize: 13,
                    fontWeight: FontWeight.w600,),),
          ],
          const SizedBox(height: 22),
          PaButton(
            label: _loading ? 'Validation…' : 'Réinitialiser le mot de passe',
            onPressed: _loading ? null : _confirm,
          ),
          const SizedBox(height: 10),
          TextButton(
            onPressed: _loading
                ? null
                : () {
                    setState(() {
                      _step = _Step.email;
                      _codeCtrl.clear();
                      _pwCtrl.clear();
                      _pwConfirmCtrl.clear();
                      _error = null;
                    });
                  },
            child: const Text('Renvoyer un code',
                style: TextStyle(
                    color: PaColors.teal, fontWeight: FontWeight.w700,),),
          ),
        ],
      ),
    );
  }

  Widget _doneStep() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Container(
            width: 80,
            height: 80,
            decoration: BoxDecoration(
              color: PaColors.success.withValues(alpha: 0.14),
              shape: BoxShape.circle,
            ),
            alignment: Alignment.center,
            child: const Icon(Icons.check_rounded,
                color: PaColors.success, size: 42,),
          ),
          const SizedBox(height: 22),
          const Text(
            'Mot de passe réinitialisé',
            style: TextStyle(
              color: PaColors.inkPrimary,
              fontSize: 22,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 8),
          const Padding(
            padding: EdgeInsets.symmetric(horizontal: 18),
            child: Text(
              'Tu peux maintenant te connecter avec ton nouveau mot de passe.',
              textAlign: TextAlign.center,
              style: TextStyle(
                color: PaColors.inkSecondary,
                fontSize: 14,
                height: 1.5,
              ),
            ),
          ),
          const SizedBox(height: 28),
          SizedBox(
            width: double.infinity,
            child: PaButton(
              label: 'Aller à la connexion',
              onPressed: () => context.go('/login'),
            ),
          ),
        ],
      ),
    );
  }
}
