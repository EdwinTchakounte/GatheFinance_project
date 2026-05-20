/// Erreurs métier remontées par le domain → consommées par la presentation.
///
/// La couche `data` lève des `Exception` techniques (réseau, parsing) que les
/// repository impls *traduisent* en `Failure` métier avant de propager.
/// La présentation ne connaît QUE les `Failure`.
sealed class Failure implements Exception {
  const Failure(this.message);
  final String message;

  @override
  String toString() => message;
}

/// Identifiants invalides, compte verrouillé, session expirée…
class AuthFailure extends Failure {
  const AuthFailure(super.message);
}

/// Validation côté serveur (champ manquant, hors plage…).
class ValidationFailure extends Failure {
  const ValidationFailure(super.message, {this.field});
  final String? field;
}

/// Réseau / timeout / 5xx.
class NetworkFailure extends Failure {
  const NetworkFailure([super.message = 'Connexion impossible.']);
}

/// Erreur métier générique (statut incompatible, plafond dépassé…).
class BusinessFailure extends Failure {
  const BusinessFailure(super.message);
}

/// Erreur inconnue (catch-all). Toujours préférer une sous-classe explicite.
class UnexpectedFailure extends Failure {
  const UnexpectedFailure([super.message = 'Une erreur inattendue est survenue.']);
}
