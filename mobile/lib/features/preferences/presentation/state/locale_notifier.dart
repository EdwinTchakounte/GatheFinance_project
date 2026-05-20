import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Préférence utilisateur pour la langue de l'application.
///
/// Persisté en SharedPreferences sous la clé `locale_code` avec
/// les valeurs `fr` ou `en`. Si rien n'est stocké, on tombe sur
/// `fr` (langue par défaut côté coopérative).
class LocaleNotifier extends AsyncNotifier<Locale> {
  static const _key = 'locale_code';
  static const _defaultCode = 'fr';
  static const supportedCodes = <String>['fr', 'en'];

  @override
  Future<Locale> build() async {
    final prefs = await SharedPreferences.getInstance();
    final code = prefs.getString(_key) ?? _defaultCode;
    return Locale(supportedCodes.contains(code) ? code : _defaultCode);
  }

  Future<void> setCode(String code) async {
    if (!supportedCodes.contains(code)) return;
    state = AsyncValue.data(Locale(code));
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_key, code);
  }
}

final localeProvider =
    AsyncNotifierProvider<LocaleNotifier, Locale>(LocaleNotifier.new);
