import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/di/providers.dart';
import '../../domain/entities/comment.dart';
import '../../domain/entities/reaction.dart';
import '../../domain/repositories/social_repository.dart';

// ---------------------------------------------------------------------------
// Reaction (like) . family par cible.
// ---------------------------------------------------------------------------

/// Etat asynchrone du like + count pour une cible donnee. AutoDispose pour
/// liberer la memoire quand on quitte la page detail.
class SocialReactionNotifier
    extends AutoDisposeFamilyAsyncNotifier<SocialReaction, SocialTarget> {
  late final SocialRepository _repo = ref.read(socialRepositoryProvider);

  @override
  Future<SocialReaction> build(SocialTarget arg) async {
    return _repo.getReaction(arg);
  }

  /// Permet au LikeButton d'injecter la valeur fraiche apres un POST
  /// /like/ sans declencher un GET supplementaire.
  void setReaction(SocialReaction r) {
    state = AsyncValue.data(r);
  }
}

final socialReactionProvider = AutoDisposeAsyncNotifierProvider.family<
    SocialReactionNotifier,
    SocialReaction,
    SocialTarget>(SocialReactionNotifier.new);


// ---------------------------------------------------------------------------
// Commentaires . pagination cumulee (load more).
// ---------------------------------------------------------------------------

class CommentsState {
  const CommentsState({
    required this.items,
    required this.count,
    required this.loadingMore,
  });

  final List<SocialComment> items;
  final int count;
  final bool loadingMore;

  bool get hasMore => items.length < count;

  CommentsState copyWith({
    List<SocialComment>? items,
    int? count,
    bool? loadingMore,
  }) =>
      CommentsState(
        items: items ?? this.items,
        count: count ?? this.count,
        loadingMore: loadingMore ?? this.loadingMore,
      );

  static const empty = CommentsState(items: [], count: 0, loadingMore: false);
}

class SocialCommentsNotifier
    extends AutoDisposeFamilyAsyncNotifier<CommentsState, SocialTarget> {
  late final SocialRepository _repo = ref.read(socialRepositoryProvider);

  static const int _pageSize = 20;

  @override
  Future<CommentsState> build(SocialTarget arg) async {
    final page = await _repo.listComments(arg, offset: 0, limit: _pageSize);
    return CommentsState(
      items: page.items,
      count: page.count,
      loadingMore: false,
    );
  }

  Future<void> refresh() async {
    state = const AsyncValue.loading();
    state = await AsyncValue.guard(() => build(arg));
  }

  Future<void> loadMore() async {
    final current = state.valueOrNull;
    if (current == null || current.loadingMore || !current.hasMore) return;
    state = AsyncValue.data(current.copyWith(loadingMore: true));
    try {
      final next = await _repo.listComments(
        arg,
        offset: current.items.length,
        limit: _pageSize,
      );
      state = AsyncValue.data(
        current.copyWith(
          items: [...current.items, ...next.items],
          count: next.count,
          loadingMore: false,
        ),
      );
    } catch (_) {
      // On laisse l'etat precedent . l'UI affichera juste l'erreur en SnackBar
      // lors d'un prochain tap. Pour rester simple on releve le flag.
      state = AsyncValue.data(current.copyWith(loadingMore: false));
    }
  }
}

final socialCommentsProvider = AutoDisposeAsyncNotifierProvider.family<
    SocialCommentsNotifier,
    CommentsState,
    SocialTarget>(SocialCommentsNotifier.new);
