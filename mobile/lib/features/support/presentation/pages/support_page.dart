import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../app/theme/paysika/pa_colors.dart';
import '../../../../core/error/error_message.dart';
import '../../../../core/formatters/date_formatter.dart';
import '../../../../core/widgets/live_poller.dart';
import '../../../../core/widgets/skeleton.dart';
import '../../../../l10n/gen/app_localizations.dart';
import '../../domain/support_message.dart';
import '../state/support_notifier.dart';

/// Écran **Support** — fil unique membre ↔ support (chat).
///
/// Le membre laisse des messages ; le support répond dans le même fil (avec
/// notification + push). Style Paysika soft : bulles arrondies, fond clair.
class SupportPage extends ConsumerStatefulWidget {
  const SupportPage({super.key});

  @override
  ConsumerState<SupportPage> createState() => _SupportPageState();
}

class _SupportPageState extends ConsumerState<SupportPage> {
  final _ctrl = TextEditingController();
  final _scroll = ScrollController();
  bool _sending = false;

  @override
  void dispose() {
    _ctrl.dispose();
    _scroll.dispose();
    super.dispose();
  }

  Future<void> _send() async {
    final body = _ctrl.text.trim();
    if (body.isEmpty || _sending) return;
    setState(() => _sending = true);
    try {
      await ref.read(supportProvider.notifier).send(body);
      _ctrl.clear();
      _scrollToBottom();
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(friendlyError(e))),
        );
      }
    } finally {
      if (mounted) setState(() => _sending = false);
    }
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scroll.hasClients) {
        _scroll.animateTo(
          _scroll.position.maxScrollExtent + 80,
          duration: const Duration(milliseconds: 260),
          curve: Curves.easeOut,
        );
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final l = AppL10n.of(context);
    final async = ref.watch(supportProvider);

    return Scaffold(
      backgroundColor: PaColors.canvas,
      appBar: AppBar(
        backgroundColor: PaColors.canvas,
        surfaceTintColor: PaColors.canvas,
        elevation: 0,
        scrolledUnderElevation: 0,
        iconTheme: const IconThemeData(color: PaColors.inkPrimary),
        title: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              l.support_title,
              style: const TextStyle(
                color: PaColors.inkPrimary,
                fontSize: 16.5,
                fontWeight: FontWeight.w700,
              ),
            ),
            Text(
              l.support_subtitle,
              style: const TextStyle(color: PaColors.inkMuted, fontSize: 11.5),
            ),
          ],
        ),
      ),
      body: Column(
        children: [
          // Polling léger : voit les réponses du support sans pull-to-refresh.
          LivePoller(
            refresh: () => ref.read(supportProvider.notifier).refresh(),
            readSnapshot: () => ref.read(supportProvider).valueOrNull,
          ),
          Expanded(
            child: async.when(
              data: (msgs) => msgs.isEmpty
                  ? _Empty(l: l)
                  : ListView.builder(
                      controller: _scroll,
                      padding: const EdgeInsets.fromLTRB(16, 16, 16, 12),
                      itemCount: msgs.length,
                      itemBuilder: (_, i) => _Bubble(msg: msgs[i], l: l),
                    ),
              loading: () => const Padding(
                padding: EdgeInsets.all(16),
                child: SkeletonList(lines: 5),
              ),
              error: (e, _) => _ErrorBox(message: l.support_load_error),
            ),
          ),
          _Composer(
            ctrl: _ctrl,
            sending: _sending,
            hint: l.support_input_hint,
            onSend: _send,
          ),
        ],
      ),
    );
  }
}

class _Bubble extends StatelessWidget {
  const _Bubble({required this.msg, required this.l});
  final SupportMessage msg;
  final AppL10n l;

