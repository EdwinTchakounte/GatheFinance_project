import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../app/theme/paysika/pa_colors.dart';
import '../../../../core/widgets/paysika/pa_card.dart';
import '../../../../l10n/gen/app_localizations.dart';
import '../state/collecte_eom_notifier.dart';

/// Carte « Fin de mois collecte » — le membre choisit ce qui arrive à son solde
/// de collecte à la clôture mensuelle : retrait à l'agence, versement Mobile
/// Money (il renseigne sa destination) ou bascule vers l'épargne.
class CollecteEomCard extends ConsumerStatefulWidget {
  const CollecteEomCard({super.key});

  @override
  ConsumerState<CollecteEomCard> createState() => _CollecteEomCardState();
}

class _CollecteEomCardState extends ConsumerState<CollecteEomCard> {
  static const _networks = ['MTN', 'ORANGE'];

  final _phoneCtrl = TextEditingController();
  String _network = 'MTN';
  bool _hydrated = false;

  // Sélection locale (non encore persistée) — sert uniquement à déplier le
  // formulaire Mobile Money avant l'enregistrement. `null` = on suit le serveur.
  String? _pending;

  // Auto-persistance de la destination Mobile Money : dès que le numéro et le
  // réseau sont valides on enregistre (parité avec le tap immédiat cash/épargne)
  // sans attendre le bouton « Enregistrer ». Debounce pour ne pas marteler l'API.
  Timer? _debounce;
  bool _saving = false;

  @override
  void dispose() {
    _debounce?.cancel();
    _phoneCtrl.dispose();
    super.dispose();
  }

  /// Nombre de chiffres saisis dans le numéro (ignore espaces/séparateurs).
  int _phoneDigits() => _phoneCtrl.text.replaceAll(RegExp(r'\D'), '').length;

  /// Enregistre automatiquement la destination Mobile Money quand elle est
  /// valide (numéro d'au moins 9 chiffres + réseau). Debounce à la frappe ;
  /// [immediate] pour un changement discret (sélection du réseau).
  void _autoSaveMomo({bool immediate = false}) {
    _debounce?.cancel();
    if (_phoneDigits() < 9) return;
    if (immediate) {
      _saveMomo(silent: true);
      return;
    }
    _debounce = Timer(const Duration(milliseconds: 600), () {
      if (mounted) _saveMomo(silent: true);
    });
  }

  void _hydrate(CollecteEomPref pref) {
    if (_hydrated) return;
    _hydrated = true;
    _phoneCtrl.text = pref.payoutPhone;
    if (pref.payoutNetwork.isNotEmpty &&
        _networks.contains(pref.payoutNetwork)) {
      _network = pref.payoutNetwork;
    }
  }

