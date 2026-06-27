import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../app/theme/paysika/pa_colors.dart';
import '../../../../core/di/providers.dart';
import '../../domain/entities/comment.dart';
import '../../domain/entities/reaction.dart';
import '../state/social_state.dart';

/// Bloc commentaires . design soft 2026.
///
/// - Header "Commentaires" avec compteur en chip + ligne separatrice fine.
/// - Composer minimaliste : champ arrondi 22 + bouton send en cercle gradient
///   teal->navy avec micro-animation au tap.
/// - Tile : avatar gradient initiales + bulle a coin "chat" (corner cut cote
///   avatar) + temps relatif "il y a 2 h" + suppression icon-only pour mes
///   commentaires.
/// - Etats vides / erreur chaleureux (icone + sous-texte engageant).
/// - Entree des tiles : fade + slide leger (Hero-feel, non bloquant).
class CommentsSection extends ConsumerStatefulWidget {
  const CommentsSection({super.key, required this.target});

  final SocialTarget target;

  @override
  ConsumerState<CommentsSection> createState() => _CommentsSectionState();
}

class _CommentsSectionState extends ConsumerState<CommentsSection> {
  final _controller = TextEditingController();
  final _focus = FocusNode();
  bool _sending = false;

  @override
  void dispose() {
    _controller.dispose();
    _focus.dispose();
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
      await ref
          .read(socialCommentsProvider(widget.target).notifier)
          .refresh();
      if (mounted) FocusScope.of(context).unfocus();
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Envoi impossible . vérifie ta connexion.'),
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
        backgroundColor: PaColors.paper,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
        title: const Text(
          'Supprimer ce commentaire ?',
          style: TextStyle(fontWeight: FontWeight.w700),
        ),
        content: const Text(
          'Cette action est définitive. Personne ne pourra plus le voir.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(false),
            child: const Text(
              'Annuler',
              style: TextStyle(color: PaColors.inkMuted, fontWeight: FontWeight.w600),
            ),
          ),
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(true),
            child: const Text(
              'Supprimer',
              style: TextStyle(color: PaColors.danger, fontWeight: FontWeight.w700),
            ),
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
        _Header(count: asyncState.valueOrNull?.count),
        const SizedBox(height: 14),
        _Composer(
          controller: _controller,
          focus: _focus,
          sending: _sending,
          onSend: _send,
        ),
        const SizedBox(height: 18),
        asyncState.when(
          loading: () => const _LoadingDots(),
          error: (_, __) => const _ErrorBlock(),
          data: (state) {
            if (state.items.isEmpty) return const _EmptyBlock();
            return Column(
              children: [
                for (var i = 0; i < state.items.length; i++)
                  Padding(
                    padding: EdgeInsets.only(
                      bottom: i == state.items.length - 1 ? 0 : 10,
                    ),
                    child: _FadeIn(
                      delayMs: i * 60,
                      child: _CommentBubble(
                        comment: state.items[i],
                        onDelete: state.items[i].isMine
                            ? () => _delete(state.items[i])
                            : null,
                      ),
                    ),
                  ),
                if (state.hasMore) ...[
                  const SizedBox(height: 14),
                  _LoadMoreButton(
                    loading: state.loadingMore,
                    onTap: () => ref
                        .read(socialCommentsProvider(widget.target).notifier)
                        .loadMore(),
                  ),
                ],
              ],
            );
          },
        ),
      ],
    );
  }
}

/// Header "Commentaires · 12" . chip compteur + barre teal accent.
class _Header extends StatelessWidget {
  const _Header({this.count});
  final int? count;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        const Text(
          'Commentaires',
          style: TextStyle(
            color: PaColors.inkPrimary,
            fontSize: 17,
            fontWeight: FontWeight.w800,
            letterSpacing: -0.3,
          ),
        ),
        if (count != null && count! > 0) ...[
          const SizedBox(width: 8),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 2),
            decoration: BoxDecoration(
              color: PaColors.tealSurface,
              borderRadius: BorderRadius.circular(10),
            ),
            child: Text(
              '$count',
              style: const TextStyle(
                color: PaColors.tealDark,
                fontSize: 11.5,
                fontWeight: FontWeight.w800,
                letterSpacing: 0.1,
              ),
            ),
          ),
        ],
        const Spacer(),
        Container(
          width: 36,
          height: 3,
          decoration: BoxDecoration(
            gradient: const LinearGradient(
              colors: [PaColors.teal, PaColors.blue],
            ),
            borderRadius: BorderRadius.circular(3),
          ),
        ),
      ],
    );
  }
}

