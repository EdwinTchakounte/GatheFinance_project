import 'package:flutter_test/flutter_test.dart';
import 'package:gathe_finance/core/usecases/usecase.dart';
import 'package:gathe_finance/features/auth/domain/repositories/auth_repository.dart';
import 'package:gathe_finance/features/auth/domain/usecases/sign_out.dart';
import 'package:mocktail/mocktail.dart';

class _MockRepo extends Mock implements AuthRepository {}

void main() {
  late _MockRepo repo;
  late SignOut useCase;

  setUp(() {
    repo = _MockRepo();
    useCase = SignOut(repo);
  });

  test('SignOut délègue au repository sans paramètre', () async {
    when(() => repo.signOut()).thenAnswer((_) async {});
    await useCase.call(const NoParams());
    verify(() => repo.signOut()).called(1);
    verifyNoMoreInteractions(repo);
  });
}
