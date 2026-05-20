import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/di/providers.dart';
import '../../../../core/usecases/usecase.dart';

class OnboardingNotifier extends AsyncNotifier<bool> {
  late final _isSeen = ref.read(isOnboardingSeenUseCaseProvider);
  late final _markSeen = ref.read(markOnboardingSeenUseCaseProvider);
  late final _reset = ref.read(resetOnboardingUseCaseProvider);

  @override
  Future<bool> build() => _isSeen.call(const NoParams());

  Future<void> markSeen() async {
    state = const AsyncValue.data(true);
    await _markSeen.call(const NoParams());
  }

  Future<void> reset() async {
    state = const AsyncValue.data(false);
    await _reset.call(const NoParams());
  }
}

final onboardingProvider =
    AsyncNotifierProvider<OnboardingNotifier, bool>(OnboardingNotifier.new);
