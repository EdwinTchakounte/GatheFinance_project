import '../../../../core/error/exceptions.dart';
import '../../../../core/error/failures.dart';
import '../../domain/entities/comment.dart';
import '../../domain/entities/reaction.dart';
import '../../domain/repositories/social_repository.dart';
import '../datasources/social_remote_datasource.dart';

class SocialRepositoryImpl implements SocialRepository {
  const SocialRepositoryImpl(this._remote);
  final SocialRemoteDataSource _remote;

  Future<T> _run<T>(Future<T> Function() op) async {
    try {
      return await op();
    } on NetworkException catch (e) {
      throw NetworkFailure(e.message);
    } on ServerException catch (e) {
      throw UnexpectedFailure(e.message);
    }
  }

  @override
  Future<SocialReaction> getReaction(SocialTarget target) =>
      _run(() => _remote.getReaction(target));

  @override
  Future<SocialReaction> toggleLike(SocialTarget target) =>
      _run(() => _remote.toggleLike(target));

  @override
  Future<CommentsPage> listComments(
    SocialTarget target, {
    int offset = 0,
    int limit = 20,
  }) =>
      _run(() => _remote.listComments(target, offset: offset, limit: limit));

  @override
  Future<SocialComment> postComment(SocialTarget target, String body) =>
      _run(() => _remote.postComment(target, body));

  @override
  Future<void> deleteMyComment(int commentId) =>
      _run(() => _remote.deleteMyComment(commentId));
}
