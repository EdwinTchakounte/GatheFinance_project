import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/date_symbol_data_local.dart';

import 'app/app.dart';
import 'core/di/providers.dart';
import 'core/network/api_client.dart';
import 'core/network/api_config.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  // Préchargement des données de localisation FR pour intl.
  await initializeDateFormatting('fr_FR');

  // Status bar transparente — le thème prendra le relais ensuite.
  SystemChrome.setSystemUIOverlayStyle(const SystemUiOverlayStyle(
    statusBarColor: Colors.transparent,
    statusBarIconBrightness: Brightness.dark,
  ));

  // Initialise le client HTTP (cookies persistants) — sauf en mode mocks
  // (--dart-define=USE_MOCKS=true) où aucune connexion réseau n'est tentée.
  final overrides = <Override>[];
  if (!ApiConfig.useMocks) {
    final apiClient = await ApiClient.create();
    overrides.add(apiClientProvider.overrideWithValue(apiClient));
  }

  runApp(
    ProviderScope(
      overrides: overrides,
      child: const GatheApp(),
    ),
  );
}