  @override
  Widget build(BuildContext context) {
    final mine = msg.isMine;
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Column(
        crossAxisAlignment:
            mine ? CrossAxisAlignment.end : CrossAxisAlignment.start,
        children: [
          Container(
            constraints: BoxConstraints(
              maxWidth: MediaQuery.sizeOf(context).width * 0.78,
            ),
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
            decoration: BoxDecoration(
              color: mine ? PaColors.teal : PaColors.paper,
              borderRadius: BorderRadius.only(
                topLeft: const Radius.circular(16),
                topRight: const Radius.circular(16),
                bottomLeft: Radius.circular(mine ? 16 : 4),
                bottomRight: Radius.circular(mine ? 4 : 16),
              ),
              border: mine
                  ? null
                  : Border.all(color: PaColors.line, width: 0.8),
            ),
            child: Text(
              msg.body,
              style: TextStyle(
                color: mine ? Colors.white : PaColors.inkPrimary,
                fontSize: 14,
                height: 1.4,
              ),
            ),
          ),
          const SizedBox(height: 3),
          Text(
            '${mine ? l.support_sender_you : l.support_sender_staff} · '
            '${AppDateFormatter.withTime(msg.createdAt)}',
            style: const TextStyle(color: PaColors.inkMuted, fontSize: 10.5),
          ),
        ],
      ),
    );
  }
}

class _Composer extends StatelessWidget {
  const _Composer({
    required this.ctrl,
    required this.sending,
    required this.hint,
    required this.onSend,
  });
  final TextEditingController ctrl;
  final bool sending;
  final String hint;
  final VoidCallback onSend;

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      top: false,
      child: Container(
        padding: const EdgeInsets.fromLTRB(12, 8, 12, 8),
        decoration: const BoxDecoration(
          color: PaColors.canvas,
          border: Border(top: BorderSide(color: PaColors.line, width: 0.8)),
        ),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.end,
          children: [
            Expanded(
              child: TextField(
                controller: ctrl,
                minLines: 1,
                maxLines: 5,
                textCapitalization: TextCapitalization.sentences,
                cursorColor: PaColors.teal,
                style: const TextStyle(fontSize: 14, color: PaColors.inkPrimary),
                decoration: InputDecoration(
                  hintText: hint,
                  hintStyle: const TextStyle(color: PaColors.inkFaint),
                  filled: true,
                  fillColor: PaColors.paper,
                  contentPadding:
                      const EdgeInsets.symmetric(horizontal: 16, vertical: 11),
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(22),
                    borderSide: BorderSide.none,
                  ),
                  enabledBorder: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(22),
                    borderSide: const BorderSide(color: PaColors.line, width: 0.8),
                  ),
                  focusedBorder: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(22),
                    borderSide: const BorderSide(color: PaColors.teal, width: 1.4),
                  ),
                ),
              ),
            ),
            const SizedBox(width: 8),
            GestureDetector(
              onTap: sending ? null : onSend,
              child: Container(
                width: 44,
                height: 44,
                decoration: BoxDecoration(
                  color: sending ? PaColors.inkFaint : PaColors.teal,
                  shape: BoxShape.circle,
                ),
                alignment: Alignment.center,
                child: sending
                    ? const SizedBox(
                        width: 18,
                        height: 18,
                        child: CircularProgressIndicator(
                          strokeWidth: 2.2,
                          color: Colors.white,
                        ),
                      )
                    : const Icon(Icons.send_rounded,
                        color: Colors.white, size: 20,),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _Empty extends StatelessWidget {
  const _Empty({required this.l});
  final AppL10n l;

  @override
  Widget build(BuildContext context) {
    return ListView(
      children: [
        const SizedBox(height: 70),
        Center(
          child: Container(
            width: 78,
            height: 78,
            decoration: const BoxDecoration(
              color: PaColors.tealSurface,
              shape: BoxShape.circle,
            ),
            alignment: Alignment.center,
            child: const Icon(Icons.support_agent_rounded,
                color: PaColors.teal, size: 36,),
          ),
        ),
        const SizedBox(height: 18),
        Center(
          child: Text(
            l.support_empty_title,
            style: const TextStyle(
              color: PaColors.inkPrimary,
              fontSize: 17,
              fontWeight: FontWeight.w700,
            ),
          ),
        ),
        const SizedBox(height: 6),
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 40),
          child: Text(
            l.support_empty_sub,
            textAlign: TextAlign.center,
            style: const TextStyle(color: PaColors.inkMuted, fontSize: 13.5),
          ),
        ),
      ],
    );
  }
}

class _ErrorBox extends StatelessWidget {
  const _ErrorBox({required this.message});
  final String message;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Text(
          message,
          textAlign: TextAlign.center,
          style: const TextStyle(color: PaColors.inkMuted, fontSize: 13.5),
        ),
      ),
    );
  }
}
