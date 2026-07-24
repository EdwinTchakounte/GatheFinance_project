import 'package:flutter/foundation.dart';

import '../../../../core/error/failures.dart';
import '../../../../core/usecases/usecase.dart';
import '../repositories/auth_repository.dart';

@immutable
class ConfirmPasswordResetParams {
  const ConfirmPasswordResetParams({
    required this.email,
    required this.code,
    required this.newPassword,
  });

  final String email;
  final String code;
  final String newPassword;
}

/// Étape 2 du flow — valide l'OTP reçu par e-mail puis change le mot de
/// passe. Renvoie `null` en succès, ou un message d'erreur à afficher
/// (code faux, expiré, ou mot de passe rejeté par les validateurs Django).
class ConfirmPasswordReset
    extends UseCase<String?, ConfirmPasswordResetParams> {
  const ConfirmPasswordReset(this._repo);
  final AuthRepository _repo;

  @override
  Future<String?> call(ConfirmPasswordResetParams params) async {
    final email = params.email.trim();
    final code = params.code.trim();
    if (email.isEmpty || !email.contains('@')) {
      throw const ValidationFailure(
        'Adresse e-mail invalide.',
        field: 'email',
      );
    }
    if (code.length != 6 || int.tryParse(code) == null) {
      throw const ValidationFailure(
        'Le code doit contenir 6 chiffres.',
        field: 'code',
      );
    }
    if (params.newPassword.length < 4) {
      throw const ValidationFailure(
        'Mot de passe trop court (minimum 4 caractères).',
        field: 'new_password',
      );
    }
    return _repo.confirmPasswordReset(
      email: email,
      code: code,
      newPassword: params.newPassword,
    );
  }
}
