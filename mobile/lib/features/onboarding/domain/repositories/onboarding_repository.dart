/// Persiste l'état « onboarding vu » entre sessions.
abstract class OnboardingRepository {
  Future<bool> isSeen();
  Future<void> markSeen();
  Future<void> reset();
}
