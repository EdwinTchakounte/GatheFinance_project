import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../app/theme/paysika/pa_colors.dart';
import '../../core/formatters/xaf_formatter.dart';
import '../../core/widgets/paysika/pa_card.dart';
import 'special_collections_notifier.dart';

/// Section « Collectes particulières » de l'accueil : deux cartes (caisse
/// scolaire, tontine alimentaire) qui mènent chacune à la vue dédiée.
class SpecialCollectionsSection extends ConsumerWidget {
  const SpecialCollectionsSection({super.key});

  static const _meta = <String, IconData>{
    'caisse_scolaire': Icons.school_rounded,
    'tontine_alimentaire': Icons.restaurant_rounded,
  };

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final notifier = ref.watch(specialCollectionsProvider.notifier);
    ref.watch(specialCollectionsProvider); // rebuild quand la liste change

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Padding(
          padding: EdgeInsets.fromLTRB(4, 0, 4, 10),
          child: Text(
            'Collectes particulières',
            style: TextStyle(
              color: PaColors.inkPrimary,
              fontSize: 15,
              fontWeight: FontWeight.w800,
            ),
          ),
        ),
        Row(
          children: [
            for (final entry in kSpecialCollectionTypes.entries) ...[
              Expanded(
                child: _CollectionCard(
                  title: entry.value,
                  icon: _meta[entry.key] ?? Icons.savings_rounded,
                  slot: notifier.slotFor(entry.key),
                  onTap: () =>
                      context.push('/special-collections/${entry.key}'),
                ),
              ),
              if (entry.key != kSpecialCollectionTypes.keys.last)
                const SizedBox(width: 12),
            ],
          ],
        ),
      ],
    );
  }
}

class _CollectionCard extends StatelessWidget {
  const _CollectionCard({
    required this.title,
    required this.icon,
    required this.slot,
    required this.onTap,
  });

  final String title;
  final IconData icon;
  final SpecialCollectionSlot? slot;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final (String hint, Color hintColor) = _hint();

    return InkWell(
      borderRadius: BorderRadius.circular(16),
      onTap: onTap,
      child: PaCard(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Container(
              width: 40,
              height: 40,
              decoration: BoxDecoration(
                color: PaColors.tealSurface,
                borderRadius: BorderRadius.circular(12),
              ),
              child: Icon(icon, color: PaColors.teal, size: 22),
            ),
            const SizedBox(height: 12),
            Text(
              title,
              style: const TextStyle(
                color: PaColors.inkPrimary,
                fontSize: 14,
                fontWeight: FontWeight.w700,
              ),
            ),
            const SizedBox(height: 3),
            Text(
              hint,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: TextStyle(
                color: hintColor,
                fontSize: 12,
                fontWeight: FontWeight.w600,
              ),
            ),
          ],
        ),
      ),
    );
  }

  (String, Color) _hint() {
    final s = slot;
    if (s == null || !s.hasOpenCycle) {
      return ('Pas de cycle en cours', PaColors.inkSecondary);
    }
    final m = s.membership;
    if (m == null) return ('Participer', PaColors.teal);
    switch (m.statut) {
      case 'valide':
        return ('${XAFFormatter.formatNumber(m.solde)} XAF', PaColors.teal);
      case 'en_attente':
        return ('En attente de validation', PaColors.warning);
      case 'rejete':
        return ('Demande refusée', PaColors.danger);
      default:
        return ('Participer', PaColors.teal);
    }
  }
}
