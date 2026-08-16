import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../app/theme/paysika/pa_colors.dart';
import '../../core/error/error_message.dart';
import '../../core/formatters/xaf_formatter.dart';
import '../../core/widgets/paysika/pa_button.dart';
import '../../core/widgets/paysika/pa_card.dart';
import 'special_collections_notifier.dart';

/// Vue d'une collecte particulière (caisse scolaire / tontine alimentaire).
///
/// Selon l'état de la participation :
///   • absente/rejetée → formulaire de demande (objectif + montant cible) ;
///   • en attente       → bandeau « en attente de validation » ;
///   • validée          → solde + actions Verser (Mobile Money) et Transférer.
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
            // Pas de cycle ouvert → rien à faire pour l'instant.
            if (slot == null || !slot.hasOpenCycle) {
              return _NoCycleBanner(title: title);
            }
            final m = slot.membership;
            if (m != null && m.statut == 'valide') {
              return _ActiveView(type: type, collection: m);
            }
            if (m != null && m.statut == 'en_attente') {
              return _PendingBanner(title: title);
            }
            // Aucune participation ou rejetée → formulaire de demande.
            return _RequestForm(
              type: type,
              title: title,
              previousRejet: m?.motifRejet,
            );
          },
        ),
      ),
    );
  }
}

// ── Formulaire de demande ─────────────────────────────────────────────────────
class _RequestForm extends ConsumerStatefulWidget {
  const _RequestForm({
    required this.type,
    required this.title,
    this.previousRejet,
  });

  final String type;
  final String title;
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
    return SingleChildScrollView(
      padding: const EdgeInsets.fromLTRB(20, 12, 20, 24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (widget.previousRejet != null &&
              widget.previousRejet!.isNotEmpty) ...[
            PaCard(
              padding: const EdgeInsets.all(14),
              child: Row(
                children: [
                  const Icon(
                    Icons.info_outline_rounded,
                    color: PaColors.warning,
                    size: 20,
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      'Demande précédente refusée : ${widget.previousRejet}',
                      style: const TextStyle(
                        color: PaColors.inkSecondary,
                        fontSize: 12.5,
                        height: 1.3,
                      ),
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 16),
          ],
          Text(
            'Participer à « ${widget.title} »',
            style: const TextStyle(
              color: PaColors.inkPrimary,
              fontSize: 19,
              fontWeight: FontWeight.w800,
            ),
          ),
          const SizedBox(height: 6),
          const Text(
            'Avant de pouvoir verser, envoie une demande. La coopérative la '
            'valide, puis tu pourras alimenter ta collecte.',
            style: TextStyle(
              color: PaColors.inkSecondary,
              fontSize: 13,
              height: 1.35,
            ),
          ),
          const SizedBox(height: 18),
          const Text(
            'TON OBJECTIF',
            style: TextStyle(
              color: PaColors.inkSecondary,
              fontSize: 11,
              fontWeight: FontWeight.w700,
              letterSpacing: 1.1,
            ),
          ),
          const SizedBox(height: 8),
          TextField(
            controller: _objectifCtrl,
            maxLines: 4,
            minLines: 3,
            cursorColor: PaColors.teal,
            decoration: InputDecoration(
              hintText:
                  'Ex. réunir la scolarité de mes enfants pour la rentrée…',
              filled: true,
              fillColor: PaColors.cardBg,
              border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(12),
                borderSide: BorderSide.none,
              ),
            ),
          ),
          const SizedBox(height: 16),
          const Text(
            'MONTANT CIBLE (OPTIONNEL)',
            style: TextStyle(
              color: PaColors.inkSecondary,
              fontSize: 11,
              fontWeight: FontWeight.w700,
              letterSpacing: 1.1,
            ),
          ),
          const SizedBox(height: 8),
          TextField(
            controller: _cibleCtrl,
            keyboardType: TextInputType.number,
            cursorColor: PaColors.teal,
            decoration: InputDecoration(
              hintText: 'Ex. 150000',
              suffixText: 'XAF',
              filled: true,
              fillColor: PaColors.cardBg,
              border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(12),
                borderSide: BorderSide.none,
              ),
            ),
          ),
          const SizedBox(height: 22),
          PaButton(
            label: _busy ? 'Envoi…' : 'Envoyer ma demande',
            onPressed: _busy ? null : _submit,
          ),
        ],
      ),
    );
  }
}

// ── Bandeau « pas de cycle ouvert » ──────────────────────────────────────────
class _NoCycleBanner extends StatelessWidget {
  const _NoCycleBanner({required this.title});

