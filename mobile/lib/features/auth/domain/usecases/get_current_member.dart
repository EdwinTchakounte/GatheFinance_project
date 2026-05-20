import '../../../../core/usecases/usecase.dart';
import '../entities/member.dart';
import '../repositories/auth_repository.dart';

class GetCurrentMember extends UseCase<Member?, NoParams> {
  const GetCurrentMember(this._repo);
  final AuthRepository _repo;

  @override
  Future<Member?> call(NoParams params) => _repo.currentMember();
}
