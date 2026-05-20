import 'package:flutter_test/flutter_test.dart';
import 'package:gathe_finance/core/usecases/usecase.dart';
import 'package:gathe_finance/features/auth/domain/entities/member.dart';
import 'package:gathe_finance/features/auth/domain/repositories/auth_repository.dart';
import 'package:gathe_finance/features/auth/domain/usecases/get_current_member.dart';
import 'package:mocktail/mocktail.dart';

import '../../../../helpers/fixtures.dart';

class _MockRepo extends Mock implements AuthRepository {}

void main() {
  late _MockRepo repo;
  late GetCurrentMember useCase;

  setUp(() {
    repo = _MockRepo();
    useCase = GetCurrentMember(repo);
  });

  test('renvoie le membre courant', () async {
    final m = Fixtures.member();
    when(() => repo.currentMember()).thenAnswer((_) async => m);
    expect(await useCase.call(const NoParams()), m);
  });

  test('renvoie null quand pas de session', () async {
    when(() => repo.currentMember()).thenAnswer((_) async => null);
    expect(await useCase.call(const NoParams()), isNull);
  });
}
