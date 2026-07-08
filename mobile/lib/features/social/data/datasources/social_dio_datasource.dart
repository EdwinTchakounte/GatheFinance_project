import 'package:dio/dio.dart';

import '../../../../core/network/api_client.dart';
import '../../../../core/network/api_exceptions.dart';
import '../../domain/entities/comment.dart';
import '../../domain/entities/reaction.dart';
import '../../domain/repositories/social_repository.dart';
import 'social_remote_datasource.dart';

/// Implementation HTTP des endpoints `/api/v1/social/...`.
///
/// Tous les endpoints exigent une session authentifiee (le client Dio
/// porte deja le cookie sessionid via `ApiClient`).
class SocialDioDataSource implements SocialRemoteDataSource {
  SocialDioDataSource(this._client);

  final ApiClient _client;
  Dio get _dio => _client.dio;

  String _base(SocialTarget t) => '/social/${t.kind.apiPath}/${t.id}';

  @override
  Future<SocialReaction> getReaction(SocialTarget target) async {
    try {
      final res = await _dio.get<Map<String, dynamic>>(
        '${_base(target)}/reaction/',
      );
      return _parseReaction(res.data ?? const {});
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }

  @override
  Future<SocialReaction> toggleLike(SocialTarget target) async {
    try {
      final res = await _dio.post<Map<String, dynamic>>(
        '${_base(target)}/like/',
      );
      return _parseReaction(res.data ?? const {});
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }

  @override
  Future<CommentsPage> listComments(
    SocialTarget target, {
    int offset = 0,
    int limit = 20,
  }) async {
    try {
      final res = await _dio.get<Map<String, dynamic>>(
        '${_base(target)}/comments/',
        queryParameters: {'offset': offset, 'limit': limit},
      );
      final data = res.data ?? const {};
      final results = (data['results'] as List<dynamic>?) ?? const [];
      return CommentsPage(
        items: results
            .map((c) => _parseComment(c as Map<String, dynamic>))
            .toList(growable: false),
        count: (data['count'] as num?)?.toInt() ?? results.length,
        offset: (data['offset'] as num?)?.toInt() ?? offset,
        limit: (data['limit'] as num?)?.toInt() ?? limit,
      );
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }

  @override
  Future<SocialComment> postComment(
    SocialTarget target,
    String body, {
    int? parentId,
  }) async {
    try {
      final res = await _dio.post<Map<String, dynamic>>(
        '${_base(target)}/comments/',
        data: {
          'body': body,
          if (parentId != null) 'parent_id': parentId,
        },
      );
      return _parseComment(res.data ?? const {});
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }

  @override
  Future<void> deleteMyComment(int commentId) async {
    try {
      await _dio.delete<void>('/social/comments/$commentId/');
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }
}

SocialReaction _parseReaction(Map<String, dynamic> json) {
  return SocialReaction(
    liked: json['liked'] == true,
    count: (json['count'] as num?)?.toInt() ?? 0,
  );
}

SocialComment _parseComment(Map<String, dynamic> json) {
  final rawReplies = (json['replies'] as List<dynamic>?) ?? const [];
  return SocialComment(
    id: (json['id'] as num).toInt(),
    body: (json['body'] as String?) ?? '',
    authorName: (json['author_name'] as String?) ?? 'Membre',
    createdAt:
        DateTime.tryParse((json['created_at'] as String?) ?? '') ??
            DateTime.now(),
    hidden: json['hidden'] == true,
    isMine: json['is_mine'] == true,
    parentId: (json['parent_id'] as num?)?.toInt(),
    replies: rawReplies
        .map((r) => _parseComment(r as Map<String, dynamic>))
        .toList(growable: false),
    replyCount: (json['reply_count'] as num?)?.toInt() ?? rawReplies.length,
  );
}
