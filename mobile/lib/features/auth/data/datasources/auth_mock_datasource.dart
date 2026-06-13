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

  @override
  Future<Member> updateProfile({
    required String prenom,
    required String nom,
    required String phone,
  }) async {
    await Future<void>.delayed(const Duration(milliseconds: 600));
    final current = _session ?? _fixtureMember;
    _session = current.copyWith(
      prenom: prenom.trim(),
      nom: nom.trim(),
      phone: phone.trim(),
    );
    return _session!;
  }

  @override
  Future<String?> changePassword({
    required String oldPassword,
    required String newPassword,
  }) async {
    await Future<void>.delayed(const Duration(milliseconds: 700));
    // Convention historique du mock : ancien mot de passe attendu = 'test1234'.
    if (oldPassword != 'test1234') {
      return 'Ancien mot de passe incorrect.';
    }
    if (newPassword.length < 8) {
      return 'Le nouveau mot de passe doit faire au moins 8 caractères.';
    }
    return null;
  }

  @override
  Future<void> requestPasswordReset({required String email}) async {
    // Mock — no-op : pas d'envoi d'e-mail en mode démo.
    await Future<void>.delayed(const Duration(milliseconds: 400));
  }

  @override
  Future<String?> confirmPasswordReset({
    required String email,
    required String code,
    required String newPassword,
  }) async {
    await Future<void>.delayed(const Duration(milliseconds: 400));
    // Convention mock : code '000000' = succès.
    if (code != '000000') return 'Code invalide ou expiré.';
    if (newPassword.length < 8) {
      return 'Le nouveau mot de passe doit faire au moins 8 caractères.';
    }
    return null;
  }
}
