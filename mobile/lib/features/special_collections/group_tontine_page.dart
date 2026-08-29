import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../app/theme/paysika/pa_colors.dart';
import '../../core/error/error_message.dart';
import '../../core/formatters/xaf_formatter.dart';
import '../../core/widgets/paysika/pa_button.dart';
import '../../core/widgets/paysika/pa_card.dart';
import 'group_tontines_notifier.dart';

/// Détail d'une réunion (tontine de groupe) : cagnotte, membres/rôles,
/// cotisation, et — pour le président/trésorier — versement bénéficiaire,
/// prêt, remboursement, changement de rôle, clôture.
class GroupTontinePage extends ConsumerStatefulWidget {
  const GroupTontinePage({super.key, required this.id});

  final int id;

  @override
  ConsumerState<GroupTontinePage> createState() => _GroupTontinePageState();
}

class _GroupTontinePageState extends ConsumerState<GroupTontinePage> {
  GroupDetail? _detail;
  Object? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final d =
          await ref.read(groupTontinesProvider.notifier).fetchDetail(widget.id);
      if (mounted) setState(() => _detail = d);
    } catch (e) {
      if (mounted) setState(() => _error = e);
    }
  }

  void _apply(GroupDetail d) => setState(() => _detail = d);

  void _toast(String m) =>
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(m)));

  @override
  Widget build(BuildContext context) {
    final d = _detail;
    return Scaffold(
      backgroundColor: PaColors.canvas,
      appBar: AppBar(
        backgroundColor: PaColors.canvas,
        elevation: 0,
        title: Text(
          d?.summary.nom ?? 'Réunion',
          style: const TextStyle(color: PaColors.inkPrimary),
        ),
        iconTheme: const IconThemeData(color: PaColors.inkPrimary),
      ),
      body: SafeArea(
        child: _error != null
            ? Center(
                child: Padding(
                  padding: const EdgeInsets.all(24),
                  child: Text(
                    friendlyError(_error!),
                    textAlign: TextAlign.center,
                    style: const TextStyle(color: PaColors.inkSecondary),
                  ),
                ),
              )
            : d == null
                ? const Center(
                    child: CircularProgressIndicator(color: PaColors.teal),
                  )
                : _body(d),
      ),
    );
  }

  Widget _body(GroupDetail d) {
    final s = d.summary;
    // Gating par PERMISSIONS effectives (rôle intégré + rôles personnalisés),
    // pas seulement par le rôle nominal.
    final canPayout = d.can('can_manage_funds');
    final canLoan = d.can('can_grant_loan');
    final canClose = d.can('can_close');
    final canRoster = d.can('can_manage_roster');
    return SingleChildScrollView(
      padding: const EdgeInsets.fromLTRB(20, 12, 20, 24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          // Cagnotte
          PaCard(
            padding: const EdgeInsets.all(18),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Cagnotte de la réunion',
                  style: TextStyle(color: PaColors.inkSecondary, fontSize: 13),
                ),
                const SizedBox(height: 4),
                Text(
                  '${XAFFormatter.formatNumber(s.solde)} XAF',
                  style: const TextStyle(
                    color: PaColors.inkPrimary,
                    fontSize: 28,
                    fontWeight: FontWeight.w800,
                  ),
                ),
                const SizedBox(height: 6),
                _roleChip(s.myRole),
                if (!s.isOpen) ...[
                  const SizedBox(height: 8),
                  const Text(
                    'Réunion clôturée',
                    style: TextStyle(color: PaColors.danger, fontSize: 12.5),
                  ),
                ],
              ],
            ),
          ),
          const SizedBox(height: 14),

          if (s.isOpen) ...[
            PaButton(
              label: 'Cotiser',
              icon: Icons.add_rounded,
              onPressed: () => _cotiserSheet(d),
            ),
            if (canPayout) ...[
              const SizedBox(height: 10),
              PaButton(
                label: 'Verser à un bénéficiaire',
                variant: PaButtonVariant.outline,
                icon: Icons.volunteer_activism_rounded,
                onPressed: () => _memberAmountSheet(
                  d,
                  title: 'Verser à un bénéficiaire',
                  action: (mid, montant) => ref
                      .read(groupTontinesProvider.notifier)
                      .payout(widget.id, mid, montant),
                ),
              ),
            ],
            if (canLoan) ...[
              const SizedBox(height: 10),
              PaButton(
                label: 'Accorder un prêt',
                variant: PaButtonVariant.outline,
                icon: Icons.account_balance_wallet_rounded,
                onPressed: () => _loanSheet(d),
              ),
            ],
          ],

          const SizedBox(height: 18),
          // Membres
          _sectionTitle('Membres (${d.members.length})'),
          const SizedBox(height: 8),
          ...d.members.map((m) => _memberRow(d, m, canRoster && s.isOpen)),

          // Rôles personnalisés (actions rattachées) — si habilité « gérer le roster ».
          if (canRoster) ...[
            const SizedBox(height: 18),
            _sectionTitle('Rôles personnalisés'),
            const SizedBox(height: 8),
            ...d.customRoles.map((r) => _customRoleRow(d, r)),
            const SizedBox(height: 8),
            PaButton(
              label: 'Créer un rôle',
              variant: PaButtonVariant.outline,
              icon: Icons.add_moderator_outlined,
              onPressed: () => _createRoleSheet(d),
            ),
          ],

          // Prêts
          if (d.loans.isNotEmpty) ...[
            const SizedBox(height: 18),
            _sectionTitle('Prêts'),
            const SizedBox(height: 8),
            ...d.loans.map(
              (l) => _loanRow(
                l,
                canManage: canPayout || canLoan,
                isOpen: s.isOpen,
                isMine: d.myMemberId != null && l.memberId == d.myMemberId,
              ),
            ),
          ],

          // Mouvements
          const SizedBox(height: 18),
          _sectionTitle('Mouvements (${d.transactions.length})'),
          const SizedBox(height: 8),
          if (d.transactions.isEmpty)
            const Text(
              'Aucun mouvement.',
              style: TextStyle(color: PaColors.inkSecondary, fontSize: 13),
            )
          else
            ...d.transactions.take(30).map(_txRow),

          if (canClose && s.isOpen) ...[
            const SizedBox(height: 20),
            PaButton(
              label: 'Clôturer la réunion',
              variant: PaButtonVariant.outline,
              icon: Icons.lock_outline_rounded,
              onPressed: () async {
                try {
                  _apply(
                    await ref
                        .read(groupTontinesProvider.notifier)
                        .close(widget.id),
                  );
                  _toast('Réunion clôturée.');
                } catch (e) {
                  _toast(friendlyError(e));
                }
              },
            ),
          ],
        ],
      ),
    );
  }

  Widget _sectionTitle(String t) => Text(
        t,
        style: const TextStyle(
          color: PaColors.inkSecondary,
          fontSize: 11,
          fontWeight: FontWeight.w700,
          letterSpacing: 1.1,
        ),
      );

  Widget _roleChip(String? role) {
    final label = switch (role) {
      'president' => 'Président',
      'tresorier' => 'Trésorier',
      _ => 'Membre',
    };
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: PaColors.tealSurface,
        borderRadius: BorderRadius.circular(20),
      ),
      child: Text(
        'Mon rôle : $label',
        style: const TextStyle(
          color: PaColors.teal,
          fontSize: 11.5,
          fontWeight: FontWeight.w700,
        ),
      ),
    );
  }

  Widget _memberRow(GroupDetail d, GroupMember m, bool canSetRole) {
    return Container(
      margin: const EdgeInsets.only(bottom: 6),
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(
        color: PaColors.cardBg,
        borderRadius: BorderRadius.circular(10),
      ),
      child: Row(
        children: [
          Expanded(
            child: Text(
              '${m.prenom} ${m.nom}',
              style: const TextStyle(
                color: PaColors.inkPrimary,
                fontSize: 13.5,
              ),
            ),
          ),
          if (canSetRole) ...[
            DropdownButton<String>(
              value: m.role,
              underline: const SizedBox.shrink(),
              isDense: true,
              items: const [
                DropdownMenuItem(value: 'president', child: Text('Président')),
                DropdownMenuItem(value: 'tresorier', child: Text('Trésorier')),
                DropdownMenuItem(value: 'membre', child: Text('Membre')),
              ],
              onChanged: (v) async {
                if (v == null) return;
                try {
                  _apply(
                    await ref
                        .read(groupTontinesProvider.notifier)
                        .setRole(widget.id, m.memberId, v),
                  );
                } catch (e) {
                  _toast(friendlyError(e));
                }
              },
            ),
            if (d.customRoles.isNotEmpty)
              DropdownButton<int?>(
                value: m.customRoleId,
                underline: const SizedBox.shrink(),
                isDense: true,
                hint: const Text('Rôle +', style: TextStyle(fontSize: 12)),
                items: [
                  const DropdownMenuItem<int?>(value: null, child: Text('—')),
                  ...d.customRoles.map(
                    (r) => DropdownMenuItem<int?>(value: r.id, child: Text(r.nom)),
                  ),
                ],
                onChanged: (v) async {
                  try {
                    _apply(
                      await ref
                          .read(groupTontinesProvider.notifier)
                          .assignRole(widget.id, m.memberId, v),
                    );
                  } catch (e) {
                    _toast(friendlyError(e));
                  }
                },
              ),
          ] else
            Text(
              m.customRoleNom.isNotEmpty
                  ? '${m.roleDisplay} · ${m.customRoleNom}'
                  : m.roleDisplay,
              style: const TextStyle(
                color: PaColors.inkSecondary,
                fontSize: 12,
              ),
            ),
        ],
      ),
    );
  }

  Widget _loanRow(
    GroupLoan l, {
    required bool canManage,
    required bool isOpen,
    required bool isMine,
  }) {
    final canRepay = (canManage || isMine) && isOpen && l.statut == 'en_cours';
    return Container(
      margin: const EdgeInsets.only(bottom: 6),
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(
        color: PaColors.cardBg,
        borderRadius: BorderRadius.circular(10),
      ),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '${l.prenom} ${l.nom}${isMine ? ' (moi)' : ''}',
                  style: const TextStyle(
                    color: PaColors.inkPrimary,
                    fontSize: 13,
                  ),
                ),
                Text(
                  'Reste ${XAFFormatter.formatNumber(l.soldeRestant)} / ${XAFFormatter.formatNumber(l.montant)} XAF',
                  style: const TextStyle(
                    color: PaColors.inkSecondary,
                    fontSize: 11.5,
                  ),
                ),
                if (l.avalisteDisplay.isNotEmpty)
                  Text(
                    'Avaliste : ${l.avalisteDisplay}',
                    style: const TextStyle(
                      color: PaColors.inkSecondary,
                      fontSize: 11,
                    ),
                  ),
              ],
            ),
          ),
          if (canRepay)
            TextButton(
              onPressed: () => _repaySheet(l, isMine: isMine),
              child: Text(isMine ? 'Rembourser mon prêt' : 'Rembourser'),
            ),
        ],
      ),
    );
  }

  Widget _txRow(GroupTx t) {
    final entree = t.typeOpDisplay.toLowerCase().contains('entrée') ||
        t.typeOpDisplay.toLowerCase().contains('cotisation') ||
        t.typeOpDisplay.toLowerCase().contains('remboursement');
    return Container(
      margin: const EdgeInsets.only(bottom: 5),
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 9),
      decoration: BoxDecoration(
        color: PaColors.cardBg,
        borderRadius: BorderRadius.circular(10),
      ),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  t.typeOpDisplay,
                  style: const TextStyle(
                    color: PaColors.inkPrimary,
                    fontSize: 12.5,
                  ),
                ),
                if (t.memberNom.isNotEmpty)
                  Text(
                    '${t.memberPrenom} ${t.memberNom}',
                    style: const TextStyle(
                      color: PaColors.inkSecondary,
                      fontSize: 11,
                    ),
                  ),
                if (t.actedByName.isNotEmpty)
                  Text(
                    'par ${t.actedByName}',
                    style: const TextStyle(
                      color: PaColors.inkMuted,
                      fontSize: 10,
                    ),
                  ),
              ],
            ),
          ),
          Text(
            '${entree ? '+' : '−'}${XAFFormatter.formatNumber(t.montant)}',
            style: TextStyle(
              color: entree ? PaColors.success : PaColors.danger,
              fontSize: 13,
              fontWeight: FontWeight.w700,
            ),
          ),
        ],
      ),
    );
  }

  // ── Sheets ──────────────────────────────────────────────────────────────────
  Future<void> _cotiserSheet(GroupDetail d) async {
    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      backgroundColor: PaColors.canvas,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      builder: (_) => _CotiserSheet(id: widget.id, onDone: _apply),
    );
  }

  Future<void> _repaySheet(GroupLoan l, {required bool isMine}) async {
    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      backgroundColor: PaColors.canvas,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      builder: (_) =>
          _RepaySheet(id: widget.id, loan: l, isMine: isMine, onDone: _apply),
    );
  }

  Future<void> _memberAmountSheet(
    GroupDetail d, {
    required String title,
    required Future<GroupDetail> Function(int memberId, num montant) action,
  }) async {
    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      backgroundColor: PaColors.canvas,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      builder: (_) => _MemberAmountSheet(
        title: title,
        members: d.members,
        onSubmit: (mid, montant) async => _apply(await action(mid, montant)),
      ),
    );
  }

  // ── Prêt avec avaliste (informatif) ─────────────────────────────────────────
  Future<void> _loanSheet(GroupDetail d) async {
    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      backgroundColor: PaColors.canvas,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      builder: (_) => _LoanSheet(id: widget.id, members: d.members, onDone: _apply),
    );
  }

  // ── Rôles personnalisés ────────────────────────────────────────────────────
  Widget _customRoleRow(GroupDetail d, GroupCustomRole r) {
    final actions = kGroupRoleActions.entries
        .where((e) => r.perms[e.key] == true)
        .map((e) => e.value)
        .toList();
    return Container(
      margin: const EdgeInsets.only(bottom: 6),
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(
        color: PaColors.cardBg,
        borderRadius: BorderRadius.circular(10),
      ),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  r.nom,
                  style: const TextStyle(
                    color: PaColors.inkPrimary,
                    fontSize: 13.5,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                Text(
                  actions.isEmpty ? 'Aucune action' : actions.join(' · '),
                  style: const TextStyle(
                    color: PaColors.inkSecondary,
                    fontSize: 11,
                  ),
                ),
              ],
            ),
          ),
          IconButton(
            icon: const Icon(Icons.delete_outline_rounded, size: 20),
            color: PaColors.danger,
            onPressed: () async {
              try {
                _apply(
                  await ref
                      .read(groupTontinesProvider.notifier)
                      .deleteRole(widget.id, r.id),
                );
              } catch (e) {
                _toast(friendlyError(e));
              }
            },
          ),
        ],
      ),
    );
  }

  Future<void> _createRoleSheet(GroupDetail d) async {
    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      backgroundColor: PaColors.canvas,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      builder: (_) => _CreateRoleSheet(id: widget.id, onDone: _apply),
    );
  }
}

