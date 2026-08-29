import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../app/theme/paysika/pa_colors.dart';
import '../../core/formatters/xaf_formatter.dart';
import '../../core/widgets/paysika/pa_card.dart';
import 'group_tontines_notifier.dart';
import 'special_collections_notifier.dart';

/// Section d'accueil « Tontines & caisses » — UNE seule carte consolidée avec
/// un bouton « + » qui ouvre la page listant la totalité (caisse scolaire,
/// tontine alimentaire, mes réunions de groupe).
class SpecialCollectionsSection extends ConsumerWidget {
  const SpecialCollectionsSection({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    ref.watch(specialCollectionsProvider);
    final groups = ref.watch(groupTontinesProvider);
    final myGroups = groups.valueOrNull ?? const <GroupTontineSummary>[];
    final potTotal = myGroups.fold<num>(0, (acc, g) => acc + g.solde);

    return PaCard(
      padding: EdgeInsets.zero,
      child: InkWell(
        borderRadius: BorderRadius.circular(16),
        onTap: () => context.push('/collectes'),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Row(
            children: [
              Container(
                width: 46,
                height: 46,
                decoration: BoxDecoration(
                  gradient: const LinearGradient(
                    colors: [PaColors.tealLight, PaColors.teal],
                    begin: Alignment.topLeft,
                    end: Alignment.bottomRight,
                  ),
                  borderRadius: BorderRadius.circular(13),
                ),
                child: const Icon(
                  Icons.savings_rounded,
                  color: Colors.white,
                  size: 24,
                ),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      'Tontines & caisses',
                      style: TextStyle(
                        color: PaColors.inkPrimary,
                        fontSize: 15,
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      myGroups.isEmpty
                          ? 'Caisse scolaire, tontine, réunions…'
                          : '${myGroups.length} réunion(s) · ${XAFFormatter.formatNumber(potTotal)} XAF en cagnotte',
                      style: const TextStyle(
                        color: PaColors.inkSecondary,
                        fontSize: 12.5,
                      ),
                    ),
                  ],
                ),
              ),
              Container(
                width: 34,
                height: 34,
                decoration: BoxDecoration(
                  color: PaColors.tealSurface,
                  borderRadius: BorderRadius.circular(10),
                ),
                child: const Icon(
                  Icons.add_rounded,
                  color: PaColors.teal,
                  size: 22,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
