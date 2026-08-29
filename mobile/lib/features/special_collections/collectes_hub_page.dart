import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../app/theme/paysika/pa_colors.dart';
import '../../core/formatters/xaf_formatter.dart';
import '../../core/widgets/paysika/pa_card.dart';
import 'group_tontines_notifier.dart';
import 'special_collections_notifier.dart';

/// Page « Tontines & caisses » consolidée : caisse scolaire, tontine
/// alimentaire, et mes réunions (tontines de groupe) en une seule vue.
class CollectesHubPage extends ConsumerWidget {
  const CollectesHubPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    ref.watch(specialCollectionsProvider);
    final scNotifier = ref.read(specialCollectionsProvider.notifier);
    final groups = ref.watch(groupTontinesProvider);

    return Scaffold(
      backgroundColor: PaColors.canvas,
      appBar: AppBar(
        backgroundColor: PaColors.canvas,
        elevation: 0,
        title: const Text(
          'Tontines & caisses',
          style: TextStyle(color: PaColors.inkPrimary),
        ),
        iconTheme: const IconThemeData(color: PaColors.inkPrimary),
      ),
      body: SafeArea(
        child: RefreshIndicator(
          color: PaColors.teal,
          onRefresh: () async {
            await ref.read(specialCollectionsProvider.notifier).refresh();
            await ref.read(groupTontinesProvider.notifier).refresh();
          },
          child: ListView(
            padding: const EdgeInsets.fromLTRB(20, 12, 20, 24),
            children: [
              _sectionTitle('Collectes particulières'),
              const SizedBox(height: 8),
              for (final entry in kSpecialCollectionTypes.entries)
                _TypeTile(
                  title: entry.value,
                  icon: entry.key == 'caisse_scolaire'
                      ? Icons.school_rounded
                      : Icons.restaurant_rounded,
                  subtitle: _scSubtitle(scNotifier.slotFor(entry.key)),
                  onTap: () =>
                      context.push('/special-collections/${entry.key}'),
                ),
              const SizedBox(height: 20),
              _sectionTitle('Mes réunions (tontines de groupe)'),
              const SizedBox(height: 8),
              groups.when(
                loading: () => const Padding(
                  padding: EdgeInsets.all(16),
                  child: Center(
                    child: CircularProgressIndicator(color: PaColors.teal),
                  ),
                ),
                error: (_, __) => const Text(
                  'Réunions indisponibles.',
                  style: TextStyle(color: PaColors.inkSecondary),
                ),
                data: (list) => list.isEmpty
                    ? const Padding(
                        padding: EdgeInsets.symmetric(vertical: 8),
                        child: Text(
                          'Tu ne fais partie d\'aucune réunion pour le moment.',
                          style: TextStyle(
                            color: PaColors.inkSecondary,
                            fontSize: 13,
                          ),
                        ),
                      )
                    : Column(
                        children: [
                          for (final g in list)
                            _TypeTile(
                              title: g.nom,
                              icon: Icons.groups_rounded,
                              subtitle:
                                  '${XAFFormatter.formatNumber(g.solde)} XAF en cagnotte · ${g.membersCount} membre(s)'
                                  '${g.isOpen ? '' : ' · clôturée'}',
                              onTap: () =>
                                  context.push('/group-tontines/${g.id}'),
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

  String _scSubtitle(SpecialCollectionSlot? slot) {
    if (slot == null || !slot.hasOpenCycle) return 'Aucune collecte en cours';
    if (!slot.hasCarnet) return 'Carnet requis pour verser';
    return '${slot.cycles.length} collecte(s) ouverte(s)';
  }

  Widget _sectionTitle(String t) => Text(
        t,
        style: const TextStyle(
          color: PaColors.inkSecondary,
          fontSize: 11,
          fontWeight: FontWeight.w700,
          letterSpacing: 1.1,
        ),
      );
}

class _TypeTile extends StatelessWidget {
  const _TypeTile({
    required this.title,
    required this.icon,
    required this.subtitle,
    required this.onTap,
  });

  final String title;
  final IconData icon;
  final String subtitle;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: PaCard(
        padding: EdgeInsets.zero,
        child: InkWell(
          borderRadius: BorderRadius.circular(16),
          onTap: onTap,
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Row(
              children: [
                Container(
                  width: 42,
                  height: 42,
                  decoration: BoxDecoration(
                    color: PaColors.tealSurface,
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Icon(icon, color: PaColors.teal, size: 22),
                ),
                const SizedBox(width: 14),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        title,
                        style: const TextStyle(
                          color: PaColors.inkPrimary,
                          fontSize: 15,
                          fontWeight: FontWeight.w800,
                        ),
                      ),
                      const SizedBox(height: 2),
                      Text(
                        subtitle,
                        style: const TextStyle(
                          color: PaColors.inkSecondary,
                          fontSize: 12.5,
                        ),
                      ),
                    ],
                  ),
                ),
                const Icon(
                  Icons.chevron_right_rounded,
                  color: PaColors.inkMuted,
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