// ── Feuille cotisation (MoMo ou depuis épargne) ───────────────────────────────
class _CotiserSheet extends ConsumerStatefulWidget {
  const _CotiserSheet({required this.id, required this.onDone});
  final int id;
  final void Function(GroupDetail) onDone;

  @override
  ConsumerState<_CotiserSheet> createState() => _CotiserSheetState();
}

class _CotiserSheetState extends ConsumerState<_CotiserSheet> {
  final _montant = TextEditingController();
  final _phone = TextEditingController();
  String _network = 'MTN';
  bool _fromSavings = false;
  bool _busy = false;

  @override
  void dispose() {
    _montant.dispose();
    _phone.dispose();
    super.dispose();
  }

  void _toast(String m) =>
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(m)));

  Future<void> _submit() async {
    final montant = num.tryParse(_montant.text.replaceAll(RegExp(r'\D'), ''));
    if (montant == null || montant <= 0) {
      _toast('Montant invalide.');
      return;
    }
    setState(() => _busy = true);
    try {
      final notifier = ref.read(groupTontinesProvider.notifier);
      if (_fromSavings) {
        final d = await notifier.cotiserFromSavings(widget.id, montant);
        if (mounted) {
          widget.onDone(d);
          Navigator.of(context).pop();
        }
      } else {
        final phone = _phone.text.replaceAll(RegExp(r'\D'), '');
        if (phone.length < 8) {
          _toast('Numéro Mobile Money invalide.');
          setState(() => _busy = false);
          return;
        }
        await notifier.cotiserMomo(
          id: widget.id,
          montant: montant,
          phone: phone,
          network: _network,
        );
        if (mounted) Navigator.of(context).pop();
      }
    } catch (e) {
      if (mounted) _toast(friendlyError(e));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

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
                'Cotiser',
                style: TextStyle(
                  color: PaColors.inkPrimary,
                  fontSize: 18,
                  fontWeight: FontWeight.w800,
                ),
              ),
              const SizedBox(height: 14),
              _field(
                _montant,
                'Montant',
                suffix: 'XAF',
                keyboard: TextInputType.number,
              ),
              const SizedBox(height: 12),
              Row(
                children: [
                  ChoiceChip(
                    label: const Text('Mobile Money'),
                    selected: !_fromSavings,
                    onSelected: (_) => setState(() => _fromSavings = false),
                    selectedColor: PaColors.tealSurface,
                  ),
                  const SizedBox(width: 8),
                  ChoiceChip(
                    label: const Text('Mon épargne'),
                    selected: _fromSavings,
                    onSelected: (_) => setState(() => _fromSavings = true),
                    selectedColor: PaColors.tealSurface,
                  ),
                ],
              ),
              if (!_fromSavings) ...[
                const SizedBox(height: 12),
                _field(
                  _phone,
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
              ],
              const SizedBox(height: 18),
              PaButton(
                label: _busy ? 'Envoi…' : 'Cotiser',
                onPressed: _busy ? null : _submit,
              ),
            ],
          ),
        ),
      ),
    );
  }
}

