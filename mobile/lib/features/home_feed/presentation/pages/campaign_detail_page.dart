import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

import '../../../../app/theme/paysika/pa_colors.dart';
import '../../../../core/formatters/xaf_formatter.dart';
import '../../../loans/presentation/state/loans_notifier.dart';
import '../../../loans/presentation/widgets/loan_request_sheet.dart';
import '../../../social/domain/entities/reaction.dart';
import '../../../social/presentation/widgets/comments_section.dart';
import '../../../social/presentation/widgets/like_button.dart';
import '../../domain/entities/feed_item.dart';

/// Detail d'une campagne micro-credit avec :
///  * Visuel hero (flyer ou photo stock servie par le backend)
///  * Bandeau profil cible + montants + taux + cloture
///  * Section "Comment postuler" (chronologie 4 etapes)
///  * Section "Documents requis" (par profil cible)
///  * CTA "Postuler maintenant" en bas (ouvre LoanRequestSheet pre-rempli)
///  * Bloc social (like + commentaires)
class CampaignDetailPage extends ConsumerWidget {
  const CampaignDetailPage({super.key, required this.campaign});

  final CampaignFlyer campaign;

  /// Documents requis par profil cible . derive d'un mapping cote client
  /// (court terme) pour souligner ce qu'il faut joindre. Le serveur n'impose
  /// pas (pour l'instant) une liste stricte de pieces, c'est l'instruction
  /// du comite qui peut demander des complements.
  List<String> _docsForProfil(String profil) {
    final p = profil.toLowerCase();
    final common = ['Pièce d\'identité (CNI ou passeport)'];
    if (p.contains('commerc')) {
      return [
        ...common,
        'Photo de votre boutique / point de vente',
        'Autorisation marché ou bail commercial',
        'Numéro Mobile Money de réception',
      ];
    }
    if (p.contains('parent')) {
      return [
        ...common,
        'Acte de naissance de l\'enfant',
        'Certificat de scolarité / facture frais scolaires',
        'Numéro Mobile Money de réception',
      ];
    }
    if (p.contains('agric')) {
      return [
        ...common,
        'Photo du champ ou de l\'exploitation',
        'Acte de propriété, bail rural ou attestation chefferie',
        'Numéro Mobile Money de réception',
      ];
    }
    return [
      ...common,
      'Justificatif de votre activité (photo, attestation)',
      'Numéro Mobile Money de réception',
    ];
  }

  /// Ouvre la sheet de demande de credit pre-remplie sur la voie campagne.
  /// On charge l'eligibilite au prealable (necessaire au sheet pour borner
  /// montant + duree). Si pas eligible, on previent.
  Future<void> _onApply(BuildContext context, WidgetRef ref) async {
    // Force un fetch frais . l'eligibilite peut bouger entre 2 ouvertures.
    await ref.read(eligibilityProvider.notifier).refresh();
    final eligibility = ref.read(eligibilityProvider).valueOrNull;
    if (!context.mounted) return;
    if (eligibility == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Impossible de vérifier ton éligibilité. Réessaie.')),
      );
      return;
    }
    await LoanRequestSheet.show(
      context,
      eligibility,
      prefillCampaignId: campaign.id,
    );
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final c = campaign;
    final df = DateFormat('dd MMM yyyy', 'fr_FR');
    final daysLeft = c.dateFin.difference(DateTime.now()).inDays;
    final docs = _docsForProfil(c.profilCible);
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
      bottomNavigationBar: SafeArea(
        minimum: const EdgeInsets.fromLTRB(20, 8, 20, 14),
        child: _ApplyButton(onTap: () => _onApply(context, ref)),
      ),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(20, 8, 20, 24),
        children: [
          // ── Hero flyer ──────────────────────────────────────────────
          ClipRRect(
            borderRadius: BorderRadius.circular(20),
            child: AspectRatio(
              aspectRatio: 16 / 9,
              child: CachedNetworkImage(
                imageUrl: c.flyerUrl ?? '',
                fit: BoxFit.cover,
                errorWidget: (_, __, ___) =>
                    Container(color: PaColors.tealSurface),
                placeholder: (_, __) =>
                    Container(color: PaColors.tealSurface),
              ),
            ),
          ),
          const SizedBox(height: 16),

          // ── Meta (profil + nom + montants + taux + cloture) ───────
          Row(
            children: [
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
              const Spacer(),
              if (daysLeft >= 0)
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                  decoration: BoxDecoration(
                    color: daysLeft <= 7
                        ? PaColors.dangerSurface
                        : PaColors.cardBg,
                    borderRadius: BorderRadius.circular(999),
                  ),
                  child: Text(
                    daysLeft == 0
                        ? 'Clôture aujourd\'hui'
                        : '$daysLeft j restants',
                    style: TextStyle(
                      color: daysLeft <= 7 ? PaColors.danger : PaColors.inkSecondary,
                      fontSize: 11,
                      fontWeight: FontWeight.w800,
                      letterSpacing: 0.3,
                    ),
                  ),
                ),
            ],
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
          // Onboarding 2026 — mention « sans frais » si l'admin a fixé des
          // frais d'étude à 0 sur la campagne.
          if (c.sansFrais) ...[
            const SizedBox(height: 12),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
              decoration: BoxDecoration(
                color: PaColors.success.withValues(alpha: 0.12),
                borderRadius: BorderRadius.circular(999),
              ),
              child: const Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(Icons.verified_outlined, size: 15, color: PaColors.success),
                  SizedBox(width: 6),
                  Text(
                    'Sans frais de dossier',
                    style: TextStyle(
                      color: PaColors.success,
                      fontSize: 12.5,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ],
              ),
            ),
          ],
          const SizedBox(height: 14),
          _MetaRow(
            icon: Icons.payments_outlined,
            label: 'Montant',
            value:
                '${XAFFormatter.formatCompact(c.montantMin)}  →  ${XAFFormatter.formatCompact(c.montantMax)}',
          ),
          _MetaRow(
            icon: Icons.percent_outlined,
            label: 'Taux flat',
            value: '${(c.tauxInteret * 100).toStringAsFixed(0)} %',
          ),
          _MetaRow(
            icon: Icons.event_outlined,
            label: 'Clôture',
            value: df.format(c.dateFin),
          ),

