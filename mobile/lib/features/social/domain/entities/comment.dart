/// Entite domaine — commentaire d'un contenu (article ou campagne).
///
/// Le body est deja "rendu" par le backend : si `hidden` est vrai, le
/// backend renvoie un placeholder ("[Commentaire masque]"). L'UI le
/// detecte via `hidden=true` et le rend en italique grise.
///
/// Fil de discussion (1 niveau) : un commentaire racine (`parentId == null`)
/// porte ses `replies` ; une reponse a `parentId` renseigne et `replies` vide.
class SocialComment {
  const SocialComment({
    required this.id,
    required this.body,
    required this.authorName,
    required this.createdAt,
    required this.hidden,
    required this.isMine,
    this.parentId,
    this.replies = const [],
    this.replyCount = 0,
  });

  final int id;
  final String body;
  final String authorName;
  final DateTime createdAt;
  final bool hidden;
  final bool isMine;
  final int? parentId;
  final List<SocialComment> replies;
  final int replyCount;

  bool get isReply => parentId != null;
}
