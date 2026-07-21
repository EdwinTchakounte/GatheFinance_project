import '../entities/member.dart';

/// Contrat de la couche data pour l'authentification — implémentation
/// dans `data/repositories/auth_repository_impl.dart`. Les usecases ne
/// connaissent que cette interface.
abstract class AuthRepository {
  /// Authentifie un membre. Lève `AuthFailure` si rejeté.
  Future<Member> signIn({required String email, required String password});

  /// Renvoie le membre courant (session vivante) ou `null`.
  Future<Member?> currentMember();

  /// Détruit la session locale.
  Future<void> signOut();

  /// Édite prenom/nom/phone du membre — renvoie l'entité à jour.
  Future<Member> updateProfile({
    required String prenom,
    required String nom,
    required String phone,
  });

  /// Charge/remplace la photo de profil (avatar) — renvoie l'entité à jour.
  Future<Member> updatePhoto(String filePath);

  /// Change le mot de passe ; `null` = succès, sinon message d'erreur affiché.
  Future<String?> changePassword({
    required String oldPassword,
    required String newPassword,
  });

  /// Demande l'envoi d'un OTP de réinitialisation à l'adresse fournie.
  /// Anti-énumération : succès systématique côté backend (réponse opaque)
  /// même si l'e-mail n'existe pas.
  Future<void> requestPasswordReset({required String email});

  /// Valide l'OTP et change le mot de passe. Renvoie un message d'erreur
  /// (`null` = succès) — l'UI distingue mauvais code vs mot de passe faible.
  Future<String?> confirmPasswordReset({
    required String email,
    required String code,
    required String newPassword,
  });
}
