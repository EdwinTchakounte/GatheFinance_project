import 'package:intl/intl.dart';

class AppDateFormatter {
  AppDateFormatter._();

  static final _short = DateFormat('dd MMM', 'fr_FR');
  static final _long = DateFormat('d MMMM yyyy', 'fr_FR');
  static final _withTime = DateFormat('dd MMM · HH:mm', 'fr_FR');

  static String short(DateTime date) => _short.format(date);
  static String long(DateTime date) => _long.format(date);
  static String withTime(DateTime date) => _withTime.format(date);
}