          const SizedBox(height: 24),
          const _SectionDivider(),

          // ── Chronologie : comment postuler ─────────────────────────
          const _SectionTitle(
            icon: Icons.timeline_rounded,
            text: 'Comment postuler',
          ),
          const SizedBox(height: 12),
          const _TimelineStep(
            num: '01',
            title: 'Tu remplis ta demande',
            body: 'Montant souhaité, motif, modalité . depuis le bouton « Postuler ». Joins tes pièces directement dans le formulaire.',
            done: true,
          ),
          const _TimelineStep(
            num: '02',
            title: 'Le comité examine sous 7 jours',
            body: 'Statut : « En validation campagne ». Le comité peut te demander un complément. Tu reçois une notification dès qu\'une décision est prise.',
          ),
          const _TimelineStep(
            num: '03',
            title: 'Décaissement Mobile Money',
            body: 'Si approuvé, le montant arrive sur ton numéro MoMo sous 24 à 48 h. Tu reçois une note PDF récapitulative.',
          ),
          _TimelineStep(
            num: '04',
            title: 'Remboursement par collectes',
            body: 'Tu rembourses en ${c.nbJoursRecouvrementOrDefault()} jours via les collectes journalières dédiées à la campagne. Aucun avaliste requis.',
            last: true,
          ),

          const SizedBox(height: 16),
          const _SectionDivider(),

          // ── Documents requis ───────────────────────────────────────
          const _SectionTitle(
            icon: Icons.folder_open_rounded,
            text: 'Documents à fournir',
          ),
          const SizedBox(height: 8),
          Text(
            'Adaptés au profil « ${c.profilCible} » . joints au moment de la soumission :',
            style: const TextStyle(
              color: PaColors.inkSecondary,
              fontSize: 13,
              height: 1.45,
            ),
          ),
          const SizedBox(height: 10),
          for (final d in docs) _DocBullet(text: d),

          const SizedBox(height: 8),
          Container(
            padding: const EdgeInsets.fromLTRB(12, 10, 12, 12),
            decoration: BoxDecoration(
              color: PaColors.tealSurface,
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: PaColors.teal.withValues(alpha: 0.25)),
            ),
            child: const Row(
              children: [
                Icon(Icons.info_outline_rounded, size: 18, color: PaColors.tealDark),
                SizedBox(width: 10),
                Expanded(
                  child: Text(
                    'Voie campagne : pas d\'épargne préalable ni d\'avaliste requis . la coopérative assume le risque.',
                    style: TextStyle(
                      color: PaColors.tealDark,
                      fontSize: 12.5,
                      fontWeight: FontWeight.w600,
                      height: 1.4,
                    ),
                  ),
                ),
              ],
            ),
          ),

          const SizedBox(height: 24),
          const _SectionDivider(),

          // ── Bloc social ────────────────────────────────────────────
          const SizedBox(height: 14),
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

// ─────────────────────────────────────────────────────────────────────
// Mini widgets
// ─────────────────────────────────────────────────────────────────────