// ── Feuille membre + montant (versement / prêt) ───────────────────────────────
class _MemberAmountSheet extends StatefulWidget {
  const _MemberAmountSheet({
    required this.title,
    required this.members,
    required this.onSubmit,
  });
  final String title;
  final List<GroupMember> members;
  final Future<void> Function(int memberId, num montant) onSubmit;

  @override
  State<_MemberAmountSheet> createState() => _MemberAmountSheetState();
}

class _MemberAmountSheetState extends State<_MemberAmountSheet> {
  final _montant = TextEditingController();
  int? _memberId;
  bool _busy = false;

  @override
  void dispose() {
    _montant.dispose();
    super.dispose();
  }

  void _toast(String m) =>
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(m)));

  Future<void> _submit() async {
    final montant = num.tryParse(_montant.text.replaceAll(RegExp(r'\D'), ''));
    if (_memberId == null) {
      _toast('Choisis un membre.');
      return;
    }
    if (montant == null || montant <= 0) {
      _toast('Montant invalide.');
      return;
    }
    setState(() => _busy = true);
    try {
      await widget.onSubmit(_memberId!, montant);
      if (mounted) Navigator.of(context).pop();
    } catch (e) {
      if (mounted) _toast(friendlyError(e));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

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
              Text(
                widget.title,
                style: const TextStyle(
                  color: PaColors.inkPrimary,
                  fontSize: 18,
                  fontWeight: FontWeight.w800,
                ),
              ),
              const SizedBox(height: 14),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 12),
                decoration: BoxDecoration(
                  color: PaColors.cardBg,
                  borderRadius: BorderRadius.circular(12),
                ),
                child: DropdownButton<int>(
                  value: _memberId,
                  isExpanded: true,
                  underline: const SizedBox.shrink(),
                  hint: const Text('Choisir un membre'),
                  items: [
                    for (final m in widget.members)
                      DropdownMenuItem(
                        value: m.memberId,
                        child: Text('${m.prenom} ${m.nom}'),
                      ),
                  ],
                  onChanged: (v) => setState(() => _memberId = v),
                ),
              ),
              const SizedBox(height: 12),
              _field(
                _montant,
                'Montant',
                suffix: 'XAF',
                keyboard: TextInputType.number,
              ),
              const SizedBox(height: 18),
              PaButton(
                label: _busy ? '…' : 'Valider',
                onPressed: _busy ? null : _submit,
              ),
            ],
          ),
        ),
      ),
    );
  }
}

