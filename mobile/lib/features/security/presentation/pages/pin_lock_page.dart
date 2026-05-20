import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../../app/theme/paysika/pa_colors.dart';
import '../../../../app/theme/paysika/pa_typography.dart';
import '../../../../l10n/gen/app_localizations.dart';
import '../../../auth/presentation/state/auth_notifier.dart';
import '../../data/biometric_service.dart';
import '../state/pin_notifier.dart';
import '../widgets/pin_brand_badge.dart';
import '../widgets/pin_keypad.dart';

/// Écran de déverrouillage par PIN (à l'ouverture de l'app, façon Paysika).
///
/// Premium : halo dégradé vert→bleu derrière le logo, dots animés, et — si la
/// biométrie est activée — auto-prompt empreinte à l'ouverture + touche dédiée.
class PinLockPage extends ConsumerStatefulWidget {
  const PinLockPage({super.key});

  @override
  ConsumerState<PinLockPage> createState() => _PinLockPageState();
}

class _PinLockPageState extends ConsumerState<PinLockPage> {
  String _entry = '';
  bool _error = false;
  bool _bioTried = false;
  static const _len = 4;

  @override
  void initState() {
    super.initState();
    // Auto-prompt biométrique à l'ouverture si activé.
    WidgetsBinding.instance.addPostFrameCallback((_) => _maybePromptBiometric());
  }

  Future<void> _maybePromptBiometric() async {
    if (_bioTried) return;
    final st = ref.read(pinProvider).valueOrNull;
    if (st == null || !st.canUseBiometric) return;
    _bioTried = true;
    await _biometric();
  }

  Future<void> _biometric() async {
    final l = AppL10n.of(context);
    final ok = await ref.read(pinProvider.notifier).unlockWithBiometric(
          BiometricLabels(
            reason: l.biometric_reason_unlock,
            signInTitle: l.biometric_signin_title,
            hint: l.biometric_hint,
            cancelButton: l.biometric_cancel_button,
          ),
        );
    if (!mounted) return;
    if (ok) {
      HapticFeedback.mediumImpact();
      context.go('/home');
    }
  }

  void _onDigit(int d) {
    if (_entry.length >= _len) return;
    setState(() {
      _error = false;
      _entry += '$d';
    });
    if (_entry.length == _len) _onComplete();
  }

  void _onBackspace() {
    if (_entry.isEmpty) return;
    setState(() => _entry = _entry.substring(0, _entry.length - 1));
  }

  Future<void> _onComplete() async {
    final ok = await ref.read(pinProvider.notifier).unlock(_entry);
    if (!mounted) return;
    if (ok) {
      HapticFeedback.mediumImpact();
      context.go('/home');
    } else {
      HapticFeedback.vibrate();
      setState(() {
        _error = true;
        _entry = '';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final l = AppL10n.of(context);
    final member = ref.watch(authProvider).valueOrNull;
    final firstName = member?.prenom ?? '';
    final canBio = ref.watch(pinProvider).valueOrNull?.canUseBiometric ?? false;

    return Scaffold(
      backgroundColor: PaColors.canvas,
      body: SafeArea(
        child: Column(
          children: [
            const Spacer(flex: 2),
            const PinBrandBadge(),
            const SizedBox(height: 26),
            Text(
              firstName.isEmpty ? l.pin_welcome_back : l.pin_hello(firstName),
              style: PaText.heading(size: 22),
            ),
            const SizedBox(height: 8),
            Text(
              _error ? l.pin_wrong : l.pin_unlock_prompt,
              textAlign: TextAlign.center,
              style: PaText.body(
                size: 13.5,
                color: _error ? PaColors.danger : PaColors.inkMuted,
              ),
            ),
            const SizedBox(height: 30),
            PinDots(length: _len, filled: _entry.length, error: _error),
            const Spacer(flex: 2),
            PinKeypad(
              onDigit: _onDigit,
              onBackspace: _onBackspace,
              onBiometric: canBio ? _biometric : null,
            ),
            const SizedBox(height: 10),
            TextButton(
              onPressed: () {
                ref.read(authProvider.notifier).signOut();
                context.go('/login');
              },
              child: Text(
                l.pin_use_other_account,
                style: PaText.label(size: 13, color: PaColors.inkMuted),
              ),
            ),
            const Spacer(),
          ],
        ),
      ),
    );
  }
}
