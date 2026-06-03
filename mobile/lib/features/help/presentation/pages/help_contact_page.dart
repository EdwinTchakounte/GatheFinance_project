import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../../../app/theme/paysika/pa_colors.dart';
import '../../../../app/theme/paysika/pa_typography.dart';
import '../../../../core/widgets/paysika/pa_card.dart';
import '../../../../core/widgets/paysika/pa_pattern_background.dart';
import '../../../../l10n/gen/app_localizations.dart';

/// Aide & contact — style **Paysika**.
///
/// **Coordonnées verbatim** récupérées depuis le site vitrine
/// (`frontend/apps/site/src/lib/site-config.ts`). Aucune invention.
class HelpContactPage extends StatelessWidget {
  const HelpContactPage({super.key});

  // Verbatim de site-config.ts
  static const _phone = '+237 6 56 13 06 72';
  static const _whatsapp = '+237 6 56 13 06 72';
  static const _landline = '233 42 48 47';
  static const _email = 'contact@gathe-finance.com';
  static const _agence = 'Rue Mermoz, Akwa, Douala, Cameroun';
  static const _hours = 'Lundi – Vendredi : 8h00 à 17h';

  @override
  Widget build(BuildContext context) {
    final l = AppL10n.of(context);
    final faq = <_FaqItem>[
      _FaqItem(
        icon: Icons.savings_outlined,
        tint: PaColors.teal,
        question: l.help_faq1_q,
        answer: l.help_faq1_a,
      ),
      _FaqItem(
        icon: Icons.account_balance_outlined,
        tint: PaColors.blue,
        question: l.help_faq2_q,
        answer: l.help_faq2_a,
      ),
      _FaqItem(
        icon: Icons.refresh_rounded,
        tint: PaColors.navy,
        question: l.help_faq3_q,
        answer: l.help_faq3_a,
      ),
      _FaqItem(
        icon: Icons.menu_book_outlined,
        tint: PaColors.warning,
        question: l.help_faq4_q,
        answer: l.help_faq4_a,
      ),
      _FaqItem(
        icon: Icons.lock_outline_rounded,
        tint: PaColors.success,
        question: l.help_faq5_q,
        answer: l.help_faq5_a,
      ),
    ];

    return Scaffold(
      backgroundColor: PaColors.canvas,
      body: PaPatternBackground(
        child: SafeArea(
          bottom: false,
          child: Column(
            children: [
              Padding(
                padding: const EdgeInsets.fromLTRB(8, 8, 16, 12),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    IconButton(
                      onPressed: () => Navigator.of(context).maybePop(),
                      icon: const Icon(Icons.arrow_back_rounded,
                          color: PaColors.inkPrimary),
                      tooltip: l.common_back,
                    ),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(l.help_eyebrow.toUpperCase(),
                              style: PaText.eyebrow()),
                          const SizedBox(height: 3),
                          Text(l.help_title, style: PaText.heading(size: 22)),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
              Expanded(
                child: ListView(
                  physics: const AlwaysScrollableScrollPhysics(),
                  padding: const EdgeInsets.fromLTRB(16, 4, 16, 90),
                  children: [
                    const _IntroCard(),
                    const SizedBox(height: 18),
                    _SectionLabel(l.help_faq_section),
                    const SizedBox(height: 8),
                    PaCard(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 6, vertical: 4),
                      child: Column(
                        children: [
                          for (int i = 0; i < faq.length; i++) ...[
                            _FaqTile(item: faq[i]),
                            if (i != faq.length - 1)
                              const Divider(height: 1, color: PaColors.line),
                          ],
                        ],
                      ),
                    ),
                    const SizedBox(height: 18),
                    _SectionLabel(l.help_contact_section),
                    const SizedBox(height: 8),
                    PaCard(
                      padding: EdgeInsets.zero,
                      child: Column(
                        children: [
                          _ContactTile(
                            icon: Icons.chat_outlined,
                            tint: const Color(0xFF25D366),
                            label: l.help_contact_whatsapp,
                            value: _whatsapp,
                            copyLabel: l.help_copied_whatsapp,
                          ),
                          const Divider(height: 1, color: PaColors.line),
                          _ContactTile(
                            icon: Icons.call_outlined,
                            tint: PaColors.blue,
                            label: l.help_contact_phone,
                            value: _phone,
                            copyLabel: l.help_copied_phone,
                          ),
                          const Divider(height: 1, color: PaColors.line),
                          _ContactTile(
                            icon: Icons.phone_in_talk_outlined,
                            tint: PaColors.navy,
                            label: l.help_contact_landline,
                            value: _landline,
                            copyLabel: l.help_copied_landline,
                          ),
                          const Divider(height: 1, color: PaColors.line),
                          _ContactTile(
                            icon: Icons.mail_outline_rounded,
                            tint: PaColors.teal,
                            label: l.help_contact_email,
                            value: _email,
                            copyLabel: l.help_copied_email,
                          ),
                          const Divider(height: 1, color: PaColors.line),
                          _ContactTile(
                            icon: Icons.location_on_outlined,
                            tint: PaColors.warning,
                            label: l.help_contact_agency,
                            value: _agence,
                            copyLabel: l.help_copied_agency,
                            multiline: true,
                          ),
                          const Divider(height: 1, color: PaColors.line),
                          _ContactTile(
                            icon: Icons.schedule_outlined,
                            tint: PaColors.inkMuted,
                            label: l.help_contact_hours,
                            value: _hours,
                            copyLabel: '',
                            copyable: false,
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}


class _IntroCard extends StatelessWidget {
  const _IntroCard();

  @override
  Widget build(BuildContext context) {
    final l = AppL10n.of(context);
    return PaCard(
      padding: const EdgeInsets.all(18),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 44,
            height: 44,
            decoration: BoxDecoration(
              color: PaColors.tealSurface,
              borderRadius: BorderRadius.circular(12),
            ),
            child: const Icon(
              Icons.support_agent_outlined,
              color: PaColors.teal,
              size: 22,
            ),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(l.help_intro_title, style: PaText.label(size: 14)),
                const SizedBox(height: 4),
                Text(
                  l.help_intro_sub,
                  style: PaText.body(size: 13, color: PaColors.inkSecondary),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}


class _SectionLabel extends StatelessWidget {
  const _SectionLabel(this.text);
  final String text;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(left: 2),
      child: Text(text.toUpperCase(), style: PaText.eyebrow()),
    );
  }
}


class _FaqItem {
  const _FaqItem({
    required this.icon,
    required this.tint,
    required this.question,
    required this.answer,
  });
  final IconData icon;
  final Color tint;
  final String question;
  final String answer;
}


class _FaqTile extends StatefulWidget {
  const _FaqTile({required this.item});
  final _FaqItem item;

  @override
  State<_FaqTile> createState() => _FaqTileState();
}

class _FaqTileState extends State<_FaqTile> {
  bool _open = false;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.transparent,
      child: InkWell(
        borderRadius: BorderRadius.circular(12),
        onTap: () {
          unawaited(HapticFeedback.selectionClick());
          setState(() => _open = !_open);
        },
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 14),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Container(
                    width: 36,
                    height: 36,
                    decoration: BoxDecoration(
                      color: widget.item.tint.withValues(alpha: 0.12),
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Icon(widget.item.icon,
                        size: 18, color: widget.item.tint),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Text(widget.item.question,
                        style: PaText.label(size: 14)),
                  ),
                  AnimatedRotation(
                    turns: _open ? 0.5 : 0,
                    duration: const Duration(milliseconds: 180),
                    child: const Icon(
                      Icons.keyboard_arrow_down_rounded,
                      color: PaColors.inkSecondary,
                      size: 22,
                    ),
                  ),
                ],
              ),
              AnimatedSize(
                duration: const Duration(milliseconds: 200),
                curve: Curves.easeOutCubic,
                alignment: Alignment.topCenter,
                child: _open
                    ? Padding(
                        padding:
                            const EdgeInsets.only(left: 48, top: 10, right: 4),
                        child: Text(
                          widget.item.answer,
                          style: PaText.body(
                              size: 13, color: PaColors.inkSecondary),
                        ),
                      )
                    : const SizedBox.shrink(),
              ),
            ],
          ),
        ),
      ),
    );
  }
}


class _ContactTile extends StatelessWidget {
  const _ContactTile({
    required this.icon,
    required this.tint,
    required this.label,
    required this.value,
    required this.copyLabel,
    this.multiline = false,
    this.copyable = true,
  });

  final IconData icon;
  final Color tint;
  final String label;
  final String value;
  final String copyLabel;
  final bool multiline;
  final bool copyable;

  @override
  Widget build(BuildContext context) {
    final l = AppL10n.of(context);
    final body = Padding(
      padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 14),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 36,
            height: 36,
            decoration: BoxDecoration(
              color: tint.withValues(alpha: 0.12),
              borderRadius: BorderRadius.circular(12),
            ),
            child: Icon(icon, size: 18, color: tint),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(label,
                    style: PaText.eyebrow(color: PaColors.inkMuted)),
                const SizedBox(height: 3),
                Text(
                  value,
                  maxLines: multiline ? 3 : 1,
                  overflow: TextOverflow.ellipsis,
                  style: PaText.label(size: 14),
                ),
              ],
            ),
          ),
          if (copyable) ...[
            const SizedBox(width: 8),
            const Icon(Icons.copy_rounded, size: 16, color: PaColors.inkFaint),
          ],
        ],
      ),
    );

    if (!copyable) return body;

    return Semantics(
      button: true,
      label: '$label — ${l.help_copy_a11y}',
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: () async {
            await Clipboard.setData(ClipboardData(text: value));
            unawaited(HapticFeedback.lightImpact());
            if (!context.mounted) return;
            ScaffoldMessenger.of(context)
              ..hideCurrentSnackBar()
              ..showSnackBar(
                SnackBar(
                  content: Text(copyLabel),
                  behavior: SnackBarBehavior.floating,
                  duration: const Duration(seconds: 2),
                ),
              );
          },
          child: body,
        ),
      ),
    );
  }
}
