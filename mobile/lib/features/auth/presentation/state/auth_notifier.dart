import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/di/providers.dart';
import '../../../../core/usecases/usecase.dart';
import '../../domain/entities/member.dart';
import '../../domain/usecases/sign_in.dart';

/// État auth de la presentation. Ne dépend QUE des usecases (zéro
/// référence à `AuthRepository` ou à la couche data).
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

  /// Met à jour les champs éditables du membre connecté.
  /// Mock-only : mutation locale du state, pas d'appel backend (à brancher
  /// via un usecase `UpdateMemberProfile` quand l'API existera).
  Future<void> updateProfile({
    required String prenom,
    required String nom,
    required String phone,
  }) async {
    final current = state.valueOrNull;
    if (current == null) return;
    // Simule la latence d'un PATCH /members/me/
    await Future<void>.delayed(const Duration(milliseconds: 600));
    state = AsyncValue.data(
      current.copyWith(prenom: prenom.trim(), nom: nom.trim(), phone: phone.trim()),
    );
  }

  /// Change le mot de passe — mock. En prod, appellera `POST /auth/password/change/`.
  /// Renvoie `null` en cas de succès, une chaîne d'erreur sinon (pour affichage UI).
  Future<String?> changePassword({
    required String oldPassword,
    required String newPassword,
  }) async {
    await Future<void>.delayed(const Duration(milliseconds: 700));
    // Mock : l'ancien mot de passe attendu est celui du seed (`test1234`).
    if (oldPassword != 'test1234') {
      return 'Ancien mot de passe incorrect.';
    }
    if (newPassword.length < 8) {
      return 'Le nouveau mot de passe doit faire au moins 8 caractères.';
    }
    return null;
  }
}

final authProvider = AsyncNotifierProvider<AuthNotifier, Member?>(AuthNotifier.new);
