/// Base contract for every use case.
///
/// Convention :
///   - Une instance de `UseCase` représente **une intention métier**.
///   - On l'appelle via `useCase(params)` (l'opérateur `call`).
///   - Le retour est `Future<Type>`. Les erreurs métier sont levées sous
///     forme de `Failure` (`core/error/failures.dart`).
///
/// Utilisez `NoParams` quand l'action ne prend pas d'argument :
///   `class GetCurrentMember extends UseCase<Member?, NoParams> { ... }`
abstract class UseCase<Type, Params> {
  const UseCase();
  Future<Type> call(Params params);
}

/// Marqueur « pas de paramètres » — évite `void` qui n'est pas compositionnel.
class NoParams {
  const NoParams();
}