// ── Feuille de remboursement de prêt (transfert épargne OU MoMo) ──────────────
class _RepaySheet extends ConsumerStatefulWidget {
  const _RepaySheet({
    required this.id,
    required this.loan,
    required this.isMine,
    required this.onDone,
  });

  final int id;
  final GroupLoan loan;
  final bool isMine;
  final void Function(GroupDetail) onDone;

  @override
  ConsumerState<_RepaySheet> createState() => _RepaySheetState();
}

class _RepaySheetState extends ConsumerState<_RepaySheet> {
  final _montant = TextEditingController();
  final _phone = TextEditingController();
  String _network = 'MTN';
  bool _viaMomo = false;
  bool _busy = false;

  @override
  void initState() {
    super.initState();
    // Par défaut : MoMo pour l'emprunteur, transfert épargne sinon.
    _viaMomo = widget.isMine;
  }

  @override
  void dispose() {
    _montant.dispose();
    _phone.dispose();
    super.dispose();
  }

  void _toast(String m) =>
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(m)));

  Future<void> _submit() async {
    final montant = num.tryParse(_montant.text.replaceAll(RegExp(r'\D'), ''));
    if (montant == null || montant <= 0) {
      _toast('Montant invalide.');
      return;
    }
    setState(() => _busy = true);
    try {
      final notifier = ref.read(groupTontinesProvider.notifier);
      if (_viaMomo && widget.isMine) {
        final phone = _phone.text.replaceAll(RegExp(r'\D'), '');
        if (phone.length < 8) {
          _toast('Numéro Mobile Money invalide.');
          setState(() => _busy = false);
          return;
        }
        await notifier.cotiserMomo(
          id: widget.id,
          montant: montant,
          phone: phone,
          network: _network,
          loanId: widget.loan.id,
        );
        if (mounted) Navigator.of(context).pop();
      } else {
        final d = await notifier.repay(widget.id, widget.loan.id, montant);
        if (mounted) {
          widget.onDone(d);
          Navigator.of(context).pop();
        }
      }
    } catch (e) {
      if (mounted) _toast(friendlyError(e));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

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
                'Rembourser le prêt',
                style: TextStyle(
                  color: PaColors.inkPrimary,
                  fontSize: 18,
                  fontWeight: FontWeight.w800,
                ),
              ),
              const SizedBox(height: 4),
              Text(
                'Reste ${XAFFormatter.formatNumber(widget.loan.soldeRestant)} XAF',
                style: const TextStyle(
                  color: PaColors.inkSecondary,
                  fontSize: 12.5,
                ),
              ),
              const SizedBox(height: 14),
              _field(
                _montant,
                'Montant',
                suffix: 'XAF',
                keyboard: TextInputType.number,
              ),
              if (widget.isMine) ...[
                const SizedBox(height: 12),
                Row(
                  children: [
                    ChoiceChip(
                      label: const Text('Mobile Money'),
                      selected: _viaMomo,
                      onSelected: (_) => setState(() => _viaMomo = true),
                      selectedColor: PaColors.tealSurface,
                    ),
                    const SizedBox(width: 8),
                    ChoiceChip(
                      label: const Text('Mon épargne'),
                      selected: !_viaMomo,
                      onSelected: (_) => setState(() => _viaMomo = false),
                      selectedColor: PaColors.tealSurface,
                    ),
                  ],
                ),
              ],
              if (_viaMomo && widget.isMine) ...[
                const SizedBox(height: 12),
                _field(
                  _phone,
                  'Numéro Mobile Money',
                  prefix: '+237 ',
                  keyboard: TextInputType.phone,
                ),
                const SizedBox(height: 12),
                _networkChips(_network, (n) => setState(() => _network = n)),
              ],
              const SizedBox(height: 18),
              PaButton(
                label: _busy ? '…' : 'Rembourser',
                onPressed: _busy ? null : _submit,
              ),
            ],
          ),
        ),
      ),
    );
  }
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