/// Composer arrondi 22 avec bouton send en cercle teal->navy gradient.
class _Composer extends StatelessWidget {
  const _Composer({
    required this.controller,
    required this.focus,
    required this.sending,
    required this.onSend,
  });

  final TextEditingController controller;
  final FocusNode focus;
  final bool sending;
  final VoidCallback onSend;

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: PaColors.paper,
        borderRadius: BorderRadius.circular(22),
        border: Border.all(color: PaColors.line, width: 1),
        boxShadow: [
          BoxShadow(
            color: PaColors.navy.withValues(alpha: 0.04),
            blurRadius: 12,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      padding: const EdgeInsets.fromLTRB(16, 10, 8, 10),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          Expanded(
            child: TextField(
              controller: controller,
              focusNode: focus,
              minLines: 1,
              maxLines: 5,
              maxLength: 1000,
              textInputAction: TextInputAction.newline,
              decoration: const InputDecoration(
                hintText: 'Partage ton avis…',
                hintStyle: TextStyle(
                  color: PaColors.inkMuted,
                  fontSize: 14.5,
                  fontWeight: FontWeight.w500,
                ),
                isCollapsed: true,
                border: InputBorder.none,
                counterText: '',
                contentPadding: EdgeInsets.symmetric(vertical: 6),
              ),
              style: const TextStyle(
                color: PaColors.inkPrimary,
                fontSize: 14.5,
                height: 1.45,
              ),
            ),
          ),
          const SizedBox(width: 4),
          _SendButton(sending: sending, onSend: onSend),
        ],
      ),
    );
  }
}

class _SendButton extends StatefulWidget {
  const _SendButton({required this.sending, required this.onSend});
  final bool sending;
  final VoidCallback onSend;

  @override
  State<_SendButton> createState() => _SendButtonState();
}

class _SendButtonState extends State<_SendButton> {
  bool _pressed = false;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTapDown: (_) => setState(() => _pressed = true),
      onTapUp: (_) => setState(() => _pressed = false),
      onTapCancel: () => setState(() => _pressed = false),
      onTap: widget.sending ? null : widget.onSend,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 150),
        curve: Curves.easeOut,
        width: 40,
        height: 40,
        transform: Matrix4.identity()..scaleByDouble(_pressed ? 0.93 : 1.0, _pressed ? 0.93 : 1.0, 1.0, 1.0),
        transformAlignment: Alignment.center,
        decoration: BoxDecoration(
          gradient: LinearGradient(
            colors: widget.sending
                ? [PaColors.line, PaColors.line]
                : const [PaColors.teal, PaColors.blue],
          ),
          shape: BoxShape.circle,
          boxShadow: widget.sending
              ? null
              : [
                  BoxShadow(
                    color: PaColors.teal.withValues(alpha: 0.28),
                    blurRadius: 10,
                    offset: const Offset(0, 3),
                  ),
                ],
        ),
        child: Center(
          child: widget.sending
              ? const SizedBox(
                  width: 16,
                  height: 16,
                  child: CircularProgressIndicator(
                    strokeWidth: 2,
                    color: Colors.white,
                  ),
                )
              : const Icon(
                  Icons.send_rounded,
                  color: Colors.white,
                  size: 18,
                ),
        ),
      ),
    );
  }
}

/// Bulle commentaire . avatar gradient initiales + corps en card + temps
/// relatif + bouton supprimer pour mes propres commentaires.
class _CommentBubble extends StatelessWidget {
  const _CommentBubble({required this.comment, this.onDelete});

  final SocialComment comment;
  final VoidCallback? onDelete;

