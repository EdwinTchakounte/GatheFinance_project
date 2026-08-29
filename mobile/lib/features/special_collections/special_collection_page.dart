import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../app/theme/paysika/pa_colors.dart';
import '../../core/error/error_message.dart';
import '../../core/formatters/xaf_formatter.dart';
import '../../core/widgets/paysika/pa_button.dart';
import '../../core/widgets/paysika/pa_card.dart';
import 'special_collections_notifier.dart';

/// Vue d'un type de collecte particulière (caisse scolaire / tontine).
///
/// Plusieurs collectes peuvent être ouvertes pour le même type. Pour verser, le
/// membre doit d'abord avoir acheté le carnet du type (payant, prérequis).
class SpecialCollectionPage extends ConsumerWidget {
  const SpecialCollectionPage({super.key, required this.type});

  final String type;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final title = kSpecialCollectionTypes[type] ?? 'Collecte';
    final async = ref.watch(specialCollectionsProvider);

    return Scaffold(
      backgroundColor: PaColors.canvas,
      appBar: AppBar(
        backgroundColor: PaColors.canvas,
        elevation: 0,
        title: Text(title, style: const TextStyle(color: PaColors.inkPrimary)),
        iconTheme: const IconThemeData(color: PaColors.inkPrimary),
      ),
      body: SafeArea(
        child: async.when(
          loading: () => const Center(
            child: CircularProgressIndicator(color: PaColors.teal),
          ),
          error: (e, _) => Center(
            child: Padding(
              padding: const EdgeInsets.all(24),
              child: Text(
                friendlyError(e),
                textAlign: TextAlign.center,
                style: const TextStyle(color: PaColors.inkSecondary),
              ),
            ),
          ),
          data: (_) {
            final notifier = ref.read(specialCollectionsProvider.notifier);
            final slot = notifier.slotFor(type);
            if (slot == null) return _NoCycleBanner(title: title);

            return SingleChildScrollView(
              padding: const EdgeInsets.fromLTRB(20, 12, 20, 24),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  if (!slot.hasCarnet) ...[
                    _CarnetBanner(type: type, title: title),
                    const SizedBox(height: 16),
                  ],
                  if (slot.cycles.isEmpty)
                    _NoCycleBanner(title: title, embedded: true)
                  else
                    for (final open in slot.cycles) ...[
                      _CycleCard(
                        type: type,
                        hasCarnet: slot.hasCarnet,
                        open: open,
                      ),
                      const SizedBox(height: 16),
                    ],
                ],
              ),
            );
          },
        ),
      ),
    );
  }
}

// ── Bannière achat carnet ─────────────────────────────────────────────────────
class _CarnetBanner extends ConsumerWidget {
  const _CarnetBanner({required this.type, required this.title});

  final String type;
  final String title;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return PaCard(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Row(
            children: [
              Icon(Icons.menu_book_rounded, color: PaColors.warning, size: 20),
              SizedBox(width: 10),
              Expanded(
                child: Text(
                  'Carnet requis',
                  style: TextStyle(
                    color: PaColors.inkPrimary,
                    fontSize: 15,
                    fontWeight: FontWeight.w800,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Text(
            'Pour verser dans « $title », tu dois d\'abord acheter le carnet de '
            'ce type. Il est distinct de ton carnet d\'épargne / collecte.',
            style: const TextStyle(
              color: PaColors.inkSecondary,
              fontSize: 12.5,
              height: 1.35,
            ),
          ),
          const SizedBox(height: 14),
          PaButton(
            label: 'Acheter le carnet',
            icon: Icons.smartphone_rounded,
            onPressed: () => _BuyCarnetSheet.show(context, ref, type),
          ),
        ],
      ),
    );
  }
}

// ── Carte d'une collecte ouverte ──────────────────────────────────────────────
class _CycleCard extends ConsumerWidget {
  const _CycleCard({
    required this.type,
    required this.hasCarnet,
    required this.open,
  });

  final String type;
  final bool hasCarnet;
  final SpecialCollectionOpen open;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final m = open.membership;
    return PaCard(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            open.cycle.nom,
            style: const TextStyle(
              color: PaColors.inkPrimary,
              fontSize: 16,
              fontWeight: FontWeight.w800,
            ),
          ),
          if (open.cycle.montantMinimal > 0) ...[
            const SizedBox(height: 4),
            Text(
              'Versement minimal : ${XAFFormatter.formatNumber(open.cycle.montantMinimal)} XAF',
              style:
                  const TextStyle(color: PaColors.inkSecondary, fontSize: 12),
            ),
          ],
          if (open.cycle.description.isNotEmpty) ...[
            const SizedBox(height: 6),
            Text(
              open.cycle.description,
              style: const TextStyle(
                color: PaColors.inkSecondary,
                fontSize: 12.5,
                height: 1.3,
              ),
            ),
          ],
          const SizedBox(height: 14),
          if (m != null && m.statut == 'valide')
            _ActiveView(
              type: type,
              hasCarnet: hasCarnet,
              cycleId: open.cycle.id,
              minAmount: open.cycle.montantMinimal,
              collection: m,
            )
          else if (m != null && m.statut == 'en_attente')
            const _InlineNote(
              icon: Icons.hourglass_top_rounded,
              color: PaColors.warning,
              text:
                  'Ta demande est en attente de validation. Tu pourras verser '
                  'dès qu\'elle sera validée.',
            )
          else
            _RequestForm(
              type: type,
              cycleId: open.cycle.id,
              previousRejet: m?.motifRejet,
            ),
        ],
      ),
    );
  }
}

