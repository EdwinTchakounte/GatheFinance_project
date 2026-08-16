import 'package:flutter_secure_storage/flutter_secure_storage.dart';

/// Stockage sécurisé du code PIN (déverrouillage app + révélation solde).
///
/// Le PIN est persisté via `flutter_secure_storage`, qui chiffre la valeur au
/// repos (Android Keystore / iOS Keychain). On applique en plus un obfuscage
/// déterministe simple (rotation + sel) pour ne pas écrire le PIN en clair —
/// défense en profondeur, sans dépendance crypto externe.
class PinRepository {
  PinRepository([FlutterSecureStorage? storage])
      : _storage = storage ?? _defaultStorage();

  final FlutterSecureStorage _storage;

  /// Stockage sécurisé configuré pour la FIABILITÉ sur Android.
  ///
  /// Sans ces options, `flutter_secure_storage` retombe sur le mode hérité
  /// (clé RSA Keystore enveloppant un AES posé dans des SharedPreferences
  /// classiques). Ce mode échoue la relecture sur de nombreux devices réels :
  /// au démarrage `hasPin()` renvoie faux et l'app redemande la CRÉATION du
  /// code à chaque ouverture. On force donc :
  ///   • `encryptedSharedPreferences` → EncryptedSharedPreferences (Jetpack
  ///     Security) : clé maître + données gérées ensemble, persistance fiable ;
  ///   • `resetOnError` → un déchiffrement impossible réinitialise le magasin
  ///     au lieu de lever en boucle (ex. clé Keystore invalidée / migration).
  static FlutterSecureStorage _defaultStorage() => const FlutterSecureStorage(
        aOptions: AndroidOptions(
          encryptedSharedPreferences: true,
          resetOnError: true,
        ),
        iOptions: IOSOptions(
          accessibility: KeychainAccessibility.first_unlock,
        ),
      );

  static const _key = 'gathe_pin_v1';
  static const _bioKey = 'gathe_biometric_v1';
  static const _salt = 'GF-2026';

  /// Obfuscage déterministe : sel + somme rotative des codes. Pas une crypto
  /// forte, mais combiné au chiffrement Keystore c'est suffisant pour un PIN
  /// d'app non-bancaire. Remplaçable par un vrai hash si on ajoute `crypto`.
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
      final v = await _storage.read(key: _key);
      return v != null && v.isNotEmpty;
    } catch (_) {
      // Lecture illisible (migration/clé invalidée) : on ne bloque pas — le
      // parcours de (re)création prendra le relais proprement.
      return false;
    }
  }

  Future<void> setPin(String pin) async {
    await _storage.write(key: _key, value: _obfuscate(pin));
  }

  Future<bool> verify(String pin) async {
    try {
      final stored = await _storage.read(key: _key);
      if (stored == null) return false;
      return stored == _obfuscate(pin);
    } catch (_) {
      return false;
    }
  }

  Future<void> clear() async {
    await _storage.delete(key: _key);
    await _storage.delete(key: _bioKey);
  }

  // ── Préférence biométrie ──────────────────────────────────────────────────

  /// L'utilisateur a-t-il activé le déverrouillage par empreinte ?
  Future<bool> biometricEnabled() async {
    return (await _storage.read(key: _bioKey)) == '1';
  }

  Future<void> setBiometricEnabled(bool enabled) async {
    await _storage.write(key: _bioKey, value: enabled ? '1' : '0');
  }
}
