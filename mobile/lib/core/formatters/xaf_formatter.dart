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
  static String formatCompact(num amount) {
    if (amount.abs() >= 1_000_000) {
      return '${(amount / 1_000_000).toStringAsFixed(1).replaceAll('.', ',')} M XAF';
    }
    if (amount.abs() >= 1_000) {
      return '${(amount / 1_000).toStringAsFixed(0)} k XAF';
    }
    return format(amount);
  }
}
