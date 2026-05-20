import 'package:flutter/foundation.dart';

/// Catégories d'événements pour lesquels l'utilisateur peut être notifié.
/// Alignées avec les hooks backend (apps_coop) : adhésion, épargne,
/// crédit, carnet, reconduction, sécurité.
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

/// Canaux de notification disponibles.
enum NotifChannel { push, email, sms }

extension NotifChannelLabel on NotifChannel {
  String get label => switch (this) {
        NotifChannel.push => 'Push',
        NotifChannel.email => 'Email',
        NotifChannel.sms => 'SMS',
      };
}

/// État global des préférences — une matrice Catégorie × Canal en bool.
/// Persisté localement via SharedPreferences (clé `notif_pref_<cat>_<chan>`).
@immutable
class NotificationPrefs {
  const NotificationPrefs(this.matrix);

  final Map<NotifCategory, Map<NotifChannel, bool>> matrix;

  /// Préférences par défaut — push partout, email pour les événements
  /// importants seulement, SMS uniquement sécurité.
  factory NotificationPrefs.defaults() {
    return NotificationPrefs({
      for (final cat in NotifCategory.values)
        cat: {
          NotifChannel.push: true,
          NotifChannel.email:
              cat == NotifCategory.credit || cat == NotifCategory.securite,
          NotifChannel.sms: cat == NotifCategory.securite,
        },
    });
  }

  bool isEnabled(NotifCategory cat, NotifChannel chan) =>
      matrix[cat]?[chan] ?? false;

  NotificationPrefs setEnabled(
    NotifCategory cat,
    NotifChannel chan,
    bool value,
  ) {
    final next = {
      for (final entry in matrix.entries) entry.key: {...entry.value},
    };
    next[cat]![chan] = value;
    return NotificationPrefs(next);
  }
}