class _ApplyButton extends StatelessWidget {
  const _ApplyButton({required this.onTap});
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(16),
        child: Container(
          height: 54,
          decoration: BoxDecoration(
            gradient: const LinearGradient(
              colors: [PaColors.teal, PaColors.blue],
            ),
            borderRadius: BorderRadius.circular(16),
            boxShadow: [
              BoxShadow(
                color: PaColors.teal.withValues(alpha: 0.30),
                blurRadius: 14,
                offset: const Offset(0, 6),
              ),
            ],
          ),
          alignment: Alignment.center,
          child: const Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(Icons.rocket_launch_rounded, color: Colors.white, size: 20),
              SizedBox(width: 10),
              Text(
                'Postuler maintenant',
                style: TextStyle(
                  color: Colors.white,
                  fontSize: 15.5,
                  fontWeight: FontWeight.w800,
                  letterSpacing: 0.1,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _MetaRow extends StatelessWidget {
  const _MetaRow({required this.icon, required this.label, required this.value});
  final IconData icon;
  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        children: [
          Icon(icon, size: 18, color: PaColors.teal),
          const SizedBox(width: 10),
          Text(
            label,
            style: const TextStyle(
              color: PaColors.inkMuted,
              fontSize: 13,
              fontWeight: FontWeight.w500,
            ),
          ),
          const Spacer(),
          Text(
            value,
            style: const TextStyle(
              color: PaColors.inkPrimary,
              fontSize: 14,
              fontWeight: FontWeight.w700,
            ),
          ),
        ],
      ),
    );
  }
}

class _SectionTitle extends StatelessWidget {
  const _SectionTitle({required this.icon, required this.text});
  final IconData icon;
  final String text;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(top: 14, bottom: 2),
      child: Row(
        children: [
          Container(
            width: 30,
            height: 30,
            decoration: BoxDecoration(
              color: PaColors.tealSurface,
              borderRadius: BorderRadius.circular(8),
            ),
            alignment: Alignment.center,
            child: Icon(icon, color: PaColors.teal, size: 16),
          ),
          const SizedBox(width: 10),
          Text(
            text,
            style: const TextStyle(
              color: PaColors.inkPrimary,
              fontSize: 16,
              fontWeight: FontWeight.w800,
              letterSpacing: -0.2,
            ),
          ),
        ],
      ),
    );
  }
}

class _SectionDivider extends StatelessWidget {
  const _SectionDivider();
  @override
  Widget build(BuildContext context) {
    return const Divider(color: PaColors.line, height: 1);
  }
}

class _TimelineStep extends StatelessWidget {
  const _TimelineStep({
    required this.num,
    required this.title,
    required this.body,
    this.done = false,
    this.last = false,
  });
  final String num;
  final String title;
  final String body;
  final bool done;
  final bool last;

  @override
  Widget build(BuildContext context) {
    return IntrinsicHeight(
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Colonne timeline : pastille + ligne verticale
          Column(
            children: [
              Container(
                width: 30,
                height: 30,
                decoration: BoxDecoration(
                  color: done ? PaColors.teal : PaColors.tealSurface,
                  shape: BoxShape.circle,
                  border: Border.all(color: PaColors.teal, width: 1.5),
                ),
                alignment: Alignment.center,
                child: Text(
                  num,
                  style: TextStyle(
                    color: done ? Colors.white : PaColors.tealDark,
                    fontSize: 11,
                    fontWeight: FontWeight.w800,
                  ),
                ),
              ),
              if (!last)
                Expanded(
                  child: Container(
                    width: 2,
                    color: PaColors.teal.withValues(alpha: 0.25),
                  ),
                ),
            ],
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Padding(
              padding: const EdgeInsets.only(bottom: 16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Padding(
                    padding: const EdgeInsets.only(top: 4),
                    child: Text(
                      title,
                      style: const TextStyle(
                        color: PaColors.inkPrimary,
                        fontSize: 14,
                        fontWeight: FontWeight.w800,
                        letterSpacing: -0.1,
                      ),
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    body,
                    style: const TextStyle(
                      color: PaColors.inkSecondary,
                      fontSize: 13,
                      height: 1.45,
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _DocBullet extends StatelessWidget {
  const _DocBullet({required this.text});
  final String text;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            margin: const EdgeInsets.only(top: 5),
            width: 18,
            height: 18,
            decoration: const BoxDecoration(
              color: PaColors.tealSurface,
              shape: BoxShape.circle,
            ),
            alignment: Alignment.center,
            child: const Icon(Icons.check_rounded,
                size: 12, color: PaColors.tealDark,),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              text,
              style: const TextStyle(
                color: PaColors.inkPrimary,
                fontSize: 13.5,
                height: 1.45,
                fontWeight: FontWeight.w500,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

extension on CampaignFlyer {
  /// La duree de recouvrement n'est pas dans l'entite mobile actuelle ;
  /// on retombe sur "60" par defaut, qui correspond au pattern le plus
  /// frequent (commercants). On affiche un texte coherent meme si le
  /// chiffre exact reste cote backend.
  String nbJoursRecouvrementOrDefault() => '60 à 120';
}
