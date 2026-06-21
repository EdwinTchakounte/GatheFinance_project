import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

/// Cache "last-known-good" pour des données métier — utilisé par les
/// notifiers pour rendre l'app utilisable hors-ligne. La règle est :
///
///   1. Tenter le fetch live ; sauver le snapshot en cas de succès.
///   2. Si le fetch échoue : retomber sur le snapshot précédent (si présent).
///
/// Format : `{ "at": <epoch ms>, "data": <json caller-defined> }`. Le caller
/// est responsable de la sérialisation/désérialisation du payload. Le store
/// ne fait pas de TTL — c'est l'UI qui décide d'afficher une bannière
/// "données du XX/XX à HH:MM" en fonction de la fraîcheur.
class SnapshotStore {
  SnapshotStore._();

  static const _prefix = 'snapshot:';

  /// Persiste [data] sous [key]. [data] doit être un type JSON-encodable.
  static Future<void> save(String key, Object data) async {
    final prefs = await SharedPreferences.getInstance();
    final payload = jsonEncode({
      'at': DateTime.now().millisecondsSinceEpoch,
      'data': data,
    });
    await prefs.setString('$_prefix$key', payload);
  }

  /// Charge le snapshot [key] ou `null` s'il n'existe pas / est corrompu.
  /// Renvoie un tuple `(payload, savedAt)`.
  static Future<({Object data, DateTime savedAt})?> load(String key) async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString('$_prefix$key');
    if (raw == null || raw.isEmpty) return null;
    try {
      final json = jsonDecode(raw) as Map<String, dynamic>;
      final at = json['at'] as int?;
      final data = json['data'];
      if (at == null || data == null) return null;
      return (
        data: data as Object,
        savedAt: DateTime.fromMillisecondsSinceEpoch(at),
      );
    } catch (_) {
      // JSON corrompu — on ignore plutôt que de propager. Le caller
      // ré-écrira un snapshot frais au prochain fetch réussi.
      return null;
    }
  }

  /// Supprime le snapshot [key]. Idempotent.
  static Future<void> clear(String key) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove('$_prefix$key');
  }
}
