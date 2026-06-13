import 'package:flutter/foundation.dart';

import '../../../../core/error/failures.dart';
import '../../../../core/usecases/usecase.dart';
import '../repositories/auth_repository.dart';

@immutable
class RequestPasswordResetParams {
  const RequestPasswordResetParams({required this.email});
  final String email;
}

/// Étape 1 du flow "mot de passe oublié" — déclenche l'envoi d'un OTP par
/// e-mail. La réponse backend est opaque (anti-énumération) : succès même
/// si l'e-mail n'existe pas. L'UI affiche systématiquement "Si un compte
/// existe, un code a été envoyé".
class RequestPasswordReset
    extends UseCase<void, RequestPasswordResetParams> {
  const RequestPasswordReset(this._repo);
  final AuthRepository _repo;

  @override
  Future<void> call(RequestPasswordResetParams params) async {
    final email = params.email.trim();
    if (email.isEmpty || !email.contains('@')) {
      throw const ValidationFailure(
        'Adresse e-mail invalide.',
        field: 'email',
      );
    }
    await _repo.requestPasswordReset(email: email);
  }
}
