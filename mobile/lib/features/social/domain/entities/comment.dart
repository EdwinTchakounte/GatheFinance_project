/// Entite domaine — commentaire d'un contenu (article ou campagne).
///
/// Le body est deja "rendu" par le backend : si `hidden` est vrai, le
/// backend renvoie un placeholder ("[Commentaire masque]"). L'UI le
/// detecte via `hidden=true` et le rend en italique grise.
class SocialComment {
  const SocialComment({
    required this.id,
    required this.body,
    required this.authorName,
    required this.createdAt,
    required this.hidden,
    required this.isMine,
  });

  final int id;
  final String body;
  final String authorName;
  final DateTime createdAt;
  final bool hidden;
  final bool isMine;
}