class _InlineNote extends StatelessWidget {
  const _InlineNote({
    required this.icon,
    required this.color,
    required this.text,
  });

  final IconData icon;
  final Color color;
  final String text;

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(icon, color: color, size: 18),
        const SizedBox(width: 8),
        Expanded(
          child: Text(
            text,
            style: const TextStyle(
              color: PaColors.inkSecondary,
              fontSize: 12.5,
              height: 1.3,
            ),
          ),
        ),
      ],
    );
  }
}

// ── Formulaire de demande ─────────────────────────────────────────────────────
class _RequestForm extends ConsumerStatefulWidget {
  const _RequestForm({
    required this.type,
    required this.cycleId,
    this.previousRejet,
  });

  final String type;
  final int cycleId;
  final String? previousRejet;

  @override
  ConsumerState<_RequestForm> createState() => _RequestFormState();
}

class _RequestFormState extends ConsumerState<_RequestForm> {
  final _objectifCtrl = TextEditingController();
  final _cibleCtrl = TextEditingController();
  bool _busy = false;

  @override
  void dispose() {
    _objectifCtrl.dispose();
    _cibleCtrl.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    final objectif = _objectifCtrl.text.trim();
    if (objectif.isEmpty) {
      _toast('Décris ton objectif pour cette collecte.');
      return;
    }
    setState(() => _busy = true);
    try {
      final cible = num.tryParse(_cibleCtrl.text.replaceAll(RegExp(r'\D'), ''));
      await ref.read(specialCollectionsProvider.notifier).requestParticipation(
            type: widget.type,
            cycleId: widget.cycleId,
            objectif: objectif,
            montantCible: cible,
          );
      if (mounted) _toast('Demande envoyée. En attente de validation.');
    } catch (e) {
      if (mounted) _toast(friendlyError(e));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  void _toast(String m) =>
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(m)));

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        if (widget.previousRejet != null &&
            widget.previousRejet!.isNotEmpty) ...[
          _InlineNote(
            icon: Icons.info_outline_rounded,
            color: PaColors.warning,
            text: 'Demande précédente refusée : ${widget.previousRejet}',
          ),
          const SizedBox(height: 12),
        ],
        const Text(
          'Envoie une demande pour participer. La coopérative la valide, puis tu '
          'pourras alimenter ta collecte.',
          style: TextStyle(
            color: PaColors.inkSecondary,
            fontSize: 12.5,
            height: 1.35,
          ),
        ),
        const SizedBox(height: 12),
        TextField(
          controller: _objectifCtrl,
          maxLines: 3,
          minLines: 2,
          cursorColor: PaColors.teal,
          decoration: InputDecoration(
            hintText: 'Ton objectif (ex. scolarité de la rentrée…)',
            filled: true,
            fillColor: PaColors.cardBg,
            border: OutlineInputBorder(
              borderRadius: BorderRadius.circular(12),
              borderSide: BorderSide.none,
            ),
          ),
        ),
        const SizedBox(height: 12),
        TextField(
          controller: _cibleCtrl,
          keyboardType: TextInputType.number,
          cursorColor: PaColors.teal,
          decoration: InputDecoration(
            hintText: 'Montant cible (optionnel)',
            suffixText: 'XAF',
            filled: true,
            fillColor: PaColors.cardBg,
            border: OutlineInputBorder(
              borderRadius: BorderRadius.circular(12),
              borderSide: BorderSide.none,
            ),
          ),
        ),
        const SizedBox(height: 16),
        PaButton(
          label: _busy ? 'Envoi…' : 'Envoyer ma demande',
          onPressed: _busy ? null : _submit,
        ),
      ],
    );
  }
}

