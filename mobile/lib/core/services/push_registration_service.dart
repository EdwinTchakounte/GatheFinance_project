import 'dart:io' show Platform;

import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../features/notifications/domain/repositories/notifications_repository.dart';
import '../di/providers.dart';

/// Fournit le jeton push de l'appareil.
///
/// **Base posée pour FCM** : l'implémentation par défaut ([NoopPushTokenProvider])
/// renvoie `null` (aucun SDK push embarqué pour l'instant — pas de
/// `google-services.json`). Quand FCM sera branché, il suffira de fournir une
/// implémentation `FcmPushTokenProvider` qui appelle
/// `FirebaseMessaging.instance.getToken()` et d'override
/// [pushTokenProvider] — le reste de la plomberie (enregistrement backend)
/// est déjà en place.
abstract class PushTokenProvider {
  Future<String?> getToken();
}

class NoopPushTokenProvider implements PushTokenProvider {
  const NoopPushTokenProvider();

  @override
  Future<String?> getToken() async => null;
}

final pushTokenProvider = Provider<PushTokenProvider>(
  (ref) => const NoopPushTokenProvider(),
);

/// Service d'enregistrement du jeton push auprès du backend.
///
/// - [syncToken] : à appeler après le login → enregistre le jeton (si dispo).
/// - [clearToken] : à appeler au logout → désenregistre le jeton courant.
///
/// Tout est best-effort : en l'absence de jeton (FCM non branché) ou en cas
/// d'erreur réseau, on ne lève jamais — la fonctionnalité reste dormante.
class PushRegistrationService {
  PushRegistrationService(this._repo, this._tokenProvider);

  final NotificationsRepository _repo;
  final PushTokenProvider _tokenProvider;
  String? _lastToken;

  String get _platform {
    if (kIsWeb) return 'web';
    if (Platform.isIOS) return 'ios';
    return 'android';
  }

  Future<void> syncToken() async {
    try {
      final token = await _tokenProvider.getToken();
      if (token == null || token.isEmpty) return;
      await _repo.registerDevice(token, platform: _platform);
      _lastToken = token;
    } catch (_) {
      // Push dormant — on n'interrompt jamais le flux applicatif.
    }
  }

  Future<void> clearToken() async {
    try {
      final token = _lastToken ?? await _tokenProvider.getToken();
      if (token == null || token.isEmpty) return;
      await _repo.unregisterDevice(token);
      _lastToken = null;
    } catch (_) {
      // idem — best-effort.
    }
  }
}

final pushRegistrationServiceProvider = Provider<PushRegistrationService>(
  (ref) => PushRegistrationService(
    ref.watch(notificationsRepositoryProvider),
    ref.watch(pushTokenProvider),
  ),
);
