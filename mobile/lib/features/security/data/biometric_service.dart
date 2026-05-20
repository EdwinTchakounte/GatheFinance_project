import 'package:flutter/services.dart';
import 'package:local_auth/local_auth.dart';
import 'package:local_auth_android/local_auth_android.dart';

/// Libellés localisés (EN/FR) pour le prompt biométrique système.
/// Construits côté UI à partir de [AppL10n].
class BiometricLabels {
  const BiometricLabels({
    required this.reason,
    required this.signInTitle,
    required this.hint,
    required this.cancelButton,
  });

  final String reason;
  final String signInTitle;
  final String hint;
  final String cancelButton;
}

/// Encapsule `local_auth` : disponibilité du capteur + prompt biométrique.
///
/// L'empreinte/visage ne « déverrouille » pas un secret stocké : c'est une
/// vérification de présence locale. Combinée au PIN (toujours requis en repli),
/// elle offre un accès rapide à l'app — comme les apps bancaires.
class BiometricService {
  BiometricService([LocalAuthentication? auth])
      : _auth = auth ?? LocalAuthentication();

  final LocalAuthentication _auth;

  /// Le device a-t-il un capteur biométrique exploitable (empreinte/visage)
  /// ET au moins une empreinte enrôlée ?
  Future<bool> isAvailable() async {
    try {
      final supported = await _auth.isDeviceSupported();
      if (!supported) return false;
      final canCheck = await _auth.canCheckBiometrics;
      if (!canCheck) return false;
      final enrolled = await _auth.getAvailableBiometrics();
      return enrolled.isNotEmpty;
    } on PlatformException {
      return false;
    }
  }

  /// Lance le prompt système. Retourne `true` si l'utilisateur s'est authentifié.
  /// Les libellés sont fournis par l'UI (déjà localisés EN/FR).
  Future<bool> authenticate({
    required String reason,
    required String signInTitle,
    required String hint,
    required String cancelButton,
  }) async {
    try {
      return await _auth.authenticate(
        localizedReason: reason,
        options: const AuthenticationOptions(
          biometricOnly: true,
          stickyAuth: true,
          useErrorDialogs: true,
        ),
        authMessages: [
          AndroidAuthMessages(
            signInTitle: signInTitle,
            biometricHint: hint,
            cancelButton: cancelButton,
          ),
        ],
      );
    } on PlatformException {
      return false;
    }
  }
}