  @override
  Widget build(BuildContext context) {
    final isMine = comment.isMine;
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _GradientAvatar(name: comment.authorName, size: 36),
        const SizedBox(width: 10),
        Expanded(
          child: Container(
            padding: const EdgeInsets.fromLTRB(14, 11, 12, 12),
            decoration: BoxDecoration(
              color: isMine ? PaColors.tealSurface : PaColors.paper,
              borderRadius: const BorderRadius.only(
                topLeft: Radius.circular(4), // coin "chat" cote avatar
                topRight: Radius.circular(16),
                bottomLeft: Radius.circular(16),
                bottomRight: Radius.circular(16),
              ),
              border: Border.all(
                color: isMine
                    ? PaColors.teal.withValues(alpha: 0.22)
                    : PaColors.line,
              ),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Expanded(
                      child: Text(
                        comment.authorName,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: TextStyle(
                          color: isMine ? PaColors.tealDark : PaColors.inkPrimary,
                          fontSize: 13,
                          fontWeight: FontWeight.w800,
                          letterSpacing: -0.1,
                        ),
                      ),
                    ),
                    const SizedBox(width: 8),
                    Text(
                      _relativeTime(comment.createdAt),
                      style: const TextStyle(
                        color: PaColors.inkMuted,
                        fontSize: 11,
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                    if (onDelete != null) ...[
                      const SizedBox(width: 4),
                      InkResponse(
                        onTap: onDelete,
                        radius: 16,
                        child: const Padding(
                          padding: EdgeInsets.all(4),
                          child: Icon(
                            Icons.more_horiz_rounded,
                            size: 16,
                            color: PaColors.inkMuted,
                          ),
                        ),
                      ),
                    ],
                  ],
                ),
                const SizedBox(height: 4),
                Text(
                  comment.body,
                  style: TextStyle(
                    color: comment.hidden
                        ? PaColors.inkMuted
                        : PaColors.inkSecondary,
                    fontSize: 14,
                    height: 1.5,
                    fontStyle:
                        comment.hidden ? FontStyle.italic : FontStyle.normal,
                  ),
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }
}

/// Avatar circulaire avec gradient deterministe (hash du nom) + initiales.
class _GradientAvatar extends StatelessWidget {
  const _GradientAvatar({required this.name, this.size = 36});
  final String name;
  final double size;

  static const _palettes = <List<Color>>[
    [PaColors.teal, PaColors.blue],
    [PaColors.blue, PaColors.navy],
    [PaColors.tealDark, PaColors.teal],
    [Color(0xFF7B61FF), Color(0xFFB069FF)],
    [Color(0xFFFF8A65), Color(0xFFFFB199)],
    [Color(0xFF26C6DA), Color(0xFF00ACC1)],
  ];

  String get _initials {
    final parts = name.trim().split(RegExp(r'\s+'));
    if (parts.isEmpty || parts.first.isEmpty) return '?';
    final first = parts.first[0];
    final last = parts.length > 1 ? parts.last[0] : '';
    return '$first$last'.toUpperCase();
  }

  List<Color> get _palette {
    var hash = 0;
    for (final c in name.runes) {
      hash = (hash * 31 + c) & 0x7fffffff;
    }
    return _palettes[hash % _palettes.length];
  }

  @override
  Widget build(BuildContext context) {
    final palette = _palette;
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: palette,
        ),
        shape: BoxShape.circle,
        boxShadow: [
          BoxShadow(
            color: palette.last.withValues(alpha: 0.25),
            blurRadius: 8,
            offset: const Offset(0, 3),
          ),
        ],
      ),
      alignment: Alignment.center,
      child: Text(
        _initials,
        style: TextStyle(
          color: Colors.white,
          fontSize: size * 0.38,
          fontWeight: FontWeight.w800,
          letterSpacing: 0.2,
        ),
      ),
    );
  }
}

/// Temps relatif court : "à l'instant", "il y a 3 min", "il y a 2 h",
/// "hier", "12 mars".
String _relativeTime(DateTime dt) {
  final now = DateTime.now();
  final diff = now.difference(dt.toLocal());
  if (diff.inSeconds < 30) return "à l'instant";
  if (diff.inMinutes < 1) return 'il y a ${diff.inSeconds} s';
  if (diff.inMinutes < 60) return 'il y a ${diff.inMinutes} min';
  if (diff.inHours < 24) return 'il y a ${diff.inHours} h';
  if (diff.inDays == 1) return 'hier';
  if (diff.inDays < 7) return 'il y a ${diff.inDays} j';
  const months = [
    'janv.', 'févr.', 'mars', 'avr.', 'mai', 'juin',
    'juil.', 'août', 'sept.', 'oct.', 'nov.', 'déc.',
  ];
  return '${dt.day} ${months[dt.month - 1]}';
}

/// Wrapper qui fade-in + slide-up le child apres un delai (en ms).
/// Utilise pour la cascade des commentaires.
class _FadeIn extends StatefulWidget {
  const _FadeIn({required this.child, this.delayMs = 0});
  final Widget child;
  final int delayMs;

