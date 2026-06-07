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
}