// ── Feuille « Accorder un prêt » avec avaliste INFORMATIF ─────────────────────
class _LoanSheet extends ConsumerStatefulWidget {
  const _LoanSheet({required this.id, required this.members, required this.onDone});
  final int id;
  final List<GroupMember> members;
  final void Function(GroupDetail) onDone;

  @override
  ConsumerState<_LoanSheet> createState() => _LoanSheetState();
}

class _LoanSheetState extends ConsumerState<_LoanSheet> {
  final _montant = TextEditingController();
  final _avalisteNom = TextEditingController();
  int? _memberId;
  int? _avalisteId;
  bool _busy = false;

  @override
  void dispose() {
    _montant.dispose();
    _avalisteNom.dispose();
    super.dispose();
  }

  void _toast(String m) =>
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(m)));

  Future<void> _submit() async {
    final montant = num.tryParse(_montant.text.replaceAll(RegExp(r'\D'), ''));
    if (_memberId == null) {
      _toast('Choisis l\'emprunteur.');
      return;
    }
    if (montant == null || montant <= 0) {
      _toast('Montant invalide.');
      return;
    }
    setState(() => _busy = true);
    try {
      final d = await ref.read(groupTontinesProvider.notifier).loan(
            widget.id,
            _memberId!,
            montant,
            avalisteId: _avalisteId,
            avalisteNom: _avalisteNom.text,
          );
      widget.onDone(d);
      if (mounted) Navigator.of(context).pop();
    } catch (e) {
      if (mounted) _toast(friendlyError(e));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

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
                'Accorder un prêt',
                style: TextStyle(
                  color: PaColors.inkPrimary,
                  fontSize: 18,
                  fontWeight: FontWeight.w800,
                ),
              ),
              const SizedBox(height: 14),
              _memberDropdown(
                value: _memberId,
                hint: 'Emprunteur',
                onChanged: (v) => setState(() => _memberId = v),
              ),
              const SizedBox(height: 12),
              _field(
                _montant,
                'Montant',
                suffix: 'XAF',
                keyboard: TextInputType.number,
              ),
              const SizedBox(height: 16),
              const Text(
                'Avaliste (facultatif — informatif)',
                style: TextStyle(
                  color: PaColors.inkSecondary,
                  fontSize: 12.5,
                  fontWeight: FontWeight.w600,
                ),
              ),
              const SizedBox(height: 6),
              _memberDropdown(
                value: _avalisteId,
                hint: 'Un membre de la réunion',
                nullable: true,
                onChanged: (v) => setState(() => _avalisteId = v),
              ),
              const SizedBox(height: 8),
              _field(_avalisteNom, 'ou un nom libre (hors réunion)'),
              const SizedBox(height: 18),
              PaButton(
                label: _busy ? '…' : 'Accorder le prêt',
                onPressed: _busy ? null : _submit,
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _memberDropdown({
    required int? value,
    required String hint,
    required ValueChanged<int?> onChanged,
    bool nullable = false,
  }) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12),
      decoration: BoxDecoration(
        color: PaColors.cardBg,
        borderRadius: BorderRadius.circular(12),
      ),
      child: DropdownButton<int?>(
        value: value,
        isExpanded: true,
        underline: const SizedBox.shrink(),
        hint: Text(hint),
        items: [
          if (nullable) const DropdownMenuItem<int?>(value: null, child: Text('—')),
          for (final m in widget.members)
            DropdownMenuItem<int?>(
              value: m.memberId,
              child: Text('${m.prenom} ${m.nom}'),
            ),
        ],
        onChanged: onChanged,
      ),
    );
  }
}

