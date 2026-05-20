import 'package:flutter/foundation.dart';

import '../../../../core/usecases/usecase.dart';
import '../entities/member.dart';
import '../repositories/auth_repository.dart';

@immutable
class SignInParams {
  const SignInParams({required this.email, required this.password});
  final String email;
  final String password;
}

/// Authentifie le membre et renvoie son entité métier.
/// Lève `AuthFailure` (ou autre `Failure`) en cas d'échec.
class SignIn extends UseCase<Member, SignInParams> {
  const SignIn(this._repo);
  final AuthRepository _repo;

  @override
  Future<Member> call(SignInParams params) {
    return _repo.signIn(email: params.email, password: params.password);
  }
}
