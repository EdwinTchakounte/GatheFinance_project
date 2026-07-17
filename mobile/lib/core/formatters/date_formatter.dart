import 'package:intl/intl.dart';

/// Formatage de dates **localisé**.
///
/// La locale courante est portée par [Intl.defaultLocale] (posée par l'app à
/// chaque changement de langue, cf. `app.dart`). On (re)construit les
/// `DateFormat` à chaque appel plutôt que de les mettre en cache statique :
/// un switch de langue à chaud est ainsi pris en compte immédiatement.
class AppDateFormatter {
  AppDateFormatter._();

  /// Locale intl à utiliser. `fr` est mappé sur `fr_FR` (données chargées au
  /// boot) ; toute autre langue retombe sur son code (`en`, …).
  static String get _locale {
    final l = Intl.defaultLocale;
    if (l == null || l.isEmpty) return 'fr_FR';
    if (l.startsWith('fr')) return 'fr_FR';
    return l;
  }

  static String short(DateTime date) =>
      DateFormat('dd MMM', _locale).format(date);
  static String long(DateTime date) =>
      DateFormat('d MMMM yyyy', _locale).format(date);
  static String withTime(DateTime date) =>
      DateFormat('dd MMM · HH:mm', _locale).format(date);
}
