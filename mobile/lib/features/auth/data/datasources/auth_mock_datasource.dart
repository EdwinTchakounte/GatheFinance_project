import '../../../../core/error/exceptions.dart';
import '../../domain/entities/member.dart';
import 'auth_remote_datasource.dart';

/// Source de données en mémoire — substituée par `AuthDioDataSource` au switch
/// sur l'API. Aucune persistance, juste une variable d'instance.
class AuthMockDataSource implements AuthRemoteDataSource {
  Member? _session;

  static final _fixtureMember = Member(
    id: 1,
    numeroMembre: 'GF-2026-0001',
    prenom: 'Jean',
    nom: 'Kamga',
    email: 'jean.kamga@test.local',
    phone: '+237 6 99 11 22 33',
    statut: MemberStatus.actif,
    dateAdhesion: DateTime(2026, 3, 12),
  );

  @override
  Future<Member> signIn({required String email, required String password}) async {
    await Future<void>.delayed(const Duration(milliseconds: 700));
    if (password.length < 4) {
      throw const CredentialsException('Identifiants invalides.');
    }
    _session = _fixtureMember;
    return _session!;
  }

  @override
  Future<Member?> currentMember() async {
    await Future<void>.delayed(const Duration(milliseconds: 80));
    return _session;
  }

  @override
  Future<void> signOut() async {
    _session = null;
  }
}
