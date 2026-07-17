import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../app/theme/paysika/pa_colors.dart';
import '../../../../core/widgets/paysika/pa_gradient_header_band.dart';
import '../../../../core/widgets/paysika/pa_pattern_background.dart';
import '../../../../l10n/gen/app_localizations.dart';
import 'campaigns_list_page.dart';
import 'news_list_page.dart';

/// Onglet « Annonces » de la barre de navigation (remplace l'ancien Carnet).
///
/// Regroupe, en deux vues segmentées, ce qui encombrait la Home :
///   • Actualités (articles vitrine)
///   • Campagnes micro-crédit en cours
///
/// Les corps de liste sont réutilisés tels quels ([NewsListBody] /
/// [CampaignsListBody]) : mêmes données (`homeFeedProvider`), même
/// pull-to-refresh, même lazy-load.
class AnnoncesPage extends ConsumerWidget {
  const AnnoncesPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l = AppL10n.of(context);
    return Scaffold(
      backgroundColor: PaColors.canvas,
      body: PaPatternBackground(
        child: SafeArea(
          bottom: false,
          child: DefaultTabController(
            length: 2,
            child: Column(
              children: [
                PaGradientHeaderBand(title: l.nav_annonces),
                const Padding(
                  padding: EdgeInsets.fromLTRB(16, 4, 16, 12),
                  child: _SegmentedTabs(),
                ),
                const Expanded(
                  child: TabBarView(
                    children: [
                      NewsListBody(),
                      CampaignsListBody(),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

/// Sélecteur segmenté façon « pilule » : onglet actif = pastille teal.
class _SegmentedTabs extends StatelessWidget {
  const _SegmentedTabs();

  @override
  Widget build(BuildContext context) {
    final l = AppL10n.of(context);
    return Container(
      height: 44,
      padding: const EdgeInsets.all(4),
      decoration: BoxDecoration(
        color: PaColors.tealSurface.withValues(alpha: 0.6),
        borderRadius: BorderRadius.circular(999),
      ),
      child: TabBar(
        indicator: BoxDecoration(
          color: PaColors.teal,
          borderRadius: BorderRadius.circular(999),
          boxShadow: [
            BoxShadow(
              color: PaColors.teal.withValues(alpha: 0.28),
              blurRadius: 10,
              offset: const Offset(0, 3),
            ),
          ],
        ),
        indicatorSize: TabBarIndicatorSize.tab,
        dividerColor: Colors.transparent,
        splashBorderRadius: BorderRadius.circular(999),
        labelColor: Colors.white,
        unselectedLabelColor: PaColors.inkSecondary,
        labelStyle: const TextStyle(fontSize: 13.5, fontWeight: FontWeight.w700),
        unselectedLabelStyle:
            const TextStyle(fontSize: 13.5, fontWeight: FontWeight.w600),
        tabs: [
          Tab(text: l.annonces_tab_news),
          Tab(text: l.annonces_tab_campaigns),
        ],
      ),
    );
  }
}
