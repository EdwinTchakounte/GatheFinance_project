import '../../domain/entities/member.dart';

/// Contrat de la source distante (sera implémenté par un `AuthDioDataSource`
/// le jour de la bascule sur l'API). En attendant, seul `AuthMockDataSource`
/// existe.
abstract class AuthRemoteDataSource {
  /// Lève `CredentialsException` si l'auth échoue ; `ServerException` /
  /// `NetworkException` pour le reste.
  Future<Member> signIn({required String email, required String password});

  Future<Member?> currentMember();

  Future<void> signOut();
}
