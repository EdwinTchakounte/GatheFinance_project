import 'package:flutter/material.dart';

/// Navigator key racine — passé à GoRouter via `navigatorKey`. Permet
/// de pousser une page depuis n'importe quel datasource/service qui
/// n'a pas de `BuildContext` à disposition (typiquement le
/// `TaraCheckoutLauncher` appelé depuis un Dio interceptor).
final rootNavigatorKey = GlobalKey<NavigatorState>(debugLabel: 'root');
