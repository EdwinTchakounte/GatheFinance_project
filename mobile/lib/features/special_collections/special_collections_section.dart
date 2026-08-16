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
    // On lit l'état sans bloquer l'accueil : la liste peut être en cours de
    // chargement (les cartes affichent alors « Découvrir »).
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
                  type: entry.key,
                  title: entry.value,
                  icon: _meta[entry.key] ?? Icons.savings_rounded,
                  collection: notifier.byType(entry.key),
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
    required this.type,
    required this.title,
    required this.icon,
    required this.collection,
    required this.onTap,
  });

  final String type;
  final String title;
  final IconData icon;
  final SpecialCollection? collection;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final (String hint, Color hintColor) = switch (collection?.statut) {
      'valide' => (
          '${XAFFormatter.formatNumber(collection!.solde)} XAF',
          PaColors.teal
        ),
      'en_attente' => ('En attente de validation', PaColors.warning),
      'rejete' => ('Demande refusée', PaColors.danger),
      _ => ('Découvrir', PaColors.inkSecondary),
    };

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
}
