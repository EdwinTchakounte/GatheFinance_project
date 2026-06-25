import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../app/theme/paysika/pa_colors.dart';
import '../../../../core/di/providers.dart';
import '../../domain/entities/reaction.dart';
import '../state/social_state.dart';

/// Bouton coeur + compteur. Au tap : optimistic toggle (UI immediate),
/// puis appel API ; rollback si l'API echoue. Le compteur affiche le
/// total agrege renvoye par le backend (`count`).
class LikeButton extends ConsumerStatefulWidget {
  const LikeButton({
    super.key,
    required this.target,
    this.padding = const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
  });

  final SocialTarget target;
  final EdgeInsetsGeometry padding;

  @override
  ConsumerState<LikeButton> createState() => _LikeButtonState();
}

class _LikeButtonState extends ConsumerState<LikeButton> {
  bool _busy = false;

  Future<void> _onTap(SocialReaction current) async {
    if (_busy) return;
    setState(() => _busy = true);
    final repo = ref.read(socialRepositoryProvider);
    // Optimistic UI : on inverse l'etat localement avant le tour reseau.
    // Le provider lit la valeur reseau, on n'a pas a tordre son cache .
    // on invalidera apres l'appel pour rafraichir proprement.
    try {
      final updated = await repo.toggleLike(widget.target);
      // Re-injecte directement la valeur fraiche dans le provider . evite
      // un round-trip GET inutile.
      ref
          .read(socialReactionProvider(widget.target).notifier)
          .setReaction(updated);
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Action impossible . verifie ta connexion.'),
          ),
        );
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final asyncReaction = ref.watch(socialReactionProvider(widget.target));
    final reaction = asyncReaction.value ?? SocialReaction.empty;
    final liked = reaction.liked;
    final count = reaction.count;

    return InkWell(
      onTap: () => _onTap(reaction),
      borderRadius: BorderRadius.circular(999),
      child: Padding(
        padding: widget.padding,
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            AnimatedScale(
              scale: liked ? 1.12 : 1.0,
              duration: const Duration(milliseconds: 180),
              curve: Curves.easeOutBack,
              child: Icon(
                liked ? Icons.favorite_rounded : Icons.favorite_border_rounded,
                size: 22,
                color: liked ? PaColors.danger : PaColors.inkSecondary,
              ),
            ),
            const SizedBox(width: 6),
            Text(
              '$count',
              style: TextStyle(
                fontSize: 13,
                fontWeight: FontWeight.w700,
                color: liked ? PaColors.danger : PaColors.inkSecondary,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
