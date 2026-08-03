import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../app/theme/paysika/pa_colors.dart';
import '../../../../core/di/providers.dart';
import '../../../../core/formatters/xaf_formatter.dart';
import '../../../../core/widgets/paysika/pa_card.dart';
import '../../../../core/widgets/paysika/pa_pattern_background.dart';
import '../../../../core/widgets/skeleton.dart';
import '../../domain/entities/savings_account.dart';
import '../../domain/entities/withdrawal_request.dart';
import '../state/classic_savings_notifier.dart';
import '../state/savings_notifier.dart';

/// « État de mon compte » — page synthèse ouverte depuis l'icône détail de
/// l'accueil. Présente au membre, en un coup d'œil :
///   • la ventilation de son épargne classique (total, placement, libre, gelé
///     en garantie, disponible au retrait) ;
///   • le solde de sa collecte ;
///   • ses demandes de retrait en cours avec leur statut ;
///   • une explication du cycle d'un retrait (demande → validation → paiement)
///     et du gel de garantie.
class AccountStatePage extends ConsumerWidget {
  const AccountStatePage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final classic = ref.watch(classicSavingsProvider);
    final collecte = ref.watch(savingsProvider);
    final withdrawals = ref.watch(myWithdrawalsProvider);

    return Scaffold(
      backgroundColor: PaColors.canvas,
      appBar: AppBar(
        backgroundColor: PaColors.canvas,
        surfaceTintColor: PaColors.canvas,
        elevation: 0,
        scrolledUnderElevation: 0,
        centerTitle: true,
        title: const Text(
          'État de mon compte',
          style: TextStyle(
            color: PaColors.inkPrimary,
            fontSize: 16,
            fontWeight: FontWeight.w700,
          ),
        ),
        iconTheme: const IconThemeData(color: PaColors.inkPrimary),
      ),
      body: PaPatternBackground(
        child: RefreshIndicator.adaptive(
          color: PaColors.teal,
          onRefresh: () async {
            ref.invalidate(classicSavingsProvider);
            ref.invalidate(savingsProvider);
            ref.invalidate(myWithdrawalsProvider);
            await Future.wait([
              ref.read(classicSavingsProvider.future),
              ref.read(savingsProvider.future),
            ]);
          },
          child: ListView(
            padding: const EdgeInsets.fromLTRB(16, 8, 16, 40),
            children: [
              // ── Hero : disponible au retrait ──────────────────────────
              classic.when(
                data: (d) => _AvailableHero(account: d),
                loading: () => const PaCard(
                  padding: EdgeInsets.all(20),
                  child: SkeletonList(lines: 2),
                ),
                error: (_, __) => const SizedBox.shrink(),
              ),
              const SizedBox(height: 18),

              // ── Ventilation épargne classique ─────────────────────────
              const _SectionTitle('Épargne classique'),
              const SizedBox(height: 10),
              classic.when(
                data: (d) => _BreakdownCard(account: d),
                loading: () => const PaCard(
                  padding: EdgeInsets.all(16),
                  child: SkeletonList(lines: 4),
                ),
                error: (_, __) => const _ErrorCard(),
              ),
              const SizedBox(height: 20),

              // ── Collecte journalière ──────────────────────────────────
              const _SectionTitle('Collecte journalière'),
              const SizedBox(height: 10),
              collecte.when(
                data: (d) => _KvCard(
                  rows: [
                    ('Solde disponible', XAFFormatter.format(d.solde), false),
                  ],
                ),
                loading: () => const PaCard(
                  padding: EdgeInsets.all(16),
                  child: SkeletonList(lines: 1),
                ),
                error: (_, __) => const _ErrorCard(),
              ),
              const SizedBox(height: 20),

              // ── Retraits en cours ─────────────────────────────────────
              withdrawals.maybeWhen(
                data: (list) {
                  final active = list
                      .where(
                        (w) =>
                            w.statut == WithdrawalStatus.enAttente ||
                            w.statut == WithdrawalStatus.approuvee ||
                            w.statut == WithdrawalStatus.enPayout ||
                            w.statut == WithdrawalStatus.payoutFailed,
                      )
                      .toList();
                  if (active.isEmpty) return const SizedBox.shrink();
                  return Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const _SectionTitle('Retraits en cours'),
                      const SizedBox(height: 10),
                      PaCard(
                        padding: EdgeInsets.zero,
                        child: Column(
                          children: [
                            for (var i = 0; i < active.length; i++) ...[
                              if (i > 0) const SizedBox(height: 6),
                              _WithdrawalRow(w: active[i]),
                            ],
                          ],
                        ),
                      ),
                      const SizedBox(height: 20),
                    ],
                  );
                },
                orElse: () => const SizedBox.shrink(),
              ),

              // ── Explication du cycle de retrait ───────────────────────
              const _SectionTitle('Comment fonctionne un retrait'),
              const SizedBox(height: 10),
              const _CycleCard(),
            ],
          ),
        ),
      ),
    );
  }
}

