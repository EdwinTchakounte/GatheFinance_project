import 'package:flutter/foundation.dart';

enum NotifKind { savings, loan, payment, lender, announcement, support, system }

@immutable
class AppNotification {
  const AppNotification({
    required this.id,
    required this.kind,
    required this.title,
    required this.body,
    required this.createdAt,
    this.read = false,
  });

  final int id;
  final NotifKind kind;
  final String title;
  final String body;
  final DateTime createdAt;
  final bool read;
}
