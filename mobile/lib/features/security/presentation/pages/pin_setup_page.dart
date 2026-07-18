import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../../app/theme/paysika/pa_colors.dart';
import '../../../../app/theme/paysika/pa_typography.dart';
import '../../../../l10n/gen/app_localizations.dart';
import '../state/pin_notifier.dart';
import '../widgets/pin_brand_badge.dart';
import '../widgets/pin_keypad.dart';

/// Configuration du PIN au 1er login.
///
/// Deux temps : saisie d'un PIN à 4 chiffres, puis confirmation. Si les deux
/// correspondent, le PIN est persisté et l'app déverrouillée → `/home`.
class PinSetupPage extends ConsumerStatefulWidget {
  const PinSetupPage({super.key});

  @override
  ConsumerState<PinSetupPage> createState() => _PinSetupPageState();
}

class _PinSetupPageState extends ConsumerState<PinSetupPage> {
  String _first = '';
  String _entry = '';
  bool _confirming = false;
  bool _error = false;

  static const _len = 4;

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
    if (!_confirming) {
      // Première saisie → on demande la confirmation.
      setState(() {
        _first = _entry;
        _entry = '';
        _confirming = true;
      });
      return;
    }
    // Confirmation.
    if (_entry == _first) {
      await ref.read(pinProvider.notifier).setPin(_entry);
      if (!mounted) return;
      unawaited(HapticFeedback.heavyImpact());
      context.go('/home');
    } else {
      unawaited(HapticFeedback.vibrate());
      setState(() {
        _error = true;
        _entry = '';
        _first = '';
        _confirming = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final l = AppL10n.of(context);
    final title = _confirming ? l.pin_confirm_title : l.pin_create_title;
    final subtitle = _error
        ? l.pin_mismatch
        : _confirming
            ? l.pin_confirm_prompt
            : l.pin_create_sub;

    return Scaffold(
      backgroundColor: PaColors.canvas,
      body: SafeArea(
        child: Column(
          children: [
            const Spacer(flex: 2),
            const PinBrandBadge(),
            const SizedBox(height: 24),
            Text(
              title,
              style: PaText.heading(size: 22),
            ),
            const SizedBox(height: 8),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 40),
              child: Text(
                subtitle,
                textAlign: TextAlign.center,
                style: TextStyle(
                  color: _error ? PaColors.danger : PaColors.inkMuted,
                  fontSize: 13,
                  height: 1.4,
                ),
              ),
            ),
            const SizedBox(height: 32),
            PinDots(length: _len, filled: _entry.length, error: _error),
            const Spacer(flex: 2),
            PinKeypad(onDigit: _onDigit, onBackspace: _onBackspace),
            const Spacer(),
          ],
        ),
      ),
    );
  }
}