  Future<void> _saveMomo({bool silent = false}) async {
    if (_saving) return;
    final l = AppL10n.of(context);
    final phone = _phoneCtrl.text.trim();
    if (phone.isEmpty) {
      if (!silent) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(l.collecte_eom_momo_phone_required)),
        );
      }
      return;
    }
    _saving = true;
    try {
      await ref
          .read(collecteEomProvider.notifier)
          .setPreference('mobile_money', phone: phone, network: _network);
      if (mounted) setState(() => _pending = null);
    } catch (_) {
      if (mounted && !silent) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(l.collecte_eom_momo_phone_required)),
        );
      }
    } finally {
      _saving = false;
    }
  }

  @override
  Widget build(BuildContext context) {
    final l = AppL10n.of(context);
    final async = ref.watch(collecteEomProvider);
    final pref = async.valueOrNull ??
        const CollecteEomPref(preference: 'cash');
    _hydrate(pref);
    final current = _pending ?? pref.preference;

    return PaCard(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.event_available_rounded,
                  size: 18, color: PaColors.teal,),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  l.collecte_eom_title,
                  style: const TextStyle(
                    color: PaColors.inkPrimary,
                    fontSize: 14,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 4),
          Text(
            l.collecte_eom_sub,
            style: const TextStyle(color: PaColors.inkMuted, fontSize: 12),
          ),
          const SizedBox(height: 14),
          _Option(
            selected: current == 'cash',
            icon: Icons.storefront_outlined,
            title: l.collecte_eom_cash,
            desc: l.collecte_eom_cash_desc,
            onTap: () {
              setState(() => _pending = null);
              ref.read(collecteEomProvider.notifier).setPreference('cash');
            },
          ),
          const SizedBox(height: 10),
          _Option(
            selected: current == 'mobile_money',
            icon: Icons.smartphone_rounded,
            title: l.collecte_eom_momo,
            desc: l.collecte_eom_momo_desc,
            onTap: () {
              // Déplie le formulaire. Parité « tap » : si une destination
              // valide est DÉJÀ renseignée (numéro pré-rempli inchangé), on
              // persiste le choix immédiatement — sinon la saisie déclenchera
              // l'auto-enregistrement, ou le bouton « Enregistrer ».
              setState(() => _pending = 'mobile_money');
              _autoSaveMomo(immediate: true);
            },
          ),
          if (current == 'mobile_money') _buildMomoForm(l),
          const SizedBox(height: 10),
          _Option(
            selected: current == 'epargne',
            icon: Icons.savings_outlined,
            title: l.collecte_eom_savings,
            desc: l.collecte_eom_savings_desc,
            onTap: () {
              setState(() => _pending = null);
              ref.read(collecteEomProvider.notifier).setPreference('epargne');
            },
          ),
        ],
      ),
    );
  }

  Widget _buildMomoForm(AppL10n l) {
    return Container(
      margin: const EdgeInsets.only(top: 10),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: PaColors.paper,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: PaColors.line),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            l.collecte_eom_momo_phone,
            style: const TextStyle(
              color: PaColors.inkMuted,
              fontSize: 12,
              fontWeight: FontWeight.w600,
            ),
          ),
          const SizedBox(height: 6),
          TextField(
            controller: _phoneCtrl,
            keyboardType: TextInputType.phone,
            onChanged: (_) => _autoSaveMomo(),
            decoration: InputDecoration(
              isDense: true,
              hintText: l.collecte_eom_momo_phone_hint,
              border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(10),
              ),
              contentPadding:
                  const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
            ),
          ),
          const SizedBox(height: 10),
          Text(
            l.collecte_eom_momo_network,
            style: const TextStyle(
              color: PaColors.inkMuted,
              fontSize: 12,
              fontWeight: FontWeight.w600,
            ),
          ),
          const SizedBox(height: 6),
          Wrap(
            spacing: 8,
            children: [
              for (final net in _networks)
                ChoiceChip(
                  label: Text(net),
                  selected: _network == net,
                  onSelected: (_) {
                    setState(() => _network = net);
                    // Réseau = choix discret : on enregistre tout de suite si le
                    // numéro est déjà valide.
                    _autoSaveMomo(immediate: true);
                  },
                ),
            ],
          ),
          const SizedBox(height: 12),
          SizedBox(
            width: double.infinity,
            child: FilledButton(
              onPressed: _saveMomo,
              child: Text(l.collecte_eom_momo_save),
            ),
          ),
        ],
      ),
    );
  }
}

class _Option extends StatelessWidget {
  const _Option({
    required this.selected,
    required this.icon,
    required this.title,
    required this.desc,
    required this.onTap,
  });

  final bool selected;
  final IconData icon;
  final String title;
  final String desc;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(14),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 160),
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: selected ? PaColors.tealSurface : PaColors.paper,
          borderRadius: BorderRadius.circular(14),
          border: Border.all(
            color: selected ? PaColors.teal : PaColors.line,
            width: selected ? 1.5 : 1,
          ),
        ),
        child: Row(
          children: [
            Icon(icon,
                size: 20, color: selected ? PaColors.teal : PaColors.inkMuted,),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    title,
                    style: TextStyle(
                      color: selected ? PaColors.tealDark : PaColors.inkPrimary,
                      fontSize: 13,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    desc,
                    style: const TextStyle(
                      color: PaColors.inkMuted,
                      fontSize: 12,
                      height: 1.3,
                    ),
                  ),
                ],
              ),
            ),
            if (selected)
              const Icon(Icons.check_circle_rounded,
                  size: 20, color: PaColors.teal,),
          ],
        ),
      ),
    );
  }
}
