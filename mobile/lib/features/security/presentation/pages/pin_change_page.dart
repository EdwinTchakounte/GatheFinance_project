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

/// Mise à jour du code secret en 3 temps :
///   1. saisir le code actuel  → 2. nouveau code  → 3. confirmation.
class PinChangePage extends ConsumerStatefulWidget {
  const PinChangePage({super.key});

  @override
  ConsumerState<PinChangePage> createState() => _PinChangePageState();
}

enum _Step { current, next, confirm }

class _PinChangePageState extends ConsumerState<PinChangePage> {
  _Step _step = _Step.current;
  String _current = '';
  String _next = '';
  String _entry = '';
  bool _error = false;
  String? _errorMsg;
  static const _len = 4;

  void _onDigit(int d) {
    if (_entry.length >= _len) return;
    setState(() {
      _error = false;
      _errorMsg = null;
      _entry += '$d';
    });
    if (_entry.length == _len) _onComplete();
  }

  void _onBackspace() {
    if (_entry.isEmpty) return;
    setState(() => _entry = _entry.substring(0, _entry.length - 1));
  }

  Future<void> _onComplete() async {
    final l = AppL10n.of(context);
    switch (_step) {
      case _Step.current:
        final ok = await ref.read(pinProvider.notifier).verify(_entry);
        if (!mounted) return;
        if (ok) {
          setState(() {
            _current = _entry;
            _entry = '';
            _step = _Step.next;
          });
        } else {
          _fail(l.pin_current_wrong);
        }
      case _Step.next:
        setState(() {
          _next = _entry;
          _entry = '';
          _step = _Step.confirm;
        });
      case _Step.confirm:
        if (_entry == _next) {
          final ok = await ref
              .read(pinProvider.notifier)
              .changePin(current: _current, next: _next);
          if (!mounted) return;
          if (ok) {
            unawaited(HapticFeedback.heavyImpact());
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(content: Text(l.pin_updated)),
            );
            context.pop();
          } else {
            _fail(l.pin_update_failed);
            setState(() => _step = _Step.current);
          }
        } else {
          _fail(l.pin_mismatch_short);
          setState(() => _step = _Step.next);
        }
    }
  }

  void _fail(String msg) {
    HapticFeedback.vibrate();
    setState(() {
      _error = true;
      _errorMsg = msg;
      _entry = '';
    });
  }

  @override
  Widget build(BuildContext context) {
    final l = AppL10n.of(context);
    final (title, subtitle) = switch (_step) {
      _Step.current => (l.pin_current_title, l.pin_current_sub),
      _Step.next => (l.pin_new_title, l.pin_new_sub),
      _Step.confirm => (l.pin_confirm_new_title, l.pin_confirm_new_sub),
    };

    return Scaffold(
      backgroundColor: PaColors.canvas,
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_rounded, color: PaColors.inkPrimary),
          onPressed: () => context.pop(),
        ),
      ),
      body: SafeArea(
        child: Column(
          children: [
            const Spacer(),
            const PinBrandBadge(icon: Icons.lock_outline_rounded),
            const SizedBox(height: 24),
            Text(title, style: PaText.heading(size: 22)),
            const SizedBox(height: 8),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 40),
              child: Text(
                _error ? (_errorMsg ?? '') : subtitle,
                textAlign: TextAlign.center,
                style: PaText.body(
                  size: 13.5,
                  color: _error ? PaColors.danger : PaColors.inkMuted,
                ),
              ),
            ),
            const SizedBox(height: 30),
            PinDots(length: _len, filled: _entry.length, error: _error),
            const Spacer(flex: 2),
            PinKeypad(onDigit: _onDigit, onBackspace: _onBackspace),
            const SizedBox(height: 20),
          ],
        ),
      ),
    );
  }
}
