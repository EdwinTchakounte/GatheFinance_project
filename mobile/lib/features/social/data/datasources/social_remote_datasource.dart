import '../../domain/entities/comment.dart';
import '../../domain/entities/reaction.dart';
import '../../domain/repositories/social_repository.dart';

/// Abstraction du data source HTTP — facilite les tests (mock injectable).
abstract class SocialRemoteDataSource {
  Future<SocialReaction> getReaction(SocialTarget target);
  Future<SocialReaction> toggleLike(SocialTarget target);
  Future<CommentsPage> listComments(
    SocialTarget target, {
    int offset = 0,
    int limit = 20,
  });
  Future<SocialComment> postComment(SocialTarget target, String body);
  Future<void> deleteMyComment(int commentId);
}