  @override
  State<_FadeIn> createState() => _FadeInState();
}

class _FadeInState extends State<_FadeIn> with SingleTickerProviderStateMixin {
  late final AnimationController _ctrl;
  late final Animation<double> _fade;
  late final Animation<Offset> _slide;

  @override
  void initState() {
    super.initState();
    _ctrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 380),
    );
    _fade = CurvedAnimation(parent: _ctrl, curve: Curves.easeOutCubic);
    _slide = Tween<Offset>(
      begin: const Offset(0, 0.08),
      end: Offset.zero,
    ).animate(_fade);
    Future<void>.delayed(Duration(milliseconds: widget.delayMs), () {
      if (mounted) _ctrl.forward();
    });
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return FadeTransition(
      opacity: _fade,
      child: SlideTransition(position: _slide, child: widget.child),
    );
  }
}

class _LoadingDots extends StatelessWidget {
  const _LoadingDots();

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(vertical: 28),
      alignment: Alignment.center,
      child: const SizedBox(
        width: 22,
        height: 22,
        child: CircularProgressIndicator(
          strokeWidth: 2.4,
          color: PaColors.teal,
        ),
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
      padding: const EdgeInsets.symmetric(vertical: 30, horizontal: 20),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [
            PaColors.tealSurface,
            PaColors.tealSurface.withValues(alpha: 0.45),
          ],
        ),
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: PaColors.teal.withValues(alpha: 0.18)),
      ),
      child: Column(
        children: [
          Container(
            width: 52,
            height: 52,
            decoration: const BoxDecoration(
              color: Colors.white,
              shape: BoxShape.circle,
            ),
            alignment: Alignment.center,
            child: const Icon(
              Icons.chat_bubble_outline_rounded,
              color: PaColors.teal,
              size: 26,
            ),
          ),
          const SizedBox(height: 14),
          const Text(
            'Lance la conversation',
            style: TextStyle(
              color: PaColors.inkPrimary,
              fontSize: 15,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 4),
          const Text(
            'Sois le premier à partager ton avis sur ce contenu.',
            textAlign: TextAlign.center,
            style: TextStyle(
              color: PaColors.inkMuted,
              fontSize: 13,
              height: 1.4,
            ),
          ),
        ],
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
      padding: const EdgeInsets.symmetric(vertical: 18, horizontal: 16),
      decoration: BoxDecoration(
        color: PaColors.dangerSurface,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: PaColors.danger.withValues(alpha: 0.2)),
      ),
      child: const Row(
        children: [
          Icon(Icons.cloud_off_rounded, color: PaColors.danger, size: 20),
          SizedBox(width: 10),
          Expanded(
            child: Text(
              'Impossible de charger les commentaires. Tire pour réessayer.',
              style: TextStyle(
                color: PaColors.danger,
                fontSize: 13,
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _LoadMoreButton extends StatelessWidget {
  const _LoadMoreButton({required this.loading, required this.onTap});
  final bool loading;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          borderRadius: BorderRadius.circular(20),
          onTap: loading ? null : onTap,
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 10),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                if (loading) ...[
                  const SizedBox(
                    width: 14,
                    height: 14,
                    child: CircularProgressIndicator(
                      strokeWidth: 2,
                      color: PaColors.teal,
                    ),
                  ),
                  const SizedBox(width: 8),
                ],
                Text(
                  loading ? 'Chargement…' : 'Voir plus de commentaires',
                  style: const TextStyle(
                    color: PaColors.teal,
                    fontSize: 13,
                    fontWeight: FontWeight.w700,
                    letterSpacing: 0.1,
                  ),
                ),
                if (!loading) ...[
                  const SizedBox(width: 4),
                  const Icon(
                    Icons.arrow_forward_rounded,
                    size: 15,
                    color: PaColors.teal,
                  ),
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }
}
