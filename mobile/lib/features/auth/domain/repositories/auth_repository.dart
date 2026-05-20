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
}
