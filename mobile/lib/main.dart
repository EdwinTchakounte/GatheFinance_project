import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/date_symbol_data_local.dart';

import 'app/app.dart';
import 'core/di/providers.dart';
import 'core/network/api_client.dart';
import 'core/services/local_notif_service.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  // Préchargement des données de localisation FR pour intl.
  await initializeDateFormatting('fr_FR');

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
  Future.microtask(() async {
    try {
      final notifSvc = LocalNotifService.instance;
      await notifSvc.init();
      await notifSvc.requestPermissions();
      await notifSvc.scheduleAppReminderEvery6h();
      await notifSvc.scheduleCotisationDaily16h();
    } catch (_) {
      // Best-effort . echec d'init notifs ne bloque jamais l'app.
    }
  });

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
