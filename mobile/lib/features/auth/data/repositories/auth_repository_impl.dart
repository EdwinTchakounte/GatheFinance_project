import '../../../../core/error/exceptions.dart';
import '../../../../core/error/failures.dart';
import '../../domain/entities/member.dart';
import '../../domain/repositories/auth_repository.dart';
import '../datasources/auth_remote_datasource.dart';

/// Traduit les exceptions techniques (data) en `Failure` métier (domain).
/// Le domain ne sait rien de Dio ni de HTTP — il reçoit uniquement des
/// `Failure` levées.
class AuthRepositoryImpl implements AuthRepository {
  const AuthRepositoryImpl(this._remote);
  final AuthRemoteDataSource _remote;

  @override
  Future<Member> signIn({required String email, required String password}) async {
    try {
      return await _remote.signIn(email: email, password: password);
    } on CredentialsException catch (e) {
      throw AuthFailure(e.message);
    } on NetworkException catch (e) {
      throw NetworkFailure(e.message);
    } on ServerException catch (e) {
      throw UnexpectedFailure(e.message);
    }
  }

  @override
  Future<Member?> currentMember() async {
    try {
      return await _remote.currentMember();
    } on NetworkException {
      return null; // mode hors-ligne : pas connecté
    }
  }

  @override
  Future<void> signOut() => _remote.signOut();

  @override
  Future<Member> updateProfile({
    required String prenom,
    required String nom,
    required String phone,
  }) async {
    try {
      return await _remote.updateProfile(
        prenom: prenom,
        nom: nom,
        phone: phone,
      );
    } on CredentialsException catch (e) {
      throw AuthFailure(e.message);
    } on NetworkException catch (e) {
      throw NetworkFailure(e.message);
    } on ServerException catch (e) {
      throw ValidationFailure(e.message);
    }
  }

  @override
  Future<String?> changePassword({
    required String oldPassword,
    required String newPassword,
  }) async {
    try {
      return await _remote.changePassword(
        oldPassword: oldPassword,
        newPassword: newPassword,
      );
    } on NetworkException catch (e) {
      throw NetworkFailure(e.message);
    } on ServerException catch (e) {
      throw UnexpectedFailure(e.message);
    }
  }
}