// ── Bandeau « aucune collecte » ───────────────────────────────────────────────
class _NoCycleBanner extends StatelessWidget {
  const _NoCycleBanner({required this.title, this.embedded = false});

  final String title;
  final bool embedded;

  @override
  Widget build(BuildContext context) {
    final content = Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          width: 64,
          height: 64,
          decoration: const BoxDecoration(
            color: PaColors.cardBg,
            shape: BoxShape.circle,
          ),
          child: const Icon(
            Icons.event_busy_rounded,
            color: PaColors.inkMuted,
            size: 32,
          ),
        ),
        const SizedBox(height: 16),
        const Text(
          'Aucune collecte en cours',
          textAlign: TextAlign.center,
          style: TextStyle(
            color: PaColors.inkPrimary,
            fontSize: 18,
            fontWeight: FontWeight.w800,
          ),
        ),
        const SizedBox(height: 8),
        Text(
          'La coopérative n\'a pas encore ouvert de collecte pour « $title ». '
          'Reviens dès qu\'une nouvelle sera lancée pour t\'y inscrire.',
          textAlign: TextAlign.center,
          style: const TextStyle(
            color: PaColors.inkSecondary,
            fontSize: 13,
            height: 1.4,
          ),
        ),
      ],
    );
    if (embedded) {
      return PaCard(padding: const EdgeInsets.all(24), child: content);
    }
    return Center(
      child: Padding(padding: const EdgeInsets.all(28), child: content),
    );
  }
}

// ── Vue active (validée) ──────────────────────────────────────────────────────
class _ActiveView extends ConsumerWidget {
  const _ActiveView({
    required this.type,
    required this.hasCarnet,
    required this.cycleId,
    required this.minAmount,
    required this.collection,
  });

  final String type;
  final bool hasCarnet;
  final int cycleId;
  final num minAmount;
  final SpecialCollection collection;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Container(
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(
            color: PaColors.cardBg,
            borderRadius: BorderRadius.circular(12),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                'Mon solde',
                style: TextStyle(color: PaColors.inkSecondary, fontSize: 12.5),
              ),
              const SizedBox(height: 4),
              Text(
                '${XAFFormatter.formatNumber(collection.solde)} XAF',
                style: const TextStyle(
                  color: PaColors.inkPrimary,
                  fontSize: 26,
                  fontWeight: FontWeight.w800,
                ),
              ),
              if (collection.montantCible != null) ...[
                const SizedBox(height: 4),
                Text(
                  'Objectif : ${XAFFormatter.formatNumber(collection.montantCible!)} XAF',
                  style: const TextStyle(
                    color: PaColors.inkSecondary,
                    fontSize: 12,
                  ),
                ),
              ],
            ],
          ),
        ),
        const SizedBox(height: 12),
        if (!hasCarnet) ...[
          const _InlineNote(
            icon: Icons.menu_book_rounded,
            color: PaColors.warning,
            text: 'Achète d\'abord le carnet (en haut) pour pouvoir verser.',
          ),
          const SizedBox(height: 12),
        ],
        PaButton(
          label: 'Verser (Mobile Money)',
          icon: Icons.smartphone_rounded,
          onPressed: hasCarnet
              ? () =>
                  _VersementSheet.show(context, ref, type, cycleId, minAmount)
              : null,
        ),
        const SizedBox(height: 10),
        PaButton(
          label: 'Transférer depuis mon épargne',
          variant: PaButtonVariant.outline,
          icon: Icons.swap_horiz_rounded,
          onPressed: hasCarnet
              ? () =>
                  _TransferSheet.show(context, ref, type, cycleId, minAmount)
              : null,
        ),
      ],
    );
  }
}

int _floor(num minAmount) {
  final m = minAmount.toInt();
  return m > 1000 ? m : 1000;
}

// ── Feuille d'achat de carnet ─────────────────────────────────────────────────
class _BuyCarnetSheet extends ConsumerStatefulWidget {
  const _BuyCarnetSheet({required this.type});

  final String type;

  static Future<void> show(BuildContext context, WidgetRef ref, String type) =>
      showModalBottomSheet<void>(
        context: context,
        isScrollControlled: true,
        backgroundColor: PaColors.canvas,
        shape: const RoundedRectangleBorder(
          borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
        ),
        builder: (_) => _BuyCarnetSheet(type: type),
      );

  @override
  ConsumerState<_BuyCarnetSheet> createState() => _BuyCarnetSheetState();
}

class _BuyCarnetSheetState extends ConsumerState<_BuyCarnetSheet> {
  final _phoneCtrl = TextEditingController();
  String _network = 'MTN';
  bool _busy = false;

