import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../app/theme/paysika/pa_colors.dart';
import '../../../../core/widgets/paysika/pa_card.dart';
import '../../../../l10n/gen/app_localizations.dart';
import '../state/collecte_eom_notifier.dart';

/// Carte « Fin de mois collecte » — le membre choisit ce qui arrive à son solde
/// de collecte à la clôture mensuelle : retrait cash ou bascule vers l'épargne.
class CollecteEomCard extends ConsumerWidget {
  const CollecteEomCard({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = AppL10n.of(context);
    final async = ref.watch(collecteEomProvider);
    final current = async.valueOrNull ?? 'cash';

    return PaCard(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.event_available_rounded,
                  size: 18, color: PaColors.teal,),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  l.collecte_eom_title,
                  style: const TextStyle(
                    color: PaColors.inkPrimary,
                    fontSize: 14.5,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 4),
          Text(
            l.collecte_eom_sub,
            style: const TextStyle(color: PaColors.inkMuted, fontSize: 12.5),
          ),
          const SizedBox(height: 14),
          _Option(
            selected: current == 'cash',
            icon: Icons.payments_outlined,
            title: l.collecte_eom_cash,
            desc: l.collecte_eom_cash_desc,
            onTap: () =>
                ref.read(collecteEomProvider.notifier).setPreference('cash'),
          ),
          const SizedBox(height: 10),
          _Option(
            selected: current == 'epargne',
            icon: Icons.savings_outlined,
            title: l.collecte_eom_savings,
            desc: l.collecte_eom_savings_desc,
            onTap: () =>
                ref.read(collecteEomProvider.notifier).setPreference('epargne'),
          ),
        ],
      ),
    );
  }
}

class _Option extends StatelessWidget {
  const _Option({
    required this.selected,
    required this.icon,
    required this.title,
    required this.desc,
    required this.onTap,
  });

  final bool selected;
  final IconData icon;
  final String title;
  final String desc;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(14),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 160),
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: selected ? PaColors.tealSurface : PaColors.paper,
          borderRadius: BorderRadius.circular(14),
          border: Border.all(
            color: selected ? PaColors.teal : PaColors.line,
            width: selected ? 1.5 : 1,
          ),
        ),
        child: Row(
          children: [
            Icon(icon,
                size: 20, color: selected ? PaColors.teal : PaColors.inkMuted,),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    title,
                    style: TextStyle(
                      color: selected ? PaColors.tealDark : PaColors.inkPrimary,
                      fontSize: 13.5,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    desc,
                    style: const TextStyle(
                      color: PaColors.inkMuted,
                      fontSize: 12,
                      height: 1.3,
                    ),
                  ),
                ],
              ),
            ),
            if (selected)
              const Icon(Icons.check_circle_rounded,
                  size: 20, color: PaColors.teal,),
          ],
        ),
      ),
    );
  }
}
