import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/date_symbol_data_local.dart';

import 'app/app.dart';
import 'core/di/providers.dart';
import 'core/network/api_client.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  // Préchargement des données de localisation FR pour intl.
  await initializeDateFormatting('fr_FR');

  // Status bar transparente — le thème prendra le relais ensuite.
  SystemChrome.setSystemUIOverlayStyle(const SystemUiOverlayStyle(
    statusBarColor: Colors.transparent,
    statusBarIconBrightness: Brightness.dark,
  ),);

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
