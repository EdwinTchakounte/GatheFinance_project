import 'package:flutter/foundation.dart';

/// Catégories d'événements pour lesquelles l'utilisateur peut recevoir un
/// **push**. Alignées 1-1 avec le backend (`NotifCategory.name` == clé serveur).
enum NotifCategory {
  epargne,
  credit,
  carnet,
  reconduction,
  securite,
}

extension NotifCategoryLabel on NotifCategory {
  String get label => switch (this) {
        NotifCategory.epargne => 'Épargne',
        NotifCategory.credit => 'Crédit',
        NotifCategory.carnet => 'Carnet',
        NotifCategory.reconduction => 'Reconduction',
        NotifCategory.securite => 'Sécurité',
      };

  String get subtitle => switch (this) {
        NotifCategory.epargne =>
          'Dépôts validés, intérêts crédités, alertes solde.',
        NotifCategory.credit =>
          'Demande, décision comité, décaissement, échéances.',
        NotifCategory.carnet => 'Commande, retrait à l\'agence.',
        NotifCategory.reconduction => 'Comité, frais à régler, validation.',
        NotifCategory.securite =>
          'Connexions, changements de mot de passe, accès suspects.',
      };
}

/// Préférences de notification **push** par catégorie (opt-out). Miroir de
/// l'endpoint backend `/notifications/preferences/` — une catégorie absente
/// est considérée activée.
@immutable
class NotificationPrefs {
  const NotificationPrefs(this.push);

  final Map<NotifCategory, bool> push;

  /// Tout activé (défaut opt-out).
  factory NotificationPrefs.defaults() =>
      NotificationPrefs({for (final c in NotifCategory.values) c: true});

  /// Depuis la map serveur `{ "epargne": true, ... }`.
  factory NotificationPrefs.fromApi(Map<String, bool> map) => NotificationPrefs(
        {for (final c in NotifCategory.values) c: map[c.name] ?? true},
      );

  bool isEnabled(NotifCategory cat) => push[cat] ?? true;

  /// Vers la map serveur `{ "epargne": true, ... }`.
  Map<String, bool> toApi() =>
      {for (final e in push.entries) e.key.name: e.value};

  NotificationPrefs setEnabled(NotifCategory cat, bool value) {
    final next = {...push};
    next[cat] = value;
    return NotificationPrefs(next);
  }
}