  @override
  void dispose() {
    _phoneCtrl.dispose();
    super.dispose();
  }

  Future<void> _buy() async {
    final phone = _phoneCtrl.text.replaceAll(RegExp(r'\D'), '');
    if (phone.length < 8) {
      _toast('Numéro Mobile Money invalide.');
      return;
    }
    setState(() => _busy = true);
    try {
      await ref.read(specialCollectionsProvider.notifier).buyCarnet(
            type: widget.type,
            phone: phone,
            network: _network,
          );
      if (mounted) Navigator.of(context).pop();
    } catch (e) {
      if (mounted) _toast(friendlyError(e));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  void _toast(String m) =>
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(m)));

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.only(bottom: MediaQuery.viewInsetsOf(context).bottom),
      child: SafeArea(
        top: false,
        child: SingleChildScrollView(
          padding: const EdgeInsets.fromLTRB(20, 16, 20, 24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                'Acheter le carnet',
                style: TextStyle(
                  color: PaColors.inkPrimary,
                  fontSize: 18,
                  fontWeight: FontWeight.w800,
                ),
              ),
              const SizedBox(height: 6),
              const Text(
                'Le tarif du carnet est fixé par la coopérative. Confirme le '
                'paiement sur ton téléphone.',
                style: TextStyle(
                  color: PaColors.inkSecondary,
                  fontSize: 12.5,
                  height: 1.3,
                ),
              ),
              const SizedBox(height: 16),
              _sheetField(
                _phoneCtrl,
                'Numéro Mobile Money',
                prefix: '+237 ',
                keyboard: TextInputType.phone,
              ),
              const SizedBox(height: 12),
              _networkChips(_network, (n) => setState(() => _network = n)),
              const SizedBox(height: 20),
              PaButton(
                label: _busy ? 'Achat…' : 'Payer le carnet',
                onPressed: _busy ? null : _buy,
              ),
            ],
          ),
        ),
      ),
    );
  }
}

// ── Feuille de versement Mobile Money ─────────────────────────────────────────
class _VersementSheet extends ConsumerStatefulWidget {
  const _VersementSheet({
    required this.type,
    required this.cycleId,
    required this.minAmount,
  });

  final String type;
  final int cycleId;
  final num minAmount;

  static Future<void> show(
    BuildContext context,
    WidgetRef ref,
    String type,
    int cycleId,
    num minAmount,
  ) =>
      showModalBottomSheet<void>(
        context: context,
        isScrollControlled: true,
        backgroundColor: PaColors.canvas,
        shape: const RoundedRectangleBorder(
          borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
        ),
        builder: (_) =>
            _VersementSheet(type: type, cycleId: cycleId, minAmount: minAmount),
      );

  @override
  ConsumerState<_VersementSheet> createState() => _VersementSheetState();
}

class _VersementSheetState extends ConsumerState<_VersementSheet> {
  final _montantCtrl = TextEditingController();
  final _phoneCtrl = TextEditingController();
  String _network = 'MTN';
  bool _busy = false;

  @override
  void dispose() {
    _montantCtrl.dispose();
    _phoneCtrl.dispose();
    super.dispose();
  }

  Future<void> _pay() async {
    final montant =
        num.tryParse(_montantCtrl.text.replaceAll(RegExp(r'\D'), ''));
    final phone = _phoneCtrl.text.replaceAll(RegExp(r'\D'), '');
    final floor = _floor(widget.minAmount);
    if (montant == null || montant < floor) {
      _toast('Montant minimum : ${XAFFormatter.formatNumber(floor)} XAF.');
      return;
    }
    if (phone.length < 8) {
      _toast('Numéro Mobile Money invalide.');
      return;
    }
    setState(() => _busy = true);
    try {
      await ref.read(specialCollectionsProvider.notifier).initVersement(
            type: widget.type,
            cycleId: widget.cycleId,
            montant: montant,
            phone: phone,
            network: _network,
          );
      if (mounted) Navigator.of(context).pop();
    } catch (e) {
      if (mounted) _toast(friendlyError(e));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  void _toast(String m) =>
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(m)));

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.only(bottom: MediaQuery.viewInsetsOf(context).bottom),
      child: SafeArea(
        top: false,
        child: SingleChildScrollView(
          padding: const EdgeInsets.fromLTRB(20, 16, 20, 24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                'Verser sur ma collecte',
                style: TextStyle(
                  color: PaColors.inkPrimary,
                  fontSize: 18,
                  fontWeight: FontWeight.w800,
                ),
              ),
              const SizedBox(height: 16),
              _sheetField(
                _montantCtrl,
                'Montant',
                suffix: 'XAF',
                keyboard: TextInputType.number,
              ),
              const SizedBox(height: 12),
              _sheetField(
                _phoneCtrl,
                'Numéro Mobile Money',
                prefix: '+237 ',
                keyboard: TextInputType.phone,
              ),
              const SizedBox(height: 12),
              _networkChips(_network, (n) => setState(() => _network = n)),
              const SizedBox(height: 20),
              PaButton(
                label: _busy ? 'Paiement…' : 'Payer',
                onPressed: _busy ? null : _pay,
              ),
            ],
          ),
        ),
      ),
    );
  }
}

