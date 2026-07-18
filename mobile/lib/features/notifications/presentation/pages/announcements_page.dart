import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../app/theme/paysika/pa_colors.dart';
import '../../../../core/formatters/date_formatter.dart';
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
      body: const PaPatternBackground(child: AnnouncementsBody()),
    );
  }
}

/// Corps réutilisable de la liste des annonces (sans Scaffold/AppBar) — utilisé
/// tel quel comme onglet dans la page « Annonces » et par [AnnouncementsPage].
class AnnouncementsBody extends ConsumerWidget {
  const AnnouncementsBody({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(announcementsProvider);
    return RefreshIndicator(
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
    );
  }
}

class _AnnouncementTile extends StatelessWidget {
  const _AnnouncementTile({required this.item});

  final Announcement item;

  @override
  Widget build(BuildContext context) {
    final date = item.publishedAt;
    return PaCard(
      padding: EdgeInsets.zero,
      onTap: () => Navigator.of(context).push(
        MaterialPageRoute<void>(
          builder: (_) => AnnouncementDetailPage(announcement: item),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Couverture affichée directement pour les annonces avec image.
          if (item.hasImage)
            ClipRRect(
              borderRadius: const BorderRadius.vertical(top: Radius.circular(16)),
              child: AspectRatio(
                aspectRatio: 16 / 9,
                child: CachedNetworkImage(
                  imageUrl: item.imageUrl!,
                  fit: BoxFit.cover,
                  memCacheWidth: 720,
                  placeholder: (_, __) => const _ImgFallback(),
                  errorWidget: (_, __, ___) => const _ImgFallback(),
                ),
              ),
            ),
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 14, 16, 14),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    const Icon(Icons.campaign_rounded,
                        size: 15, color: PaColors.teal,),
                    const SizedBox(width: 6),
                    Text(
                      date != null
                          ? AppDateFormatter.long(date).toUpperCase()
                          : 'ANNONCE',
                      style: const TextStyle(
                        color: PaColors.inkMuted,
                        fontSize: 10.5,
                        fontWeight: FontWeight.w800,
                        letterSpacing: 0.6,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 8),
                Text(
                  item.titre,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    color: PaColors.inkPrimary,
                    fontSize: 16,
                    fontWeight: FontWeight.w700,
                    height: 1.3,
                  ),
                ),
                if (item.corps.isNotEmpty) ...[
                  const SizedBox(height: 6),
                  Text(
                    item.corps,
                    maxLines: 3,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                      color: PaColors.inkSecondary,
                      fontSize: 13,
                      height: 1.45,
                    ),
                  ),
                ],
                const SizedBox(height: 10),
                const Row(
                  children: [
                    Text(
                      'Lire l\'annonce',
                      style: TextStyle(
                        color: PaColors.teal,
                        fontSize: 13,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    SizedBox(width: 3),
                    Icon(Icons.arrow_forward_rounded,
                        size: 17, color: PaColors.teal,),
                  ],
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

/// Fond de repli quand l'image d'annonce est absente / en erreur.
class _ImgFallback extends StatelessWidget {
  const _ImgFallback();
  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: const BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [PaColors.tealSurface, Color(0xFFD7EFE5)],
        ),
      ),
      alignment: Alignment.center,
      child: const Icon(Icons.campaign_rounded, color: PaColors.teal, size: 40),
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
