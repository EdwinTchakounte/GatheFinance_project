import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../app/theme/paysika/pa_colors.dart';
import '../../../../app/theme/app_radii.dart';
import '../../../../app/theme/app_spacing.dart';
import '../../../../app/theme/app_typography.dart';
import '../../../../l10n/gen/app_localizations.dart';
import '../state/locale_notifier.dart';

/// Bottom sheet de choix de la langue . Français / English.
///
/// Le choix est persisté immédiatement et l'application bascule de
/// langue sans relancement (MaterialApp écoute le provider).
class LanguageChoiceSheet extends ConsumerWidget {
  const LanguageChoiceSheet({super.key});

  static Future<void> show(BuildContext context) {
    return showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => const LanguageChoiceSheet(),
    );
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final current =
        ref.watch(localeProvider).valueOrNull ?? const Locale('fr');
    final l = AppL10n.of(context);

    return DraggableScrollableSheet(
      initialChildSize: 0.42,
      minChildSize: 0.3,
      maxChildSize: 0.6,
      expand: false,
      builder: (context, scroll) {
        return Container(
          decoration: BoxDecoration(
            color: Theme.of(context).colorScheme.surface,
            borderRadius: const BorderRadius.vertical(top: AppRadii.r24),
          ),
          child: ListView(
            controller: scroll,
            padding: const EdgeInsets.fromLTRB(
              AppSpacing.screenH,
              12,
              AppSpacing.screenH,
              AppSpacing.huge,
            ),
            children: [
              Center(
                child: Container(
                  width: 40,
                  height: 4,
                  margin: const EdgeInsets.only(bottom: 18),
                  decoration: BoxDecoration(
                    color: PaColors.inkMuted.withValues(alpha: 0.35),
                    borderRadius: BorderRadius.circular(2),
                  ),
                ),
              ),
              Text(l.language_choice_title, style: AppTypography.headingMedium),
              const SizedBox(height: 4),
              Text(
                l.language_choice_desc,
                style: AppTypography.bodySmall.copyWith(
                  color: PaColors.inkSecondary,
                ),
              ),
              const SizedBox(height: AppSpacing.l),
              _LanguageOption(
                code: 'fr',
                current: current,
                label: l.language_french,
                flag: '🇫🇷',
                onTap: () => _select(context, ref, 'fr'),
              ),
              const SizedBox(height: AppSpacing.s),
              _LanguageOption(
                code: 'en',
                current: current,
                label: l.language_english,
                flag: '🇬🇧',
                onTap: () => _select(context, ref, 'en'),
              ),
            ],
          ),
        );
      },
    );
  }

  Future<void> _select(BuildContext context, WidgetRef ref, String code) async {
    unawaited(HapticFeedback.selectionClick());
    await ref.read(localeProvider.notifier).setCode(code);
    if (!context.mounted) return;
    Navigator.of(context).pop();
  }
}


class _LanguageOption extends StatelessWidget {
  const _LanguageOption({
    required this.code,
    required this.current,
    required this.label,
    required this.flag,
    required this.onTap,
  });

  final String code;
  final Locale current;
  final String label;
  final String flag;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final selected = code == current.languageCode;
    final scheme = Theme.of(context).colorScheme;

    return Material(
      color: selected
          ? scheme.primary.withValues(alpha: 0.08)
          : Colors.transparent,
      borderRadius: const BorderRadius.all(AppRadii.r16),
      child: InkWell(
        onTap: onTap,
        borderRadius: const BorderRadius.all(AppRadii.r16),
        child: Container(
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(
            borderRadius: const BorderRadius.all(AppRadii.r16),
            border: Border.all(
              color: selected ? scheme.primary : scheme.outline,
              width: selected ? 1.5 : 1,
            ),
          ),
          child: Row(
            children: [
              Container(
                width: 44,
                height: 44,
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  color: scheme.surfaceContainerHighest,
                  borderRadius: const BorderRadius.all(AppRadii.r12),
                ),
                child: Text(flag, style: const TextStyle(fontSize: 22)),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Text(label, style: AppTypography.labelLarge),
              ),
              const SizedBox(width: 8),
              Icon(
                selected
                    ? Icons.radio_button_checked_rounded
                    : Icons.radio_button_unchecked_rounded,
                color: selected
                    ? scheme.primary
                    : scheme.onSurface.withValues(alpha: 0.4),
                size: 22,
              ),
            ],
          ),
        ),
      ),
    );
  }
}