// ── Feuille de transfert depuis l'épargne classique ───────────────────────────
class _TransferSheet extends ConsumerStatefulWidget {
  const _TransferSheet({
    required this.type,
    required this.cycleId,
    required this.minAmount,
  });

  final String type;
  final int cycleId;
  final num minAmount;

  static Future<void> show(
    BuildContext context,
    WidgetRef ref,
    String type,
    int cycleId,
    num minAmount,
  ) =>
      showModalBottomSheet<void>(
        context: context,
        isScrollControlled: true,
        backgroundColor: PaColors.canvas,
        shape: const RoundedRectangleBorder(
          borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
        ),
        builder: (_) =>
            _TransferSheet(type: type, cycleId: cycleId, minAmount: minAmount),
      );

  @override
  ConsumerState<_TransferSheet> createState() => _TransferSheetState();
}

class _TransferSheetState extends ConsumerState<_TransferSheet> {
  final _montantCtrl = TextEditingController();
  bool _busy = false;

  @override
  void dispose() {
    _montantCtrl.dispose();
    super.dispose();
  }

  Future<void> _transfer() async {
    final montant =
        num.tryParse(_montantCtrl.text.replaceAll(RegExp(r'\D'), ''));
    final floor = _floor(widget.minAmount);
    if (montant == null || montant < floor) {
      _toast('Montant minimum : ${XAFFormatter.formatNumber(floor)} XAF.');
      return;
    }
    setState(() => _busy = true);
    try {
      await ref.read(specialCollectionsProvider.notifier).transferFromClassic(
            type: widget.type,
            cycleId: widget.cycleId,
            montant: montant,
          );
      if (mounted) {
        Navigator.of(context).pop();
        _toast('Transfert effectué.');
      }
    } catch (e) {
      if (mounted) _toast(friendlyError(e));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  void _toast(String m) =>
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(m)));

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.only(bottom: MediaQuery.viewInsetsOf(context).bottom),
      child: SafeArea(
        top: false,
        child: SingleChildScrollView(
          padding: const EdgeInsets.fromLTRB(20, 16, 20, 24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                'Transférer depuis mon épargne',
                style: TextStyle(
                  color: PaColors.inkPrimary,
                  fontSize: 18,
                  fontWeight: FontWeight.w800,
                ),
              ),
              const SizedBox(height: 6),
              const Text(
                'Le montant est prélevé sur ton épargne classique disponible et '
                'crédité immédiatement sur ta collecte (sans frais).',
                style: TextStyle(
                  color: PaColors.inkSecondary,
                  fontSize: 12.5,
                  height: 1.3,
                ),
              ),
              const SizedBox(height: 16),
              _sheetField(
                _montantCtrl,
                'Montant',
                suffix: 'XAF',
                keyboard: TextInputType.number,
              ),
              const SizedBox(height: 20),
              PaButton(
                label: _busy ? 'Transfert…' : 'Transférer',
                onPressed: _busy ? null : _transfer,
              ),
            ],
          ),
        ),
      ),
    );
  }
}

// ── Helpers partagés des feuilles ─────────────────────────────────────────────
Widget _sheetField(
  TextEditingController c,
  String hint, {
  String? suffix,
  String? prefix,
  TextInputType? keyboard,
}) {
  return TextField(
    controller: c,
    keyboardType: keyboard,
    cursorColor: PaColors.teal,
    decoration: InputDecoration(
      hintText: hint,
      prefixText: prefix,
      suffixText: suffix,
      filled: true,
      fillColor: PaColors.cardBg,
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(12),
        borderSide: BorderSide.none,
      ),
    ),
  );
}

Widget _networkChips(String selected, ValueChanged<String> onSelected) {
  return Row(
    children: [
      for (final n in const ['MTN', 'ORANGE']) ...[
        ChoiceChip(
          label: Text(n),
          selected: selected == n,
          onSelected: (_) => onSelected(n),
          selectedColor: PaColors.tealSurface,
        ),
        const SizedBox(width: 8),
      ],
    ],
  );
}
