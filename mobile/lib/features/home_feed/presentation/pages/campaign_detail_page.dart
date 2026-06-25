import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

import '../../../../app/theme/paysika/pa_colors.dart';
import '../../../../core/formatters/xaf_formatter.dart';
import '../../../social/domain/entities/reaction.dart';
import '../../../social/presentation/widgets/comments_section.dart';
import '../../../social/presentation/widgets/like_button.dart';
import '../../domain/entities/feed_item.dart';

/// Page detail d'une campagne micro-credit — meta + flyer + bloc social.
/// Reçoit le `CampaignFlyer` en `extra` du go_router (rendu instantane).
/// Le bouton "Demander un credit" pop avec l'id pour reutiliser la
/// pipeline existante du sheet credit pre-rempli sur la voie campagne.
class CampaignDetailPage extends ConsumerWidget {
  const CampaignDetailPage({super.key, required this.campaign});

  final CampaignFlyer campaign;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final c = campaign;
    final df = DateFormat('dd MMM yyyy', 'fr_FR');
    return Scaffold(
      backgroundColor: PaColors.canvas,
      appBar: AppBar(
        backgroundColor: PaColors.canvas,
        surfaceTintColor: PaColors.canvas,
        elevation: 0,
        scrolledUnderElevation: 0,
        iconTheme: const IconThemeData(color: PaColors.inkPrimary),
        title: const Text(
          'Campagne',
          style: TextStyle(
            color: PaColors.inkPrimary,
            fontSize: 17,
            fontWeight: FontWeight.w700,
          ),
        ),
      ),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(20, 8, 20, 40),
        children: [
          ClipRRect(
            borderRadius: BorderRadius.circular(20),
            child: AspectRatio(
              aspectRatio: 16 / 9,
              child: c.flyerUrl == null
                  ? Container(
                      color: PaColors.tealSurface,
                      alignment: Alignment.center,
                      child: const Icon(
                        Icons.campaign_outlined,
                        size: 56,
                        color: PaColors.teal,
                      ),
                    )
                  : CachedNetworkImage(
                      imageUrl: c.flyerUrl!,
                      fit: BoxFit.cover,
                      errorWidget: (_, __, ___) => Container(
                        color: PaColors.tealSurface,
                      ),
                    ),
            ),
          ),
          const SizedBox(height: 16),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
            decoration: BoxDecoration(
              color: PaColors.tealSurface,
              borderRadius: BorderRadius.circular(999),
            ),
            child: Text(
              c.profilCible.toUpperCase(),
              style: const TextStyle(
                color: PaColors.teal,
                fontSize: 11,
                fontWeight: FontWeight.w800,
                letterSpacing: 1.4,
              ),
            ),
          ),
          const SizedBox(height: 10),
          Text(
            c.nom,
            style: const TextStyle(
              color: PaColors.inkPrimary,
              fontSize: 22,
              fontWeight: FontWeight.w800,
              letterSpacing: -0.3,
              height: 1.25,
            ),
          ),
          const SizedBox(height: 14),
          Row(
            children: [
              const Icon(
                Icons.payments_outlined,
                size: 18,
                color: PaColors.teal,
              ),
              const SizedBox(width: 8),
              Text(
                '${XAFFormatter.formatCompact(c.montantMin)}  →  ${XAFFormatter.formatCompact(c.montantMax)}',
                style: const TextStyle(
                  color: PaColors.inkSecondary,
                  fontSize: 14,
                  fontWeight: FontWeight.w600,
                ),
              ),
              const Spacer(),
              Text(
                '${(c.tauxInteret * 100).toStringAsFixed(0)} %',
                style: const TextStyle(
                  color: PaColors.teal,
                  fontSize: 14,
                  fontWeight: FontWeight.w800,
                ),
              ),
            ],
          ),
          const SizedBox(height: 6),
          Text(
            'Cloture le ${df.format(c.dateFin)}',
            style: const TextStyle(
              color: PaColors.inkMuted,
              fontSize: 12.5,
            ),
          ),
          const SizedBox(height: 24),
          const Divider(color: PaColors.line, height: 1),
          const SizedBox(height: 16),
          LikeButton(
            target: SocialTarget(
              kind: SocialTargetKind.campaign,
              id: c.id,
            ),
          ),
          const SizedBox(height: 18),
          CommentsSection(
            target: SocialTarget(
              kind: SocialTargetKind.campaign,
              id: c.id,
            ),
          ),
        ],
      ),
    );
  }
}
