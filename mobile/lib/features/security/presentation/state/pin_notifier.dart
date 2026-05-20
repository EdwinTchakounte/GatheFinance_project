import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../data/biometric_service.dart';
import '../../data/pin_repository.dart';

final pinRepositoryProvider = Provider<PinRepository>((ref) => PinRepository());
final biometricServiceProvider =
    Provider<BiometricService>((ref) => BiometricService());

/// État du verrou PIN.
class PinState {
  const PinState({
    required this.hasPin,
    required this.locked,
    this.biometricAvailable = false,
    this.biometricEnabled = false,
  });

  /// Un PIN a-t-il été défini par l'utilisateur ?
  final bool hasPin;

  /// L'app est-elle actuellement verrouillée (à déverrouiller par PIN) ?
  final bool locked;

  /// Le device dispose-t-il d'un capteur biométrique utilisable ?
  final bool biometricAvailable;

  /// L'utilisateur a-t-il activé le déverrouillage par empreinte ?
  final bool biometricEnabled;

  /// Peut-on proposer la biométrie maintenant ? (capteur + activée + PIN posé)
  bool get canUseBiometric => biometricAvailable && biometricEnabled && hasPin;

  PinState copyWith({
    bool? hasPin,
    bool? locked,
    bool? biometricAvailable,
    bool? biometricEnabled,
  }) =>
      PinState(
        hasPin: hasPin ?? this.hasPin,
        locked: locked ?? this.locked,
        biometricAvailable: biometricAvailable ?? this.biometricAvailable,
        biometricEnabled: biometricEnabled ?? this.biometricEnabled,
      );
}

/// Gère le cycle de vie du verrou : présence du PIN, verrouillage/déverrouillage,
/// et la préférence de déverrouillage biométrique.
class PinNotifier extends AsyncNotifier<PinState> {
  PinRepository get _repo => ref.read(pinRepositoryProvider);
  BiometricService get _bio => ref.read(biometricServiceProvider);

  @override
  Future<PinState> build() async {
    final has = await _repo.hasPin();
    final bioAvailable = await _bio.isAvailable();
    final bioEnabled = await _repo.biometricEnabled();
    return PinState(
      hasPin: has,
      locked: has,
      biometricAvailable: bioAvailable,
      biometricEnabled: bioEnabled,
    );
  }

  /// Définit le PIN (1re configuration) et déverrouille immédiatement.
  Future<void> setPin(String pin) async {
    await _repo.setPin(pin);
    final s = state.valueOrNull;
    state = AsyncValue.data(
      (s ?? const PinState(hasPin: true, locked: false))
          .copyWith(hasPin: true, locked: false),
    );
  }

  /// Change le PIN après vérification de l'ancien. Retourne `false` si l'ancien
  /// code est incorrect.
  Future<bool> changePin({required String current, required String next}) async {
    final ok = await _repo.verify(current);
    if (!ok) return false;
    await _repo.setPin(next);
    return true;
  }

  /// Vérifie le PIN saisi sur l'écran de déverrouillage.
  Future<bool> unlock(String pin) async {
    final ok = await _repo.verify(pin);
    if (ok) _markUnlocked();
    return ok;
  }

  /// Vérifie un PIN sans changer l'état de verrou (ex. révéler le solde).
  Future<bool> verify(String pin) => _repo.verify(pin);

  /// Déverrouille via biométrie (si activée + disponible).
  Future<bool> unlockWithBiometric(BiometricLabels labels) async {
    final s = state.valueOrNull;
    if (s == null || !s.canUseBiometric) return false;
    final ok = await _bio.authenticate(
      reason: labels.reason,
      signInTitle: labels.signInTitle,
      hint: labels.hint,
      cancelButton: labels.cancelButton,
    );
    if (ok) _markUnlocked();
    return ok;
  }

  /// Active/désactive la biométrie ; exige une auth réussie pour l'activer.
  Future<bool> setBiometricEnabled(bool enabled, {BiometricLabels? labels}) async {
    if (enabled) {
      if (labels == null) return false;
      final ok = await _bio.authenticate(
        reason: labels.reason,
        signInTitle: labels.signInTitle,
        hint: labels.hint,
        cancelButton: labels.cancelButton,
      );
      if (!ok) return false;
    }
    await _repo.setBiometricEnabled(enabled);
    final s = state.valueOrNull;
    if (s != null) {
      state = AsyncValue.data(s.copyWith(biometricEnabled: enabled));
    }
    return true;
  }

  void _markUnlocked() {
    final s = state.valueOrNull;
    state = AsyncValue.data(
      (s ?? const PinState(hasPin: true, locked: false))
          .copyWith(hasPin: true, locked: false),
    );
  }

  /// Reverrouille l'app (passage en arrière-plan, ou action manuelle).
  void lock() {
    final s = state.valueOrNull;
    if (s != null && s.hasPin) {
      state = AsyncValue.data(s.copyWith(locked: true));
    }
  }
}

final pinProvider =
    AsyncNotifierProvider<PinNotifier, PinState>(PinNotifier.new);