// ── Feuille « Créer un rôle personnalisé » (nom + actions cochées) ────────────
class _CreateRoleSheet extends ConsumerStatefulWidget {
  const _CreateRoleSheet({required this.id, required this.onDone});
  final int id;
  final void Function(GroupDetail) onDone;

  @override
  ConsumerState<_CreateRoleSheet> createState() => _CreateRoleSheetState();
}

class _CreateRoleSheetState extends ConsumerState<_CreateRoleSheet> {
  final _nom = TextEditingController();
  final Map<String, bool> _perms = {
    for (final k in kGroupRoleActions.keys) k: false,
  };
  bool _busy = false;

  @override
  void dispose() {
    _nom.dispose();
    super.dispose();
  }

  void _toast(String m) =>
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(m)));

  Future<void> _submit() async {
    if (_nom.text.trim().isEmpty) {
      _toast('Le nom du rôle est obligatoire.');
      return;
    }
    setState(() => _busy = true);
    try {
      final d = await ref
          .read(groupTontinesProvider.notifier)
          .createRole(widget.id, _nom.text.trim(), _perms);
      widget.onDone(d);
      if (mounted) Navigator.of(context).pop();
    } catch (e) {
      if (mounted) _toast(friendlyError(e));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

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
                'Créer un rôle',
                style: TextStyle(
                  color: PaColors.inkPrimary,
                  fontSize: 18,
                  fontWeight: FontWeight.w800,
                ),
              ),
              const SizedBox(height: 14),
              _field(_nom, 'Nom du rôle (ex. Secrétaire)'),
              const SizedBox(height: 14),
              const Text(
                'Actions permises',
                style: TextStyle(
                  color: PaColors.inkSecondary,
                  fontSize: 12.5,
                  fontWeight: FontWeight.w600,
                ),
              ),
              ...kGroupRoleActions.entries.map(
                (e) => CheckboxListTile(
                  contentPadding: EdgeInsets.zero,
                  dense: true,
                  controlAffinity: ListTileControlAffinity.leading,
                  value: _perms[e.key],
                  title: Text(e.value, style: const TextStyle(fontSize: 13.5)),
                  onChanged: (v) => setState(() => _perms[e.key] = v ?? false),
                ),
              ),
              const SizedBox(height: 12),
              PaButton(
                label: _busy ? '…' : 'Créer le rôle',
                onPressed: _busy ? null : _submit,
              ),
            ],
          ),
        ),
      ),
    );
  }
}
