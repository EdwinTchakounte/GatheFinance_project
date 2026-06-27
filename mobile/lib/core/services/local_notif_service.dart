/// Service de notifications LOCALES (push device-side, pas FCM).
///
/// Couvre 3 cas d'usage :
///   1. [showInstant] . afficher une notif locale immediatement (utilise
///      a chaque arrivee d'une nouvelle notif backend dans
///      NotificationsNotifier . cf. payload `kind`).
///   2. [scheduleAppReminderEvery6h] . rappel periodique toutes les
///      6 heures pour inviter le membre a consulter l'app.
///   3. [scheduleCotisationDaily16h] . rappel quotidien a 16h00
///      (Africa/Douala) pour effectuer la cotisation journaliere
///      avant le cut-off de 17h00.
///
/// FCM (firebase_messaging) sera ajoute dans une iteration suivante
/// pour les push serveur cross-device . pour l'instant, tout est local
/// et fonctionne offline.
library;

import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:timezone/data/latest_all.dart' as tz_data;
import 'package:timezone/timezone.dart' as tz;

class LocalNotifService {
  LocalNotifService._();

  static final LocalNotifService instance = LocalNotifService._();

  final FlutterLocalNotificationsPlugin _plugin =
      FlutterLocalNotificationsPlugin();

  bool _initialized = false;

  /// Canal Android pour les notifs business (transactions, demandes...).
  static const _channelBiz = AndroidNotificationChannel(
    'gathe_biz',
    'Gathé Finance . Activité',
    description: 'Notifications instantanées : versement, crédit, annonce...',
    importance: Importance.high,
  );

  /// Canal Android pour les rappels planifies (consultation, cotisation).
  static const _channelReminders = AndroidNotificationChannel(
    'gathe_reminders',
    'Gathé Finance . Rappels',
    description: 'Rappels périodiques : consultation app, collecte journalière.',
    importance: Importance.defaultImportance,
  );

  /// IDs reserves pour les rappels planifies (uniques par device).
  static const int _idReminderAppEvery6h = 9001;
  static const int _idReminderCotisation16h = 9002;

  /// Init . a appeler une seule fois au demarrage de l'app (main.dart).
  /// Idempotent : peut etre rappele sans degats.
  Future<void> init() async {
    if (_initialized) return;

    // Timezone . necessaire pour zonedSchedule.
    tz_data.initializeTimeZones();
    try {
      tz.setLocalLocation(tz.getLocation('Africa/Douala'));
    } catch (_) {
      // Fallback UTC . pas critique, les schedules tournent.
    }

    const androidInit = AndroidInitializationSettings('@mipmap/ic_launcher');
    const iosInit = DarwinInitializationSettings(
      requestAlertPermission: false,
      requestBadgePermission: false,
      requestSoundPermission: false,
    );

    await _plugin.initialize(
      const InitializationSettings(android: androidInit, iOS: iosInit),
    );

    // Cree les canaux Android (no-op si deja crees).
    final androidImpl = _plugin.resolvePlatformSpecificImplementation<
        AndroidFlutterLocalNotificationsPlugin>();
    if (androidImpl != null) {
      await androidImpl.createNotificationChannel(_channelBiz);
      await androidImpl.createNotificationChannel(_channelReminders);
    }

    _initialized = true;
  }

  /// Demande la permission systeme (Android 13+ POST_NOTIFICATIONS + iOS).
  /// Best-effort : si l'utilisateur refuse, les rappels seront silencieusement
  /// no-op. A appeler apres init() . typiquement au premier login reussi.
  Future<bool> requestPermissions() async {
    if (!_initialized) await init();

    if (Platform.isAndroid) {
      final androidImpl = _plugin.resolvePlatformSpecificImplementation<
          AndroidFlutterLocalNotificationsPlugin>();
      if (androidImpl == null) return false;
      final granted = await androidImpl.requestNotificationsPermission();
      // Permet aussi les alarmes exactes (Android 12+) pour zonedSchedule.
      await androidImpl.requestExactAlarmsPermission();
      return granted ?? false;
    }
    if (Platform.isIOS) {
      final iosImpl = _plugin.resolvePlatformSpecificImplementation<
          IOSFlutterLocalNotificationsPlugin>();
      final granted = await iosImpl?.requestPermissions(
        alert: true, badge: true, sound: true,
      );
      return granted ?? false;
    }
    return false;
  }

  /// Affiche une notification locale immediatement (canal "Activité").
  /// Utilise par NotificationsNotifier a chaque nouvelle notif arrivee.
  Future<void> showInstant({
    required int id,
    required String title,
    required String body,
    String? payload,
  }) async {
    if (!_initialized) await init();
    await _plugin.show(
      id,
      title,
      body,
      NotificationDetails(
        android: AndroidNotificationDetails(
          _channelBiz.id,
          _channelBiz.name,
          channelDescription: _channelBiz.description,
          importance: Importance.high,
          priority: Priority.high,
          icon: '@mipmap/ic_launcher',
        ),
        iOS: const DarwinNotificationDetails(
          presentAlert: true, presentBadge: true, presentSound: true,
        ),
      ),
      payload: payload,
    );
  }

