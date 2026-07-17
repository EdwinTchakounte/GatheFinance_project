import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/di/providers.dart';
import '../../domain/support_message.dart';

/// État du fil de support membre. Charge les messages, en poste de nouveaux.
class SupportNotifier extends AsyncNotifier<List<SupportMessage>> {
  Future<List<SupportMessage>> _fetch() async {
    final dio = ref.read(apiClientProvider).dio;
    final res = await dio.get<Map<String, dynamic>>('/support/thread/');
    final raw = (res.data?['messages'] as List? ?? const [])
        .cast<Map<String, dynamic>>();
    return raw.map(SupportMessage.fromJson).toList();
  }

  @override
  Future<List<SupportMessage>> build() => _fetch();

  Future<void> refresh() async {
    state = await AsyncValue.guard(_fetch);
  }

  /// Poste un message et rafraîchit le fil.
  Future<void> send(String body) async {
    final dio = ref.read(apiClientProvider).dio;
    await dio.post<Map<String, dynamic>>(
      '/support/messages/',
      data: {'body': body},
    );
    await refresh();
  }
}

final supportProvider =
    AsyncNotifierProvider<SupportNotifier, List<SupportMessage>>(
  SupportNotifier.new,
);

/// Compteur de messages support non-lus (badge Profil / cloche).
final supportUnreadProvider = FutureProvider<int>((ref) async {
  final dio = ref.read(apiClientProvider).dio;
  try {
    final res = await dio.get<Map<String, dynamic>>('/support/unread/');
    return (res.data?['count'] as num?)?.toInt() ?? 0;
  } catch (_) {
    return 0;
  }
});
