import '../entities/comment.dart';
import '../entities/reaction.dart';

/// Page de commentaires renvoyee par le backend (offset/limit).
class CommentsPage {
  const CommentsPage({
    required this.items,
    required this.count,
    required this.offset,
    required this.limit,
  });
  final List<SocialComment> items;
  final int count;
  final int offset;
  final int limit;
}

/// Contrat domaine pour les interactions sociales (likes & commentaires).
abstract class SocialRepository {
  Future<SocialReaction> getReaction(SocialTarget target);

  /// Toggle le like — renvoie l'etat apres mutation (liked + count).
  Future<SocialReaction> toggleLike(SocialTarget target);

  Future<CommentsPage> listComments(
    SocialTarget target, {
    int offset = 0,
    int limit = 20,
  });

  /// Poste un commentaire racine, ou une reponse si [parentId] est fourni.
  Future<SocialComment> postComment(
    SocialTarget target,
    String body, {
    int? parentId,
  });

  Future<void> deleteMyComment(int commentId);
}