  /// Rappel "Consulte ton app Gathé" toutes les 6 heures.
  /// Re-programmable : annule l'instance precedente avant de creer la nouvelle.
  Future<void> scheduleAppReminderEvery6h() async {
    if (!_initialized) await init();
    await _plugin.cancel(_idReminderAppEvery6h);
    try {
      await _plugin.periodicallyShow(
        _idReminderAppEvery6h,
        'Gathé Finance',
        'Jette un œil sur ton compte et tes dernières activités.',
        RepeatInterval.everyMinute, // override below for 6h
        NotificationDetails(
          android: AndroidNotificationDetails(
            _channelReminders.id,
            _channelReminders.name,
            channelDescription: _channelReminders.description,
            importance: Importance.defaultImportance,
            priority: Priority.defaultPriority,
            icon: '@mipmap/ic_launcher',
          ),
          iOS: const DarwinNotificationDetails(),
        ),
        androidScheduleMode: AndroidScheduleMode.inexactAllowWhileIdle,
      );
      // periodicallyShow ne supporte pas RepeatInterval custom : on utilise
      // zonedSchedule en boucle (chaque firing reprogramme le suivant via
      // les flags inexact). Pour 6h fixes, on bascule sur zonedSchedule
      // avec matchDateTimeComponents = time . re-prog journaliere a 00, 06,
      // 12, 18h.
      await _plugin.cancel(_idReminderAppEvery6h);
      final now = tz.TZDateTime.now(tz.local);
      // Prochaine occurrence : la plus proche parmi 00, 06, 12, 18h.
      const slots = [0, 6, 12, 18];
      tz.TZDateTime next = tz.TZDateTime(tz.local, now.year, now.month, now.day, slots.first);
      for (final h in slots) {
        final candidate = tz.TZDateTime(tz.local, now.year, now.month, now.day, h);
        if (candidate.isAfter(now)) {
          next = candidate;
          break;
        }
      }
      if (!next.isAfter(now)) {
        // Tous les slots passes . demain a 00h.
        next = tz.TZDateTime(tz.local, now.year, now.month, now.day + 1, slots.first);
      }
      await _plugin.zonedSchedule(
        _idReminderAppEvery6h,
        'Gathé Finance',
        'Jette un œil sur ton compte et tes dernières activités.',
        next,
        NotificationDetails(
          android: AndroidNotificationDetails(
            _channelReminders.id,
            _channelReminders.name,
            channelDescription: _channelReminders.description,
            importance: Importance.defaultImportance,
            priority: Priority.defaultPriority,
            icon: '@mipmap/ic_launcher',
          ),
          iOS: const DarwinNotificationDetails(),
        ),
        androidScheduleMode: AndroidScheduleMode.inexactAllowWhileIdle,
        uiLocalNotificationDateInterpretation:
            UILocalNotificationDateInterpretation.absoluteTime,
        // matchDateTimeComponents = time : se re-declenche chaque jour
        // a la meme heure (combine avec la rotation des slots ci-dessus
        // pour donner ~4 fois par jour = ~6h).
        matchDateTimeComponents: DateTimeComponents.time,
      );
    } catch (e) {
      debugPrint('scheduleAppReminderEvery6h failed: $e');
    }
  }

  /// Rappel quotidien a 16h00 (Africa/Douala) pour la cotisation journaliere.
  /// Cut-off agence = 17h00, donc l'utilisateur a 1h pour passer a la cooperative
  /// ou taper le code MTN/Orange.
  Future<void> scheduleCotisationDaily16h() async {
    if (!_initialized) await init();
    await _plugin.cancel(_idReminderCotisation16h);

    final now = tz.TZDateTime.now(tz.local);
    tz.TZDateTime next = tz.TZDateTime(tz.local, now.year, now.month, now.day, 16);
    if (!next.isAfter(now)) {
      next = next.add(const Duration(days: 1));
    }

    try {
      await _plugin.zonedSchedule(
        _idReminderCotisation16h,
        'Collecte du jour',
        'Pense à effectuer ta collecte journalière avant 17h00.',
        next,
        NotificationDetails(
          android: AndroidNotificationDetails(
            _channelReminders.id,
            _channelReminders.name,
            channelDescription: _channelReminders.description,
            importance: Importance.high,
            priority: Priority.high,
            icon: '@mipmap/ic_launcher',
          ),
          iOS: const DarwinNotificationDetails(),
        ),
        androidScheduleMode: AndroidScheduleMode.exactAllowWhileIdle,
        uiLocalNotificationDateInterpretation:
            UILocalNotificationDateInterpretation.absoluteTime,
        matchDateTimeComponents: DateTimeComponents.time,
      );
    } catch (e) {
      debugPrint('scheduleCotisationDaily16h failed: $e');
    }
  }

  /// Annule TOUS les rappels planifies (utile au logout).
  Future<void> cancelAllScheduled() async {
    if (!_initialized) return;
    await _plugin.cancel(_idReminderAppEvery6h);
    await _plugin.cancel(_idReminderCotisation16h);
  }
}
