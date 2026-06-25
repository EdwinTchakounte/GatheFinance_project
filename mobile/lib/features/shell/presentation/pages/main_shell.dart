import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:go_router/go_router.dart';

import '../../../../app/theme/paysika/pa_colors.dart';
import '../../../../l10n/gen/app_localizations.dart';

/// Shell racine . bottom nav style **Paysika**.
///
/// 4 destinations (Accueil / Crédit / Carnet / Profil). Active = icône
/// teal filled + label navy bold. Inactive = icône outline gris + label gris.
/// Pas de fond coloré sur l'item actif (à la différence du Material 3 default).
class MainShell extends StatelessWidget {
  const MainShell({super.key, required this.navigationShell});

  final StatefulNavigationShell navigationShell;

  void _goBranch(int index) {
    HapticFeedback.selectionClick();
    navigationShell.goBranch(
      index,
      initialLocation: index == navigationShell.currentIndex,
    );
  }

  @override
  Widget build(BuildContext context) {
    final l = AppL10n.of(context);
    final currentIndex = navigationShell.currentIndex;

    return Scaffold(
      backgroundColor: PaColors.appBg,
      body: navigationShell,
      bottomNavigationBar: Container(
        decoration: const BoxDecoration(
          color: PaColors.paper,
          border: Border(top: BorderSide(color: PaColors.line, width: 1)),
        ),
        child: SafeArea(
          top: false,
          child: SizedBox(
            height: 70,
            child: Row(
              children: [
                _PaNavItem(
                  icon: Icons.home_outlined,
                  selectedIcon: Icons.home_rounded,
                  label: l.nav_home,
                  selected: currentIndex == 0,
                  onTap: () => _goBranch(0),
                ),
                _PaNavItem(
                  icon: Icons.account_balance_outlined,
                  selectedIcon: Icons.account_balance_rounded,
                  label: l.nav_credit,
                  selected: currentIndex == 1,
                  onTap: () => _goBranch(1),
                ),
                _PaNavItem(
                  icon: Icons.menu_book_outlined,
                  selectedIcon: Icons.menu_book_rounded,
                  label: l.nav_booklet,
                  selected: currentIndex == 2,
                  onTap: () => _goBranch(2),
                ),
                _PaNavItem(
                  icon: Icons.person_outline_rounded,
                  selectedIcon: Icons.person_rounded,
                  label: l.nav_profile,
                  selected: currentIndex == 3,
                  onTap: () => _goBranch(3),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}


class _PaNavItem extends StatelessWidget {
  const _PaNavItem({
    required this.icon,
    required this.selectedIcon,
    required this.label,
    required this.selected,
    required this.onTap,
  });

  final IconData icon;
  final IconData selectedIcon;
  final String label;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final color = selected ? PaColors.teal : PaColors.inkMuted;

    return Expanded(
      child: InkWell(
        onTap: onTap,
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(selected ? selectedIcon : icon, color: color, size: 24),
            const SizedBox(height: 5),
            Text(
              label,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: TextStyle(
                color: selected ? PaColors.inkPrimary : PaColors.inkMuted,
                fontSize: 11.5,
                fontWeight: selected ? FontWeight.w700 : FontWeight.w500,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
