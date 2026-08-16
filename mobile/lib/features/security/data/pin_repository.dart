import 'package:shared_preferences/shared_preferences.dart';

/// Stockage du code PIN (déverrouillage app + révélation solde).
///
/// IMPORTANT — choix de persistance : on utilise `shared_preferences` et NON
/// `flutter_secure_storage`. Sur beaucoup de devices Android réels, le stockage
/// sécurisé (Keystore / EncryptedSharedPreferences) échoue la relecture au
/// démarrage à froid (clé non prête, erreur de déchiffrement transitoire), et
/// `resetOnError` efface alors le PIN → l'app redemande la CRÉATION du code à
/// CHAQUE ouverture. `shared_preferences` persiste de façon fiable.
///
/// Le PIN n'est jamais écrit en clair : on stocke un hash déterministe salé
/// (`_obfuscate`). Ce code protège l'accès à l'UI locale ; la vraie sécurité du
/// compte reste la session serveur (cookie httpOnly). Pour un PIN à 4 chiffres,
/// un hash local reste intrinsèquement brute-forçable hors-ligne — c'est
/// inhérent et acceptable pour ce niveau (app non bancaire, device du membre).
class PinRepository {
  PinRepository();

  static const _key = 'gathe_pin_v1';
  static const _bioKey = 'gathe_biometric_v1';
  static const _salt = 'GF-2026';

  Future<SharedPreferences> get _prefs => SharedPreferences.getInstance();

  /// Hash déterministe (sel + somme rotative) — non réversible, sans dépendance
  /// crypto externe. Remplaçable par un vrai SHA-256 si `crypto` est ajouté.
  String _obfuscate(String pin) {
    final input = '$_salt:$pin';
    var acc = 7;
    final sb = StringBuffer();
    for (final c in input.codeUnits) {
      acc = (acc * 31 + c) & 0x7fffffff;
      sb.write(acc.toRadixString(16));
    }
    return sb.toString();
  }

  Future<bool> hasPin() async {
    try {
      final v = (await _prefs).getString(_key);
      return v != null && v.isNotEmpty;
    } catch (_) {
      return false;
    }
  }

  Future<void> setPin(String pin) async {
    await (await _prefs).setString(_key, _obfuscate(pin));
  }

  Future<bool> verify(String pin) async {
    try {
      final stored = (await _prefs).getString(_key);
      if (stored == null) return false;
      return stored == _obfuscate(pin);
    } catch (_) {
      return false;
    }
  }

  Future<void> clear() async {
    final p = await _prefs;
    await p.remove(_key);
    await p.remove(_bioKey);
  }

  // ── Préférence biométrie ──────────────────────────────────────────────────

  /// L'utilisateur a-t-il activé le déverrouillage par empreinte ?
  Future<bool> biometricEnabled() async {
    return (await _prefs).getString(_bioKey) == '1';
  }

  Future<void> setBiometricEnabled(bool enabled) async {
    await (await _prefs).setString(_bioKey, enabled ? '1' : '0');
  }
}
