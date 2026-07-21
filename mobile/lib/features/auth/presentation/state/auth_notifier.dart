import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/di/providers.dart';
import '../../../../core/error/failures.dart';
import '../../../../core/services/push_registration_service.dart';
import '../../../../core/usecases/usecase.dart';
import '../../domain/entities/member.dart';
import '../../domain/usecases/sign_in.dart';

/// État auth de la presentation. Ne dépend QUE des usecases / repository
/// (zéro référence à Dio / HTTP).
class AuthNotifier extends AsyncNotifier<Member?> {
  late final SignIn _signIn = ref.read(signInUseCaseProvider);
  late final _getCurrent = ref.read(getCurrentMemberUseCaseProvider);
  late final _signOut = ref.read(signOutUseCaseProvider);

  @override
  Future<Member?> build() async {
    final member = await _getCurrent.call(const NoParams());
    // Déjà connecté (session persistée) → (ré)enregistre le token push.
    if (member != null) {
      unawaited(ref.read(pushRegistrationServiceProvider).syncToken());
    }
    return member;
  }

  Future<void> signIn({required String email, required String password}) async {
    state = const AsyncValue.loading();
    state = await AsyncValue.guard(
      () => _signIn.call(SignInParams(email: email, password: password)),
    );
    // Login réussi → enregistre le token push auprès du backend (best-effort).
    if (state.hasValue && state.value != null) {
      unawaited(ref.read(pushRegistrationServiceProvider).syncToken());
    }
  }

  Future<void> signOut() async {
    // Désenregistre le token push AVANT de fermer la session (endpoint authentifié).
    await ref.read(pushRegistrationServiceProvider).clearToken();
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
      // Garde le state actuel . l'UI gère son propre toast d'erreur.
      rethrow;
    }
  }

  /// Charge/remplace la photo de profil (avatar) et met à jour le state.
  Future<void> updatePhoto(String filePath) async {
    final repo = ref.read(authRepositoryProvider);
    final updated = await repo.updatePhoto(filePath);
    state = AsyncValue.data(updated);
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
