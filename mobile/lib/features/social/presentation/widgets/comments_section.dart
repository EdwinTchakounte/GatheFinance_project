import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

import '../../../../app/theme/paysika/pa_colors.dart';
import '../../../../core/di/providers.dart';
import '../../domain/entities/comment.dart';
import '../../domain/entities/reaction.dart';
import '../state/social_state.dart';

/// Bloc commentaires — composer en haut + liste paginee (20 par 20).
/// Charge automatiquement la 1re page au montage ; bouton "Charger plus"
/// si `count > items.length`.
class CommentsSection extends ConsumerStatefulWidget {
  const CommentsSection({super.key, required this.target});

  final SocialTarget target;

  @override
  ConsumerState<CommentsSection> createState() => _CommentsSectionState();
}

class _CommentsSectionState extends ConsumerState<CommentsSection> {
  final _controller = TextEditingController();
  bool _sending = false;

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  Future<void> _send() async {
    final raw = _controller.text.trim();
    if (raw.isEmpty || _sending) return;
    setState(() => _sending = true);
    final repo = ref.read(socialRepositoryProvider);
    try {
      await repo.postComment(widget.target, raw);
      _controller.clear();
      // Reset + re-fetch.
      await ref
          .read(socialCommentsProvider(widget.target).notifier)
          .refresh();
      if (mounted) {
        FocusScope.of(context).unfocus();
      }
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Envoi impossible — verifie ta connexion.'),
          ),
        );
      }
    } finally {
      if (mounted) setState(() => _sending = false);
    }
  }

  Future<void> _delete(SocialComment c) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Supprimer ce commentaire ?'),
        content: const Text('Cette action est definitive.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(false),
            child: const Text('Annuler'),
          ),
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(true),
            child: const Text('Supprimer'),
          ),
        ],
      ),
    );
    if (ok != true) return;
    try {
      await ref.read(socialRepositoryProvider).deleteMyComment(c.id);
      await ref
          .read(socialCommentsProvider(widget.target).notifier)
          .refresh();
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Suppression impossible.')),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final asyncState = ref.watch(socialCommentsProvider(widget.target));

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          'Commentaires',
          style: TextStyle(
            color: PaColors.inkPrimary,
            fontSize: 16,
            fontWeight: FontWeight.w800,
            letterSpacing: -0.2,
          ),
        ),
        const SizedBox(height: 12),
        _Composer(
          controller: _controller,
          sending: _sending,
          onSend: _send,
        ),
        const SizedBox(height: 16),
        asyncState.when(
          loading: () => const Padding(
            padding: EdgeInsets.symmetric(vertical: 24),
            child: Center(
              child: SizedBox(
                width: 20,
                height: 20,
                child: CircularProgressIndicator(
                  strokeWidth: 2.2,
                  color: PaColors.teal,
                ),
              ),
            ),
          ),
          error: (_, __) => const _ErrorBlock(),
          data: (state) {
            if (state.items.isEmpty) {
              return const _EmptyBlock();
            }
            return Column(
              children: [
                for (final c in state.items)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 12),
                    child: _CommentTile(
                      comment: c,
                      onDelete: c.isMine ? () => _delete(c) : null,
                    ),
                  ),
                if (state.hasMore)
                  TextButton(
                    onPressed: state.loadingMore
                        ? null
                        : () => ref
                            .read(socialCommentsProvider(widget.target).notifier)
                            .loadMore(),
                    child: Text(
                      state.loadingMore ? 'Chargement…' : 'Charger plus',
                      style: const TextStyle(
                        color: PaColors.teal,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ),
              ],
            );
          },
        ),
      ],
    );
  }
}

class _Composer extends StatelessWidget {
  const _Composer({
    required this.controller,
    required this.sending,
    required this.onSend,
  });
  final TextEditingController controller;
  final bool sending;
  final VoidCallback onSend;

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: PaColors.paper,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: PaColors.line),
      ),
      padding: const EdgeInsets.fromLTRB(14, 10, 8, 10),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          Expanded(
            child: TextField(
              controller: controller,
              minLines: 1,
              maxLines: 4,
              maxLength: 1000,
              decoration: const InputDecoration(
                hintText: 'Ecris un commentaire…',
                hintStyle: TextStyle(color: PaColors.inkMuted, fontSize: 14),
                isCollapsed: true,
                border: InputBorder.none,
                counterText: '',
              ),
              style: const TextStyle(
                color: PaColors.inkPrimary,
                fontSize: 14,
                height: 1.4,
              ),
            ),
          ),
          IconButton(
            tooltip: 'Envoyer',
            onPressed: sending ? null : onSend,
            icon: sending
                ? const SizedBox(
                    width: 18,
                    height: 18,
                    child: CircularProgressIndicator(
                      strokeWidth: 2,
                      color: PaColors.teal,
                    ),
                  )
                : const Icon(Icons.send_rounded, color: PaColors.teal),
          ),
        ],
      ),
    );
  }
}

class _CommentTile extends StatelessWidget {
  const _CommentTile({required this.comment, this.onDelete});
  final SocialComment comment;
  final VoidCallback? onDelete;

  @override
  Widget build(BuildContext context) {
    final dt = DateFormat('dd MMM yyyy · HH:mm', 'fr_FR');
    return Container(
      padding: const EdgeInsets.fromLTRB(14, 12, 14, 12),
      decoration: BoxDecoration(
        color: PaColors.paper,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: PaColors.line),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  comment.authorName,
                  style: const TextStyle(
                    color: PaColors.inkPrimary,
                    fontSize: 13,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ),
              Text(
                dt.format(comment.createdAt.toLocal()),
                style: const TextStyle(
                  color: PaColors.inkMuted,
                  fontSize: 11.5,
                ),
              ),
              if (onDelete != null) ...[
                const SizedBox(width: 4),
                InkWell(
                  onTap: onDelete,
                  borderRadius: BorderRadius.circular(20),
                  child: const Padding(
                    padding: EdgeInsets.all(4),
                    child: Icon(
                      Icons.delete_outline_rounded,
                      size: 18,
                      color: PaColors.inkMuted,
                    ),
                  ),
                ),
              ],
            ],
          ),
          const SizedBox(height: 6),
          Text(
            comment.body,
            style: TextStyle(
              color: comment.hidden ? PaColors.inkMuted : PaColors.inkSecondary,
              fontSize: 13.5,
              height: 1.45,
              fontStyle:
                  comment.hidden ? FontStyle.italic : FontStyle.normal,
            ),
          ),
        ],
      ),
    );
  }
}

class _EmptyBlock extends StatelessWidget {
  const _EmptyBlock();
  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(vertical: 24, horizontal: 16),
      decoration: BoxDecoration(
        color: PaColors.cardBg,
        borderRadius: BorderRadius.circular(14),
      ),
      alignment: Alignment.center,
      child: const Text(
        'Sois le premier a reagir.',
        style: TextStyle(color: PaColors.inkMuted, fontSize: 13.5),
      ),
    );
  }
}

class _ErrorBlock extends StatelessWidget {
  const _ErrorBlock();
  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(vertical: 16, horizontal: 16),
      decoration: BoxDecoration(
        color: PaColors.dangerSurface,
        borderRadius: BorderRadius.circular(14),
      ),
      alignment: Alignment.center,
      child: const Text(
        'Impossible de charger les commentaires.',
        style: TextStyle(color: PaColors.danger, fontSize: 13),
      ),
    );
  }
}
