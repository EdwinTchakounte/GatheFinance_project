import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../app/theme/paysika/pa_colors.dart';
import '../../../../app/theme/app_radii.dart';
import '../../../../app/theme/app_spacing.dart';
import '../../../../app/theme/app_typography.dart';
import '../state/theme_mode_notifier.dart';

/// Bottom sheet de choix du thème . Système / Clair / Sombre.
///
/// Affiche un libellé, une description, un mini aperçu visuel (chip) et
/// un radio coché pour le mode actuel. Le choix est persisté immédiatement
/// dans SharedPreferences via [ThemeModeNotifier].
class ThemeChoiceSheet extends ConsumerWidget {
  const ThemeChoiceSheet({super.key});

  static Future<void> show(BuildContext context) {
    return showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => const ThemeChoiceSheet(),
    );
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final current = ref.watch(themeModeProvider).valueOrNull ?? ThemeMode.system;

    return DraggableScrollableSheet(
      initialChildSize: 0.5,
      minChildSize: 0.35,
      maxChildSize: 0.7,
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
              // Drag handle
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
              Text('Choisir le thème', style: AppTypography.headingMedium),
              const SizedBox(height: 4),
              Text(
                'Sélectionne l\'apparence de l\'application. '
                'Le réglage est conservé sur cet appareil.',
                style: AppTypography.bodySmall.copyWith(
                  color: PaColors.inkSecondary,
                ),
              ),
              const SizedBox(height: AppSpacing.l),
              _ThemeOption(
                mode: ThemeMode.system,
                current: current,
                label: 'Automatique',
                subtitle: 'Suit les réglages de ton téléphone.',
                icon: Icons.brightness_auto_outlined,
                previewColors: const [Color(0xFFFAF6EF), Color(0xFF101626)],
                onTap: () => _select(context, ref, ThemeMode.system),
              ),
              const SizedBox(height: AppSpacing.s),
              _ThemeOption(
                mode: ThemeMode.light,
                current: current,
                label: 'Clair',
                subtitle: 'Fonds cream et accents cobalt.',
                icon: Icons.light_mode_outlined,
                previewColors: const [Color(0xFFFAF6EF), Color(0xFFFFFFFF)],
                onTap: () => _select(context, ref, ThemeMode.light),
              ),
              const SizedBox(height: AppSpacing.s),
              _ThemeOption(
                mode: ThemeMode.dark,
                current: current,
                label: 'Sombre',
                subtitle: 'Confort nocturne, fonds cobalt profond.',
                icon: Icons.dark_mode_outlined,
                previewColors: const [Color(0xFF101626), Color(0xFF161D30)],
                onTap: () => _select(context, ref, ThemeMode.dark),
              ),
            ],
          ),
        );
      },
    );
  }

  Future<void> _select(BuildContext context, WidgetRef ref, ThemeMode mode) async {
    unawaited(HapticFeedback.selectionClick());
    await ref.read(themeModeProvider.notifier).setMode(mode);
    if (!context.mounted) return;
    Navigator.of(context).pop();
  }
}


class _ThemeOption extends StatelessWidget {
  const _ThemeOption({
    required this.mode,
    required this.current,
    required this.label,
    required this.subtitle,
    required this.icon,
    required this.previewColors,
    required this.onTap,
  });

  final ThemeMode mode;
  final ThemeMode current;
  final String label;
  final String subtitle;
  final IconData icon;
  final List<Color> previewColors;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final selected = mode == current;
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
              // Mini preview gradient (2 couleurs)
              Container(
                width: 44,
                height: 44,
                decoration: BoxDecoration(
                  gradient: LinearGradient(
                    begin: Alignment.topLeft,
                    end: Alignment.bottomRight,
                    colors: previewColors,
                  ),
                  borderRadius: const BorderRadius.all(AppRadii.r12),
                  border: Border.all(
                    color: scheme.outline.withValues(alpha: 0.5),
                    width: 0.5,
                  ),
                ),
                child: Icon(
                  icon,
                  size: 20,
                  color: previewColors.first.computeLuminance() > 0.5
                      ? PaColors.navy
                      : Colors.white,
                ),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(label, style: AppTypography.labelLarge),
                    const SizedBox(height: 2),
                    Text(
                      subtitle,
                      style: AppTypography.bodySmall.copyWith(
                        color: scheme.onSurface.withValues(alpha: 0.6),
                      ),
                    ),
                  ],
                ),
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
