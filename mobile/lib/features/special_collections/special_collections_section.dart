import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../app/theme/paysika/pa_colors.dart';
import '../../core/formatters/xaf_formatter.dart';
import '../../core/widgets/paysika/pa_card.dart';
import 'special_collections_notifier.dart';

/// Style visuel propre à chaque type de collecte : icône, accent et teinte de
/// fond. Le fait de différencier les deux cartes (bleu / vert) casse l'effet
/// « deux boutons identiques » et donne un rendu plus vivant.
class _CardStyle {
  const _CardStyle({
    required this.icon,
    required this.accent,
    required this.accentLight,
    required this.surface,
    required this.tint,
  });

  final IconData icon;
  final Color accent; // fin du dégradé du badge + accents
  final Color accentLight; // début du dégradé du badge
  final Color surface; // fond du pill de statut « neutre »
  final Color tint; // bas du dégradé de fond de la carte
}

/// Section « Collectes particulières » de l'accueil : deux cartes premium
/// (caisse scolaire, tontine alimentaire) menant chacune à la vue dédiée.
class SpecialCollectionsSection extends ConsumerWidget {
  const SpecialCollectionsSection({super.key});

  static const _styles = <String, _CardStyle>{
    'caisse_scolaire': _CardStyle(
      icon: Icons.school_rounded,
      accent: PaColors.blue,
      accentLight: PaColors.navySoft,
      surface: Color(0xFFEDF2FF),
      tint: Color(0xFFF2F6FF),
    ),
    'tontine_alimentaire': _CardStyle(
      icon: Icons.restaurant_rounded,
      accent: PaColors.teal,
      accentLight: PaColors.tealLight,
      surface: PaColors.tealSurface,
      tint: Color(0xFFEDFAF4),
    ),
  };

  static const _fallback = _CardStyle(
    icon: Icons.savings_rounded,
    accent: PaColors.teal,
    accentLight: PaColors.tealLight,
    surface: PaColors.tealSurface,
    tint: Color(0xFFEDFAF4),
  );

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
        IntrinsicHeight(
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              for (final entry in kSpecialCollectionTypes.entries) ...[
                Expanded(
                  child: _CollectionCard(
                    title: entry.value,
                    style: _styles[entry.key] ?? _fallback,
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
        ),
      ],
    );
  }
}

class _CollectionCard extends StatelessWidget {
  const _CollectionCard({
    required this.title,
    required this.style,
    required this.slot,
    required this.onTap,
  });

  final String title;
  final _CardStyle style;
  final SpecialCollectionSlot? slot;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final hint = _hint();

    return PaCard(
      onTap: onTap,
      borderRadius: BorderRadius.circular(22),
      padding: const EdgeInsets.all(16),
      // Fond en dégradé blanc → teinte du type (bleu pâle / vert pâle) : plus
      // vivant que le blanc plat, sans agresser.
      gradient: LinearGradient(
        begin: Alignment.topLeft,
        end: Alignment.bottomRight,
        colors: [Colors.white, style.tint],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Badge icône : dégradé accent + halo coloré doux.
              Container(
                width: 46,
                height: 46,
                decoration: BoxDecoration(
                  gradient: LinearGradient(
                    begin: Alignment.topLeft,
                    end: Alignment.bottomRight,
                    colors: [style.accentLight, style.accent],
                  ),
                  borderRadius: BorderRadius.circular(15),
                  boxShadow: [
                    BoxShadow(
                      color: style.accent.withValues(alpha: 0.32),
                      blurRadius: 14,
                      offset: const Offset(0, 6),
                    ),
                  ],
                ),
                child: Icon(style.icon, color: Colors.white, size: 24),
              ),
              const Spacer(),
              // Flèche d'affordance dans une pastille translucide.
              Container(
                width: 28,
                height: 28,
                decoration: BoxDecoration(
                  color: Colors.white.withValues(alpha: 0.7),
                  shape: BoxShape.circle,
                ),
                child: Icon(
                  Icons.arrow_outward_rounded,
                  size: 15,
                  color: style.accent,
                ),
              ),
            ],
          ),
          const SizedBox(height: 14),
          Text(
            title,
            style: const TextStyle(
              color: PaColors.inkPrimary,
              fontSize: 14.5,
              fontWeight: FontWeight.w700,
              height: 1.15,
            ),
          ),
          const SizedBox(height: 10),
          // Statut en pill doux (bg teinté + point de couleur).
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
            decoration: BoxDecoration(
              color: hint.bg,
              borderRadius: BorderRadius.circular(999),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Container(
                  width: 6,
                  height: 6,
                  decoration: BoxDecoration(
                    color: hint.fg,
                    shape: BoxShape.circle,
                  ),
                ),
                const SizedBox(width: 6),
                Flexible(
                  child: Text(
                    hint.label,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(
                      color: hint.fg,
                      fontSize: 11.5,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  _Hint _hint() {
    final s = slot;
    if (s == null || !s.hasOpenCycle) {
      return const _Hint(
        'Pas de cycle en cours',
        PaColors.inkSecondary,
        Color(0xFFF1F3F6),
      );
    }
    final m = s.membership;
    if (m == null) {
      return _Hint('Participer', style.accent, style.surface);
    }
    switch (m.statut) {
      case 'valide':
        return _Hint(
          '${XAFFormatter.formatNumber(m.solde)} XAF',
          PaColors.success,
          PaColors.successSurface,
        );
      case 'en_attente':
        return const _Hint(
          'En attente',
          PaColors.warning,
          PaColors.warningSurface,
        );
      case 'rejete':
        return const _Hint(
          'Demande refusée',
          PaColors.danger,
          PaColors.dangerSurface,
        );
      default:
        return _Hint('Participer', style.accent, style.surface);
    }
  }
}

/// Libellé de statut + couleurs (texte/point, fond du pill).
class _Hint {
  const _Hint(this.label, this.fg, this.bg);
  final String label;
  final Color fg;
  final Color bg;
}
