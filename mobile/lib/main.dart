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

  // Notifications LOCALES (push device-side, pas FCM). Init + permissions
  // systeme + reprogrammation des 2 rappels recurrents :
  //   . Consultation app : ~toutes les 6h (slots 00/06/12/18h)
  //   . Cotisation journaliere : tous les jours a 16h00 (avant cut-off 17h)
  // Best-effort . un echec ici ne bloque pas le boot.
  try {
    final notifSvc = LocalNotifService.instance;
    await notifSvc.init();
    await notifSvc.requestPermissions();
    await notifSvc.scheduleAppReminderEvery6h();
    await notifSvc.scheduleCotisationDaily16h();
  } catch (_) {
    // Logger central pas encore initialise . on absorbe.
  }

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
