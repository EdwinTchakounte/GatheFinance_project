import '../../../../core/usecases/usecase.dart';
import '../../../forms/domain/entities/form_schema.dart';
import '../repositories/loans_repository.dart';

/// CH-5 — Récupère le FormSchema actif pour le formulaire de demande de crédit.
///
/// Renvoie `null` si aucun schéma actif n'est défini côté admin — l'UI rend
/// alors uniquement les champs hardcoded du sheet (mode legacy).
class GetActiveLoanRequestSchema extends UseCase<FormSchema?, NoParams> {
  const GetActiveLoanRequestSchema(this._repo);
  final LoansRepository _repo;

  @override
  Future<FormSchema?> call(NoParams params) =>
      _repo.getActiveLoanRequestSchema();
}
