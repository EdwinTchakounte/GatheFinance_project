import 'dart:async';

import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/date_symbol_data_local.dart';

import 'app/app.dart';
import 'core/di/providers.dart';
import 'core/network/api_client.dart';
import 'core/services/local_notif_service.dart';
import 'firebase_options.dart';

/// Handler des messages push reçus quand l'app est en fond/fermée. Il tourne
/// dans un isolate séparé → Firebase doit y être ré-initialisé. L'OS affiche
/// déjà la notification (bloc `notification`), ce handler ne traite que `data`.
@pragma('vm:entry-point')
Future<void> _fcmBackgroundHandler(RemoteMessage message) async {
  try {
    await Firebase.initializeApp(options: DefaultFirebaseOptions.currentPlatform);
  } catch (_) {
    // best-effort.
  }
}

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  // Préchargement des données de localisation FR pour intl.
  await initializeDateFormatting('fr_FR');

  // Firebase + notifications push (FCM). Best-effort : n'empêche jamais le boot.
  try {
    await Firebase.initializeApp(options: DefaultFirebaseOptions.currentPlatform);
    FirebaseMessaging.onBackgroundMessage(_fcmBackgroundHandler);
    // App au premier plan : Android n'affiche rien tout seul → on pousse une
    // notification locale via le canal métier existant.
    FirebaseMessaging.onMessage.listen((message) {
      final n = message.notification;
      if (n == null) return;
      LocalNotifService.instance.showInstant(
        id: message.hashCode & 0x7fffffff,
        title: n.title ?? 'GATHE Finance',
        body: n.body ?? '',
        payload: (message.data['lien'] ?? message.data['type']) as String?,
      );
    });
  } catch (_) {
    // Firebase indisponible (build sans google-services / test) → push dormant.
  }

  // Status bar transparente — le thème prendra le relais ensuite.
  SystemChrome.setSystemUIOverlayStyle(const SystemUiOverlayStyle(
    statusBarColor: Colors.transparent,
    statusBarIconBrightness: Brightness.dark,
  ),);

  // Notifications LOCALES . on init SANS bloquer le boot.
  // requestPermissions() peut bloquer plusieurs secondes (dialog Android)
  // et schedule* peut bloquer sur certains devices, donc on fire-and-forget
  // dans un microtask separe . runApp() peut continuer immediatement.
  // Les permissions seront demandees + schedules armes une fois l'UI montee.
  unawaited(Future.microtask(() async {
    try {
      final notifSvc = LocalNotifService.instance;
      await notifSvc.init();
      await notifSvc.requestPermissions();
      await notifSvc.scheduleAppReminderEvery6h();
      await notifSvc.scheduleCotisationDaily16h();
    } catch (_) {
      // Best-effort . echec d'init notifs ne bloque jamais l'app.
    }
  }),);

  // Initialise le client HTTP (cookies persistants). Toujours requis — les
  // datasources mockées ont été supprimées en 2026-06 (chemins prod only).
  final apiClient = await ApiClient.create();

  runApp(
    ProviderScope(
      overrides: [apiClientProvider.overrideWithValue(apiClient)],
      child: const GatheApp(),
    ),
  );
}
