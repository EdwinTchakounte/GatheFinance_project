import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/di/providers.dart';
import '../../../../core/network/api_exceptions.dart';
import '../../domain/entities/announcement.dart';

/// Liste des annonces destinées au membre connecté.
///
/// GET /notifications/announcements/ → `{results: [...]}`. Lecture seule ;
/// `ref.invalidate(announcementsProvider)` pour rafraîchir (pull-to-refresh).
final announcementsProvider =
    FutureProvider.autoDispose<List<Announcement>>((ref) async {
  final dio = ref.watch(apiClientProvider).dio;
  try {
    final res =
        await dio.get<Map<String, dynamic>>('/notifications/announcements/');
    final results = (res.data?['results'] as List<dynamic>?) ?? const [];
    return results
        .map((a) => Announcement.fromJson(a as Map<String, dynamic>))
        .toList(growable: false);
  } on DioException catch (e) {
    throw mapDioError(e);
  }
});
