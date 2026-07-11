import 'package:intl/intl.dart';

/// Formatage standard des montants XAF : "1 234 567 XAF".
/// Toujours espace fine entre les milliers, pas de décimales.
class XAFFormatter {
  XAFFormatter._();

  static final _fr = NumberFormat.decimalPattern('fr_FR');

  /// Renvoie `1 234 567 XAF`.
  static String format(num amount) => '${_fr.format(amount.round())} XAF';

  /// Renvoie juste `1 234 567` (sans la devise — utile pour grandes typos).
  static String formatNumber(num amount) => _fr.format(amount.round());

  /// Pour les chiffres compacts façon `1,2 M XAF`.
  ///
  /// Une décimale, jamais d'arrondi trompeur : `2 500` → `2,5 k` (pas `3 k`).
  /// Le `,0` superflu est retiré : `65 000` → `65 k`, `2 000 000` → `2 M`.
  static String formatCompact(num amount) {
    if (amount.abs() >= 1_000_000) {
      return '${_trimDecimal(amount / 1_000_000)} M XAF';
    }
    if (amount.abs() >= 1_000) {
      return '${_trimDecimal(amount / 1_000)} k XAF';
    }
    return format(amount);
  }

  /// 1 décimale, virgule FR, sans `,0` inutile.
  static String _trimDecimal(num v) {
    final s = v.toStringAsFixed(1);
    final trimmed = s.endsWith('.0') ? s.substring(0, s.length - 2) : s;
    return trimmed.replaceAll('.', ',');
  }
}
