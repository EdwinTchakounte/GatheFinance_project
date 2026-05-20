import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../../../app/theme/app_colors.dart';
import '../../../../app/theme/app_radii.dart';
import '../../../../app/theme/app_spacing.dart';
import '../../../../app/theme/app_typography.dart';
import '../../../../core/widgets/app_card.dart';
import '../../../../core/widgets/brand_background.dart';
import '../../../../core/widgets/static_page_header.dart';
import '../../../../l10n/gen/app_localizations.dart';

/// Aide & contact.
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
        tint: AppColors.emerald,
        question: l.help_faq1_q,
        answer: l.help_faq1_a,
      ),
      _FaqItem(
        icon: Icons.account_balance_outlined,
        tint: AppColors.cobalt,
        question: l.help_faq2_q,
        answer: l.help_faq2_a,
      ),
      _FaqItem(
        icon: Icons.refresh_rounded,
        tint: AppColors.cobaltLight,
        question: l.help_faq3_q,
        answer: l.help_faq3_a,
      ),
      _FaqItem(
        icon: Icons.menu_book_outlined,
        tint: AppColors.terra,
        question: l.help_faq4_q,
        answer: l.help_faq4_a,
      ),
      _FaqItem(
        icon: Icons.lock_outline_rounded,
        tint: AppColors.terraDark,
        question: l.help_faq5_q,
        answer: l.help_faq5_a,
      ),
    ];

    return Scaffold(
      body: BrandBackground(
        intensity: 0.55,
        child: SafeArea(
          bottom: false,
          child: Column(
            children: [
              StaticPageHeader(
                eyebrow: l.help_eyebrow,
                title: l.help_title,
              ),
              Expanded(
                child: ListView(
                  physics: const AlwaysScrollableScrollPhysics(),
                  padding: const EdgeInsets.fromLTRB(
                    AppSpacing.screenH,
                    AppSpacing.m,
                    AppSpacing.screenH,
                    AppSpacing.huge,
                  ),
                  children: [
                    const _IntroCard(),
                    const SizedBox(height: AppSpacing.l),

                    _SectionLabel(l.help_faq_section),
                    const SizedBox(height: AppSpacing.s),
                    AppCard(
                      variant: AppCardVariant.glass,
                      padding: const EdgeInsets.symmetric(
                        horizontal: 6,
                        vertical: 4,
                      ),
                      child: Column(
                        children: [
                          for (int i = 0; i < faq.length; i++) ...[
                            _FaqTile(item: faq[i]),
                            if (i != faq.length - 1)
                              Divider(
                                height: 1,
                                color: Theme.of(context).colorScheme.outline,
                              ),
                          ],
                        ],
                      ),
                    ),
                    const SizedBox(height: AppSpacing.l),

                    _SectionLabel(l.help_contact_section),
                    const SizedBox(height: AppSpacing.s),
                    AppCard(
                      variant: AppCardVariant.glass,
                      padding: EdgeInsets.zero,
                      child: Builder(
                        builder: (context) {
                          final scheme = Theme.of(context).colorScheme;
                          return Column(
                            children: [
                              _ContactTile(
                                icon: Icons.chat_outlined,
                                tint: const Color(0xFF25D366),
                                label: l.help_contact_whatsapp,
                                value: _whatsapp,
                                copyLabel: l.help_copied_whatsapp,
                              ),
                              Divider(height: 1, color: scheme.outline),
                              _ContactTile(
                                icon: Icons.call_outlined,
                                tint: AppColors.cobalt,
                                label: l.help_contact_phone,
                                value: _phone,
                                copyLabel: l.help_copied_phone,
                              ),
                              Divider(height: 1, color: scheme.outline),
                              _ContactTile(
                                icon: Icons.phone_in_talk_outlined,
                                tint: AppColors.cobaltLight,
                                label: l.help_contact_landline,
                                value: _landline,
                                copyLabel: l.help_copied_landline,
                              ),
                              Divider(height: 1, color: scheme.outline),
                              _ContactTile(
                                icon: Icons.mail_outline_rounded,
                                tint: AppColors.emerald,
                                label: l.help_contact_email,
                                value: _email,
                                copyLabel: l.help_copied_email,
                              ),
                              Divider(height: 1, color: scheme.outline),
                              _ContactTile(
                                icon: Icons.location_on_outlined,
                                tint: AppColors.terra,
                                label: l.help_contact_agency,
                                value: _agence,
                                copyLabel: l.help_copied_agency,
                                multiline: true,
                              ),
                              Divider(height: 1, color: scheme.outline),
                              _ContactTile(
                                icon: Icons.schedule_outlined,
                                tint: AppColors.terraDark,
                                label: l.help_contact_hours,
                                value: _hours,
                                copyLabel: '',
                                copyable: false,
                              ),
                            ],
                          );
                        },
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
    final scheme = Theme.of(context).colorScheme;
    return AppCard(
      variant: AppCardVariant.glass,
      padding: const EdgeInsets.all(18),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 44,
            height: 44,
            decoration: BoxDecoration(
              color: AppColors.emerald.withValues(alpha: 0.12),
              borderRadius: const BorderRadius.all(AppRadii.r12),
            ),
            child: const Icon(
              Icons.support_agent_outlined,
              color: AppColors.emerald,
              size: 22,
            ),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  l.help_intro_title,
                  style: AppTypography.labelLarge
                      .copyWith(color: scheme.onSurface),
                ),
                const SizedBox(height: 4),
                Text(
                  l.help_intro_sub,
                  style: AppTypography.bodySmall.copyWith(
                    color: scheme.onSurface.withValues(alpha: 0.7),
                  ),
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
    final scheme = Theme.of(context).colorScheme;
    return Padding(
      padding: const EdgeInsets.only(left: 2),
      child: Text(
        text.toUpperCase(),
        style: AppTypography.labelMedium.copyWith(
          color: scheme.onSurface.withValues(alpha: 0.55),
          letterSpacing: 1.4,
          fontWeight: FontWeight.w700,
          fontSize: 11.5,
        ),
      ),
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

class _FaqTileState extends State<_FaqTile>
    with SingleTickerProviderStateMixin {
  bool _open = false;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Material(
      color: Colors.transparent,
      child: InkWell(
        borderRadius: const BorderRadius.all(AppRadii.r12),
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
                      borderRadius: const BorderRadius.all(AppRadii.r12),
                    ),
                    child: Icon(
                      widget.item.icon,
                      size: 18,
                      color: widget.item.tint,
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Text(
                      widget.item.question,
                      style: AppTypography.bodyMedium.copyWith(
                        fontWeight: FontWeight.w600,
                        color: scheme.onSurface,
                      ),
                    ),
                  ),
                  AnimatedRotation(
                    turns: _open ? 0.5 : 0,
                    duration: const Duration(milliseconds: 180),
                    child: Icon(
                      Icons.keyboard_arrow_down_rounded,
                      color: scheme.onSurface.withValues(alpha: 0.7),
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
                        padding: const EdgeInsets.only(
                          left: 48,
                          top: 10,
                          right: 4,
                        ),
                        child: Text(
                          widget.item.answer,
                          style: AppTypography.bodySmall.copyWith(
                            color: scheme.onSurface.withValues(alpha: 0.7),
                            height: 1.5,
                          ),
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
    final scheme = Theme.of(context).colorScheme;
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
              borderRadius: const BorderRadius.all(AppRadii.r12),
            ),
            child: Icon(icon, size: 18, color: tint),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  label,
                  style: AppTypography.labelMedium.copyWith(
                    color: scheme.onSurface.withValues(alpha: 0.55),
                    letterSpacing: 0.4,
                    fontSize: 11.5,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  value,
                  maxLines: multiline ? 3 : 1,
                  overflow: TextOverflow.ellipsis,
                  style: AppTypography.bodyMedium.copyWith(
                    color: scheme.onSurface,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ],
            ),
          ),
          if (copyable) ...[
            const SizedBox(width: 8),
            Icon(
              Icons.copy_rounded,
              size: 16,
              color: scheme.onSurface.withValues(alpha: 0.4),
            ),
          ],
        ],
      ),
    );

    if (!copyable) return body;

    return Material(
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
    );
  }
}
