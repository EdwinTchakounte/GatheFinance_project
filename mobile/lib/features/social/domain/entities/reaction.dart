/// Etat d'une "reaction" (like) pour un contenu donne.
///
/// `liked` = true si le membre connecte a deja like ;
/// `count` = total agrege (toutes reactions confondues) sur le contenu.
class SocialReaction {
  const SocialReaction({required this.liked, required this.count});

  final bool liked;
  final int count;

  SocialReaction copyWith({bool? liked, int? count}) =>
      SocialReaction(liked: liked ?? this.liked, count: count ?? this.count);

  static const empty = SocialReaction(liked: false, count: 0);
}

/// Designe la cible d'une interaction sociale.
/// Aligne sur le `kind` cote backend (`article` / `campaign`).
enum SocialTargetKind {
  article,
  campaign;

  String get apiPath => switch (this) {
        SocialTargetKind.article => 'articles',
        SocialTargetKind.campaign => 'campaigns',
      };
}

/// Cle composite utilisee par les providers Riverpod (FutureProvider.family).
/// On l'enrobe dans une classe immuable pour pouvoir l'utiliser comme cle
/// d'un `family` sans pieges d'egalite (records sont OK aussi en Dart 3 mais
/// on garde la classe pour conserver `==`/`hashCode` explicites lisibles).
class SocialTarget {
  const SocialTarget({required this.kind, required this.id});
  final SocialTargetKind kind;
  final int id;

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      (other is SocialTarget && other.kind == kind && other.id == id);

  @override
  int get hashCode => Object.hash(kind, id);
}
