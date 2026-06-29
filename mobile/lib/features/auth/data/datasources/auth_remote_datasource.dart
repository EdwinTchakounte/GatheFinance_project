import '../../domain/entities/member.dart';

/// Contrat de la source distante. Deux implémentations :
///   - `AuthMockDataSource`  → en mémoire, pour les tests / dev sans backend
///   - `AuthDioDataSource`   → vrais appels `/api/v1/auth/*` (prod / staging)
abstract class AuthRemoteDataSource {
  /// Lève `CredentialsException` si l'auth échoue ; `ServerException` /
  /// `NetworkException` pour le reste.
  Future<Member> signIn({required String email, required String password});

  Future<Member?> currentMember();

  Future<void> signOut();

  /// PATCH /members/me/ — édite prenom/nom/phone. Renvoie le membre à jour.
  Future<Member> updateProfile({
    required String prenom,
    required String nom,
    required String phone,
  });

  /// POST /auth/change-password/ — modifie le mot de passe.
  /// Renvoie `null` en succès, une chaîne d'erreur sinon (affichage UI).
  Future<String?> changePassword({
    required String oldPassword,
    required String newPassword,
  });

  /// POST /auth/password-reset/request/ — déclenche l'envoi d'un OTP.
  Future<void> requestPasswordReset({required String email});

  /// POST /auth/password-reset/confirm/ — valide l'OTP + change le mot de passe.
  /// `null` = succès, sinon un message d'erreur à afficher (code faux, mdp faible, …).
  Future<String?> confirmPasswordReset({
    required String email,
    required String code,
    required String newPassword,
  });

  /// GET /auth/setup-password/verify/?token=XXX — valide un token de
  /// definition initiale (PWD Option B). Renvoie email mask + expiry si OK,
  /// jette en cas d'invalide/expire.
  Future<PasswordSetupTokenInfo> verifySetupToken(String token);

  /// POST /auth/setup-password/confirm/ — pose le mot de passe initial.
  /// `null` = succes, sinon un message d'erreur a afficher.
  Future<String?> confirmPasswordSetup({
    required String token,
    required String newPassword,
  });
}

/// Resultat de verify : email mask (pour confirmation visuelle) + date d'expiry.
class PasswordSetupTokenInfo {
  const PasswordSetupTokenInfo({
    required this.emailMask,
    required this.expiresAt,
  });

  final String emailMask;
  final DateTime expiresAt;
}
