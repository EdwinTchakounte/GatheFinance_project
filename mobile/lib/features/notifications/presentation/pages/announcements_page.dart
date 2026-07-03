import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../app/theme/paysika/pa_colors.dart';
import '../../../../core/widgets/paysika/pa_card.dart';
import '../../../../core/widgets/paysika/pa_pattern_background.dart';
import '../../../../core/widgets/skeleton.dart';
import '../../domain/entities/announcement.dart';
import '../state/announcements_provider.dart';
import 'announcement_detail_page.dart';

/// Onglet « Annonces » — liste des annonces de la coopérative. Chaque annonce
/// est cliquable pour lire la totalité + voir la pièce jointe.
class AnnouncementsPage extends ConsumerWidget {
  const AnnouncementsPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(announcementsProvider);
    return Scaffold(
      backgroundColor: PaColors.canvas,
      appBar: AppBar(
        backgroundColor: PaColors.canvas,
        surfaceTintColor: PaColors.canvas,
        elevation: 0,
        scrolledUnderElevation: 0,
        leading: IconButton(
          onPressed: () => Navigator.maybePop(context),
          icon:
              const Icon(Icons.arrow_back_rounded, color: PaColors.inkPrimary),
        ),
        title: const Text(
          'Annonces',
          style: TextStyle(
            color: PaColors.inkPrimary,
            fontSize: 17,
            fontWeight: FontWeight.w700,
          ),
        ),
      ),
      body: PaPatternBackground(
        child: RefreshIndicator(
          color: PaColors.teal,
          onRefresh: () async => ref.refresh(announcementsProvider.future),
          child: async.when(
            loading: () => ListView(
              padding: const EdgeInsets.all(16),
              children: List.generate(
                4,
                (_) => const Padding(
                  padding: EdgeInsets.only(bottom: 12),
                  child: Skeleton(height: 92, borderRadius: 18),
                ),
              ),
            ),
            error: (_, __) => _CenteredMessage(
              icon: Icons.wifi_off_rounded,
              text: 'Impossible de charger les annonces.',
              onRetry: () => ref.invalidate(announcementsProvider),
            ),
            data: (items) {
              if (items.isEmpty) {
                return const _CenteredMessage(
                  icon: Icons.campaign_outlined,
                  text: 'Aucune annonce pour le moment.',
                );
              }
              return ListView.separated(
                padding: const EdgeInsets.all(16),
                physics: const AlwaysScrollableScrollPhysics(),
                itemCount: items.length,
                separatorBuilder: (_, __) => const SizedBox(height: 12),
                itemBuilder: (_, i) => _AnnouncementTile(item: items[i]),
              );
            },
          ),
        ),
      ),
    );
  }
}

class _AnnouncementTile extends StatelessWidget {
  const _AnnouncementTile({required this.item});

  final Announcement item;

  @override
  Widget build(BuildContext context) {
    return PaCard(
      onTap: () => Navigator.of(context).push(
        MaterialPageRoute<void>(
          builder: (_) => AnnouncementDetailPage(announcement: item),
        ),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 40,
            height: 40,
            decoration: BoxDecoration(
              color: PaColors.teal.withValues(alpha: 0.12),
              borderRadius: BorderRadius.circular(12),
            ),
            child: const Icon(Icons.campaign_rounded,
                color: PaColors.teal, size: 22,),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  item.titre,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    color: PaColors.inkPrimary,
                    fontSize: 15,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  item.corps,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    color: PaColors.inkSecondary,
                    fontSize: 13,
                    height: 1.35,
                  ),
                ),
                if (item.hasImage) ...[
                  const SizedBox(height: 6),
                  const Row(
                    children: [
                      Icon(Icons.attach_file_rounded,
                          size: 14, color: PaColors.teal,),
                      SizedBox(width: 4),
                      Text(
                        'Pièce jointe',
                        style: TextStyle(
                          color: PaColors.teal,
                          fontSize: 12,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ],
                  ),
                ],
              ],
            ),
          ),
          const Icon(Icons.chevron_right_rounded, color: PaColors.inkMuted),
        ],
      ),
    );
  }
}

class _CenteredMessage extends StatelessWidget {
  const _CenteredMessage({
    required this.icon,
    required this.text,
    this.onRetry,
  });

  final IconData icon;
  final String text;
  final VoidCallback? onRetry;

  @override
  Widget build(BuildContext context) {
    return ListView(
      physics: const AlwaysScrollableScrollPhysics(),
      children: [
        const SizedBox(height: 120),
        Icon(icon, size: 44, color: PaColors.inkMuted),
        const SizedBox(height: 12),
        Text(
          text,
          textAlign: TextAlign.center,
          style: const TextStyle(color: PaColors.inkSecondary, fontSize: 14),
        ),
        if (onRetry != null) ...[
          const SizedBox(height: 12),
          Center(
            child: TextButton(
              onPressed: onRetry,
              child: const Text('Réessayer',
                  style: TextStyle(color: PaColors.teal),),
            ),
          ),
        ],
      ],
    );
  }
}