class _AvailableHero extends StatelessWidget {
  const _AvailableHero({required this.account});
  final SavingsAccount account;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        gradient: PaGradients.heroAurore,
        borderRadius: BorderRadius.circular(20),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'Disponible au retrait',
            style: TextStyle(
              color: Colors.white70,
              fontSize: 13,
              fontWeight: FontWeight.w600,
            ),
          ),
          const SizedBox(height: 6),
          Text(
            '${XAFFormatter.formatNumber(account.soldeRetirable)} XAF',
            style: const TextStyle(
              color: Colors.white,
              fontSize: 30,
              fontWeight: FontWeight.w800,
            ),
          ),
          if ((account.montantGeleCredit ?? 0) > 0) ...[
            const SizedBox(height: 8),
            Row(
              children: [
                const Icon(
                  Icons.lock_outline_rounded,
                  size: 14,
                  color: Colors.white70,
                ),
                const SizedBox(width: 5),
                Text(
                  '${XAFFormatter.formatNumber(account.montantGeleCredit!)} XAF gelés en garantie',
                  style: const TextStyle(color: Colors.white70, fontSize: 12),
                ),
              ],
            ),
          ],
        ],
      ),
    );
  }
}

class _BreakdownCard extends StatelessWidget {
  const _BreakdownCard({required this.account});
  final SavingsAccount account;

  @override
  Widget build(BuildContext context) {
    // Le gel scindé par motif (apport mobilisable vs caution avaliste). Sur un
    // snapshot ancien ces champs sont null → on retombe sur l'agrégat unique.
    final apport = account.montantGeleApport ?? 0;
    final avaliste = account.montantGeleAvaliste ?? 0;
    final hasSplit = account.montantGeleApport != null ||
        account.montantGeleAvaliste != null;
    final rows = <(String, String, bool)>[
      ('Solde total', XAFFormatter.format(account.solde), false),
      if ((account.soldePlacementActif ?? 0) > 0)
        (
          'En placement (bloqué jusqu\'à l\'échéance)',
          XAFFormatter.format(account.soldePlacementActif!),
          false
        ),
      // NB : on n'affiche plus la ligne « Libre » (= solde − placement) : elle
      // ignorait le gel et pouvait dépasser le solde une fois le gelé ajouté.
      // La seule part réellement mobilisable est « Disponible au retrait ».
      if (hasSplit) ...[
        if (apport > 0)
          (
            'Gelé — apport de mes crédits (mobilisable)',
            XAFFormatter.format(apport),
            false
          ),
        if (avaliste > 0)
          (
            'Gelé — caution avaliste (libéré à la clôture)',
            XAFFormatter.format(avaliste),
            false
          ),
      ] else if ((account.montantGeleCredit ?? 0) > 0)
        (
          'Gelé en garantie',
          XAFFormatter.format(account.montantGeleCredit!),
          false
        ),
      (
        'Disponible au retrait',
        XAFFormatter.format(account.soldeRetirable),
        true
      ),
    ];
    return _KvCard(rows: rows);
  }
}

/// Carte clé/valeur générique. Le dernier booléen met la ligne en avant
/// (valeur teal + gras) — utilisé pour « disponible au retrait ».
class _KvCard extends StatelessWidget {
  const _KvCard({required this.rows});
  final List<(String, String, bool)> rows;

  @override
  Widget build(BuildContext context) {
    return PaCard(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
      child: Column(
        children: [
          for (final (label, value, highlight) in rows)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 9),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(
                    label,
                    style: TextStyle(
                      color: highlight
                          ? PaColors.inkPrimary
                          : PaColors.inkSecondary,
                      fontSize: 13.5,
                      fontWeight: highlight ? FontWeight.w700 : FontWeight.w500,
                    ),
                  ),
                  Text(
                    value,
                    style: TextStyle(
                      color: highlight ? PaColors.teal : PaColors.inkPrimary,
                      fontSize: 14,
                      fontWeight: highlight ? FontWeight.w800 : FontWeight.w700,
                    ),
                  ),
                ],
              ),
            ),
        ],
      ),
    );
  }
}

class _WithdrawalRow extends StatelessWidget {
  const _WithdrawalRow({required this.w});
  final WithdrawalRequest w;

  ({Color fg, Color bg}) get _tone => switch (w.statut) {
        WithdrawalStatus.completee => (
            fg: PaColors.teal,
            bg: PaColors.tealSurface
          ),
        WithdrawalStatus.approuvee || WithdrawalStatus.enPayout => (
            fg: PaColors.blue,
            bg: PaColors.blue.withValues(alpha: 0.10)
          ),
        WithdrawalStatus.rejetee || WithdrawalStatus.payoutFailed => (
            fg: PaColors.danger,
            bg: PaColors.danger.withValues(alpha: 0.10)
          ),
        WithdrawalStatus.enAttente => (
            fg: PaColors.warning,
            bg: PaColors.warning.withValues(alpha: 0.12)
          ),
      };

