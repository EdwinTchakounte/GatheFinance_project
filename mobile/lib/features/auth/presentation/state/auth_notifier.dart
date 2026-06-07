import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/di/providers.dart';
import '../../../../core/error/failures.dart';
import '../../../../core/usecases/usecase.dart';
import '../../domain/entities/member.dart';
import '../../domain/usecases/sign_in.dart';

/// État auth de la presentation. Ne dépend QUE des usecases / repository
/// (zéro référence à Dio / HTTP).
class AuthNotifier extends AsyncNotifier<Member?> {
  late final SignIn _signIn = ref.read(signInUseCaseProvider);
  late final get_current = ref.read(getCurrentMemberUseCaseProvider);
  late final _signOut = ref.read(signOutUseCaseProvider);

  @override
  Future<Member?> build() => get_current.call(const NoParams());

  Future<void> signIn({required String email, required String password}) async {
    state = const AsyncValue.loading();
    state = await AsyncValue.guard(
      () => _signIn.call(SignInParams(email: email, password: password)),
    );
  }

  Future<void> signOut() async {
    await _signOut.call(const NoParams());
    state = const AsyncValue.data(null);
  }

  /// Met à jour les champs éditables du membre connecté via
  /// `PATCH /api/v1/members/me/` (en mocks : mutation locale).
  Future<void> updateProfile({
    required String prenom,
    required String nom,
    required String phone,
  }) async {
    final current = state.valueOrNull;
    if (current == null) return;
    final repo = ref.read(authRepositoryProvider);
    try {
      final updated = await repo.updateProfile(
        prenom: prenom,
        nom: nom,
        phone: phone,
      );
      state = AsyncValue.data(updated);
    } on Failure {
      // Garde le state actuel — l'UI gère son propre toast d'erreur.
      rethrow;
    }
  }

  /// Modifie le mot de passe via `POST /api/v1/auth/change-password/`.
  /// Renvoie `null` en cas de succès, une chaîne d'erreur sinon
  /// (pour affichage UI). Les erreurs réseau remontent en exception.
  Future<String?> changePassword({
    required String oldPassword,
    required String newPassword,
  }) async {
    final repo = ref.read(authRepositoryProvider);
    return repo.changePassword(
      oldPassword: oldPassword,
      newPassword: newPassword,
    );
  }
}

final authProvider = AsyncNotifierProvider<AuthNotifier, Member?>(AuthNotifier.new);
