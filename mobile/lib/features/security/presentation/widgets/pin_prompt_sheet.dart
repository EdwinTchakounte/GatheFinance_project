import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../app/theme/paysika/pa_colors.dart';
import '../../../../l10n/gen/app_localizations.dart';
import '../../data/biometric_service.dart';
import '../state/pin_notifier.dart';
import 'pin_keypad.dart';

/// Bottom sheet de vérification du PIN . utilisé pour révéler le solde.
///
/// Retourne `true` via `Navigator.pop` si le PIN saisi est correct, sinon
/// reste ouvert avec un message d'erreur jusqu'à abandon (retour).
class PinPromptSheet extends ConsumerStatefulWidget {
  const PinPromptSheet({super.key, this.title});

  /// Titre optionnel ; si null, retombe sur le libellé localisé par défaut.
  final String? title;

  /// Ouvre la modale et renvoie `true` si le PIN est validé.
  static Future<bool> show(BuildContext context, {String? title}) async {
    final ok = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      backgroundColor: PaColors.canvas,
      barrierColor: PaColors.navyDeep.withValues(alpha: 0.55),
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      builder: (_) => PinPromptSheet(title: title),
    );
    return ok ?? false;
  }

  @override
  ConsumerState<PinPromptSheet> createState() => _PinPromptSheetState();
}

class _PinPromptSheetState extends ConsumerState<PinPromptSheet> {
  String _entry = '';
  bool _error = false;
  bool _bioTried = false;
  static const _len = 4;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _maybeBiometric());
  }

  Future<void> _maybeBiometric() async {
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
      unawaited(HapticFeedback.mediumImpact());
      Navigator.of(context).pop(true);
    }
  }

  void _onDigit(int d) {
    if (_entry.length >= _len) return;
    setState(() {
      _error = false;
      _entry += '$d';
    });
    if (_entry.length == _len) _verify();
  }

  void _onBackspace() {
    if (_entry.isEmpty) return;
    setState(() => _entry = _entry.substring(0, _entry.length - 1));
  }

  Future<void> _verify() async {
    final ok = await ref.read(pinProvider.notifier).verify(_entry);
    if (!mounted) return;
    if (ok) {
      unawaited(HapticFeedback.mediumImpact());
      Navigator.of(context).pop(true);
    } else {
      unawaited(HapticFeedback.vibrate());
      setState(() {
        _error = true;
        _entry = '';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final l = AppL10n.of(context);
    final canBio = ref.watch(pinProvider).valueOrNull?.canUseBiometric ?? false;
    return SafeArea(
      top: false,
      child: Padding(
        padding: const EdgeInsets.fromLTRB(20, 14, 20, 24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 40,
              height: 4,
              decoration: BoxDecoration(
                color: PaColors.line,
                borderRadius: BorderRadius.circular(2),
              ),
            ),
            const SizedBox(height: 22),
            Text(
              widget.title ?? l.pin_reveal_title,
              style: const TextStyle(
                color: PaColors.inkPrimary,
                fontSize: 19,
                fontWeight: FontWeight.w700,
              ),
            ),
            const SizedBox(height: 6),
            Text(
              _error ? l.pin_wrong : l.pin_reveal_sub,
              style: TextStyle(
                color: _error ? PaColors.danger : PaColors.inkMuted,
                fontSize: 13.5,
              ),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 26),
            PinDots(length: _len, filled: _entry.length, error: _error),
            const SizedBox(height: 26),
            PinKeypad(
              onDigit: _onDigit,
              onBackspace: _onBackspace,
              onBiometric: canBio ? _biometric : null,
            ),
          ],
        ),
      ),
    );
  }
}