  final String title;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(28),
        child: Column(
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
              'Aucun cycle en cours',
              textAlign: TextAlign.center,
              style: TextStyle(
                color: PaColors.inkPrimary,
                fontSize: 18,
                fontWeight: FontWeight.w800,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              'La coopérative n\'a pas encore ouvert de cycle pour « $title ». '
              'Reviens dès qu\'un nouveau cycle sera lancé pour t\'y inscrire.',
              textAlign: TextAlign.center,
              style: const TextStyle(
                color: PaColors.inkSecondary,
                fontSize: 13,
                height: 1.4,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

// ── Bandeau en attente ────────────────────────────────────────────────────────
class _PendingBanner extends StatelessWidget {
  const _PendingBanner({required this.title});

  final String title;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(28),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 64,
              height: 64,
              decoration: const BoxDecoration(
                color: PaColors.warningSurface,
                shape: BoxShape.circle,
              ),
              child: const Icon(
                Icons.hourglass_top_rounded,
                color: PaColors.warning,
                size: 32,
              ),
            ),
            const SizedBox(height: 16),
            const Text(
              'Demande en cours de validation',
              textAlign: TextAlign.center,
              style: TextStyle(
                color: PaColors.inkPrimary,
                fontSize: 18,
                fontWeight: FontWeight.w800,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              'Ta participation à « $title » a bien été envoyée. Tu pourras '
              'verser dès que la coopérative l’aura validée.',
              textAlign: TextAlign.center,
              style: const TextStyle(
                color: PaColors.inkSecondary,
                fontSize: 13,
                height: 1.4,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

// ── Vue active (validée) ──────────────────────────────────────────────────────
class _ActiveView extends ConsumerWidget {
  const _ActiveView({required this.type, required this.collection});

  final String type;
  final SpecialCollection collection;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return SingleChildScrollView(
      padding: const EdgeInsets.fromLTRB(20, 12, 20, 24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          PaCard(
            padding: const EdgeInsets.all(20),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Solde de ta collecte',
                  style: TextStyle(color: PaColors.inkSecondary, fontSize: 13),
                ),
                const SizedBox(height: 6),
                Text(
                  '${XAFFormatter.formatNumber(collection.solde)} XAF',
                  style: const TextStyle(
                    color: PaColors.inkPrimary,
                    fontSize: 30,
                    fontWeight: FontWeight.w800,
                  ),
                ),
                if (collection.montantCible != null) ...[
                  const SizedBox(height: 6),
                  Text(
                    'Objectif : ${XAFFormatter.formatNumber(collection.montantCible!)} XAF',
                    style: const TextStyle(
                      color: PaColors.inkSecondary,
                      fontSize: 12.5,
                    ),
                  ),
                ],
              ],
            ),
          ),
          const SizedBox(height: 16),
          if (collection.objectif.isNotEmpty) ...[
            PaCard(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    'TON OBJECTIF',
                    style: TextStyle(
                      color: PaColors.inkSecondary,
                      fontSize: 11,
                      fontWeight: FontWeight.w700,
                      letterSpacing: 1.1,
                    ),
                  ),
                  const SizedBox(height: 6),
                  Text(
                    collection.objectif,
                    style: const TextStyle(
                      color: PaColors.inkPrimary,
                      fontSize: 13.5,
                      height: 1.35,
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 16),
          ],
          PaButton(
            label: 'Verser (Mobile Money)',
            icon: Icons.smartphone_rounded,
            onPressed: () => _VersementSheet.show(context, ref, type),
          ),
          const SizedBox(height: 10),
          PaButton(
            label: 'Transférer depuis mon épargne',
            variant: PaButtonVariant.outline,
            icon: Icons.swap_horiz_rounded,
            onPressed: () => _TransferSheet.show(context, ref, type),
          ),
        ],
      ),
    );
  }
}

// ── Feuille de versement Mobile Money ─────────────────────────────────────────
class _VersementSheet extends ConsumerStatefulWidget {
  const _VersementSheet({required this.type});

  final String type;

  static Future<void> show(BuildContext context, WidgetRef ref, String type) =>
      showModalBottomSheet<void>(
        context: context,
        isScrollControlled: true,
        backgroundColor: PaColors.canvas,
        shape: const RoundedRectangleBorder(
          borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
        ),
        builder: (_) => _VersementSheet(type: type),
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
    if (montant == null || montant < 1000) {
      _toast('Montant minimum : 1 000 XAF.');
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
              _field(
                _montantCtrl,
                'Montant',
                suffix: 'XAF',
                keyboard: TextInputType.number,
              ),
              const SizedBox(height: 12),
              _field(
                _phoneCtrl,
                'Numéro Mobile Money',
                prefix: '+237 ',
                keyboard: TextInputType.phone,
              ),
              const SizedBox(height: 12),
              Row(
                children: [
                  for (final n in const ['MTN', 'ORANGE']) ...[
                    ChoiceChip(
                      label: Text(n),
                      selected: _network == n,
                      onSelected: (_) => setState(() => _network = n),
                      selectedColor: PaColors.tealSurface,
                    ),
                    const SizedBox(width: 8),
                  ],
                ],
              ),
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

  Widget _field(
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
}

// ── Feuille de transfert depuis l'épargne classique ───────────────────────────
class _TransferSheet extends ConsumerStatefulWidget {
  const _TransferSheet({required this.type});

  final String type;

  static Future<void> show(BuildContext context, WidgetRef ref, String type) =>
      showModalBottomSheet<void>(
        context: context,
        isScrollControlled: true,
        backgroundColor: PaColors.canvas,
        shape: const RoundedRectangleBorder(
          borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
        ),
        builder: (_) => _TransferSheet(type: type),
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
    if (montant == null || montant <= 0) {
      _toast('Saisis un montant valide.');
      return;
    }
    setState(() => _busy = true);
    try {
      await ref.read(specialCollectionsProvider.notifier).transferFromClassic(
            type: widget.type,
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
              TextField(
                controller: _montantCtrl,
                keyboardType: TextInputType.number,
                cursorColor: PaColors.teal,
                decoration: InputDecoration(
                  hintText: 'Montant',
                  suffixText: 'XAF',
                  filled: true,
                  fillColor: PaColors.cardBg,
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(12),
                    borderSide: BorderSide.none,
                  ),
                ),
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