  /// Libellé COMPACT pour le tag (le `statutDisplay` backend est trop long
  /// — ex. « Approuvée — remise espèces en attente » — et débordait le chip).
  String get _shortStatut => switch (w.statut) {
        WithdrawalStatus.enAttente => 'En attente',
        WithdrawalStatus.approuvee =>
          w.modePaiement == WithdrawalChannel.presentiel
              ? 'Remise en attente'
              : 'Approuvé',
        WithdrawalStatus.enPayout => 'Envoi en cours',
        WithdrawalStatus.completee => 'Remis',
        WithdrawalStatus.payoutFailed => 'Envoi échoué',
        WithdrawalStatus.rejetee => 'Rejeté',
      };

  @override
  Widget build(BuildContext context) {
    final tone = _tone;
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 12),
      child: Row(
        // Alignement haut : si le tag passe sur 2 lignes (écran étroit), le
        // montant reste aligné en tête et rien ne déborde.
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '${XAFFormatter.formatNumber(w.montant)} XAF',
                  style: const TextStyle(
                    color: PaColors.inkPrimary,
                    fontSize: 14.5,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  w.modePaiementDisplay,
                  style:
                      const TextStyle(color: PaColors.inkMuted, fontSize: 12),
                ),
              ],
            ),
          ),
          const SizedBox(width: 10),
          // Tag contraint (max ~42 % de la largeur) : libellé compact, jamais
          // tronqué (retour à la ligne au besoin), aligné à droite.
          ConstrainedBox(
            constraints: BoxConstraints(
              maxWidth: MediaQuery.sizeOf(context).width * 0.42,
            ),
            child: Container(
              padding:
                  const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
              decoration: BoxDecoration(
                color: tone.bg,
                borderRadius: BorderRadius.circular(14),
              ),
              child: Text(
                _shortStatut,
                textAlign: TextAlign.center,
                softWrap: true,
                style: TextStyle(
                  color: tone.fg,
                  fontSize: 11.5,
                  fontWeight: FontWeight.w700,
                  height: 1.2,
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _CycleCard extends StatelessWidget {
  const _CycleCard();

  @override
  Widget build(BuildContext context) {
    return const PaCard(
      padding: EdgeInsets.all(16),
      child: Column(
        children: [
          _CycleStep(
            n: '1',
            title: 'Tu envoies ta demande',
            body: 'Elle passe « en attente ». Ton solde n’est pas encore '
                'débité — le montant est simplement réservé.',
          ),
          SizedBox(height: 14),
          _CycleStep(
            n: '2',
            title: 'La coopérative valide',
            body: 'La demande devient « approuvée ». Le montant reste réservé '
                '(indisponible pour un autre retrait), toujours sans débit.',
          ),
          SizedBox(height: 14),
          _CycleStep(
            n: '3',
            title: 'Le paiement / la remise',
            body: 'C’est seulement à ce moment que ton solde est réellement '
                'débité. Un paiement échoué ne débite rien.',
            last: true,
          ),
          SizedBox(height: 14),
          _GelNote(),
        ],
      ),
    );
  }
}

class _CycleStep extends StatelessWidget {
  const _CycleStep({
    required this.n,
    required this.title,
    required this.body,
    this.last = false,
  });

  final String n;
  final String title;
  final String body;
  final bool last;

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Container(
          width: 26,
          height: 26,
          decoration: const BoxDecoration(
            color: PaColors.tealSurface,
            shape: BoxShape.circle,
          ),
          alignment: Alignment.center,
          child: Text(
            n,
            style: const TextStyle(
              color: PaColors.teal,
              fontSize: 13,
              fontWeight: FontWeight.w800,
            ),
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                title,
                style: const TextStyle(
                  color: PaColors.inkPrimary,
                  fontSize: 13.5,
                  fontWeight: FontWeight.w700,
                ),
              ),
              const SizedBox(height: 2),
              Text(
                body,
                style: const TextStyle(
                  color: PaColors.inkSecondary,
                  fontSize: 12.5,
                  height: 1.35,
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }
}

class _GelNote extends StatelessWidget {
  const _GelNote();

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: PaColors.cardBg,
        borderRadius: BorderRadius.circular(12),
      ),
      child: const Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(Icons.lock_outline_rounded, size: 16, color: PaColors.inkMuted),
          SizedBox(width: 10),
          Expanded(
            child: Text(
              'Gel de garantie : quand un crédit s’appuie sur ton épargne, la '
              'part correspondante est gelée et exclue du disponible au retrait '
              'tant que le crédit la mobilise.',
              style: TextStyle(
                color: PaColors.inkSecondary,
                fontSize: 12,
                height: 1.35,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _SectionTitle extends StatelessWidget {
  const _SectionTitle(this.text);
  final String text;

  @override
  Widget build(BuildContext context) {
    return Text(
      text,
      style: const TextStyle(
        color: PaColors.inkPrimary,
        fontSize: 14.5,
        fontWeight: FontWeight.w700,
      ),
    );
  }
}

class _ErrorCard extends StatelessWidget {
  const _ErrorCard();

  @override
  Widget build(BuildContext context) {
    return const PaCard(
      padding: EdgeInsets.all(16),
      child: Text(
        'Indisponible pour le moment.',
        style: TextStyle(color: PaColors.inkMuted, fontSize: 13),
      ),
    );
  }
}
