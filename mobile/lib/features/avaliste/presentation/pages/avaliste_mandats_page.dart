import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../app/theme/paysika/pa_colors.dart';
import '../../../../app/theme/paysika/pa_typography.dart';
import '../../../../core/widgets/live_poller.dart';
import '../../../../core/widgets/paysika/pa_error_state.dart';
import '../../../../core/widgets/paysika/pa_pattern_background.dart';
import '../../../../core/widgets/skeleton.dart';
import '../../domain/entities/avaliste_mandat.dart';
import '../state/avaliste_notifier.dart';
import '../widgets/accept_cni_sheet.dart';
import '../widgets/mandat_card.dart';
import '../widgets/refuse_motif_sheet.dart';

/// Page **Mes mandats d'avaliste** . l'utilisateur consulte les demandes
/// de crédit où il est désigné comme garant, et accepte / refuse.
class AvalisteMandatsPage extends ConsumerStatefulWidget {
  const AvalisteMandatsPage({super.key});

  @override
  ConsumerState<AvalisteMandatsPage> createState() =>
      _AvalisteMandatsPageState();
}

class _AvalisteMandatsPageState extends ConsumerState<AvalisteMandatsPage> {
  final _busyIds = <int>{};

  Future<void> _accept(AvalisteMandat m) async {
    // L5 identité . L'acceptation exige le numéro de CNI de l'avaliste + un
    // justificatif (photo/scan). Le sheet bloque la validation tant que les
    // deux ne sont pas fournis, puis renvoie les valeurs captées.
    final result = await showAcceptCniSheet(context);
    if (result == null || !mounted) return; // annulé
    setState(() => _busyIds.add(m.id));
    try {
      await ref.read(avalisteProvider.notifier).respond(
            mandatId: m.id,
            accept: true,
            cniAvaliste: result.cniNumero,
            cniFichierPath: result.filePath,
            cniFichierName: result.fileName,
          );
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Mandat de ${m.demandeur.fullName} accepté.'),
          backgroundColor: PaColors.teal,
        ),
      );
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Impossible d\'accepter : $e')),
      );
    } finally {
      if (mounted) setState(() => _busyIds.remove(m.id));
    }
  }

  Future<void> _refuse(AvalisteMandat m) async {
    final motif = await showRefuseMotifSheet(context);
    if (motif == null || !mounted) return; // annulé
    setState(() => _busyIds.add(m.id));
    try {
      await ref.read(avalisteProvider.notifier).respond(
            mandatId: m.id,
            accept: false,
            motif: motif,
          );
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Mandat refusé.')),
      );
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Impossible de refuser : $e')),
      );
    } finally {
      if (mounted) setState(() => _busyIds.remove(m.id));
    }
  }

  @override
  Widget build(BuildContext context) {
    final asyncList = ref.watch(avalisteProvider);
    return Scaffold(
      backgroundColor: PaColors.canvas,
      appBar: AppBar(
        leading: const BackButton(),
        title: const Text('Mandats d\'avaliste'),
        backgroundColor: PaColors.canvas,
        surfaceTintColor: Colors.transparent,
        elevation: 0,
      ),
      body: Stack(
        children: [
          // Polling 30s : nouveaux mandats d'avaliste assignes par admin
          // ou changements de statut visibles sans pull-to-refresh.
          LivePoller(
            refresh: () => ref.read(avalisteProvider.notifier).refresh(),
            readSnapshot: () => ref.read(avalisteProvider).valueOrNull,
          ),
          PaPatternBackground(
        child: SafeArea(
          top: false,
          child: asyncList.when(
            loading: _Loading.new,
            error: (e, _) => Center(
              child: PaErrorState(
                title: 'Impossible de charger',
                message: e.toString(),
                onRetry: () => ref.read(avalisteProvider.notifier).refresh(),
              ),
            ),
            data: (data) => RefreshIndicator.adaptive(
              color: PaColors.teal,
              onRefresh: () =>
                  ref.read(avalisteProvider.notifier).refresh(),
              child: _Content(
                data: data,
                onAccept: _accept,
                onRefuse: _refuse,
                busyIds: _busyIds,
              ),
            ),
          ),
        ),
      ),
        ],
      ),
    );
  }
}

class _Content extends StatelessWidget {
  const _Content({
    required this.data,
    required this.onAccept,
    required this.onRefuse,
    required this.busyIds,
  });

  final AvalisteMandatList data;
  final Future<void> Function(AvalisteMandat) onAccept;
  final Future<void> Function(AvalisteMandat) onRefuse;
  final Set<int> busyIds;

  @override
  Widget build(BuildContext context) {
    if (data.items.isEmpty) {
      return ListView(
        padding: const EdgeInsets.fromLTRB(16, 24, 16, 32),
        children: [
          const SizedBox(height: 80),
          Icon(
            Icons.handshake_outlined,
            size: 64,
            color: PaColors.teal.withValues(alpha: 0.5),
          ),
          const SizedBox(height: 16),
          Text(
            'Aucun mandat pour l\'instant',
            textAlign: TextAlign.center,
            style: PaText.heading(size: 18),
          ),
          const SizedBox(height: 6),
          Text(
            'Quand un membre te désigne comme garant, tu le verras ici.',
            textAlign: TextAlign.center,
            style: PaText.body().copyWith(color: PaColors.inkSecondary),
          ),
        ],
      );
    }
    final pending = data.items.where((m) => m.isPending).toList();
    final history = data.items.where((m) => !m.isPending).toList();

    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 8, 16, 32),
      children: [
        if (data.pendingCount > 0) ...[
          Text(
            data.pendingCount == 1
                ? '1 demande en attente de ta réponse'
                : '${data.pendingCount} demandes en attente de ta réponse',
            style: PaText.body().copyWith(
              color: Colors.orange.shade900,
              fontWeight: FontWeight.w600,
            ),
          ),
          const SizedBox(height: 12),
        ],
        for (final m in pending) ...[
          MandatCard(
            mandat: m,
            onAccept: () => onAccept(m),
            onRefuse: () => onRefuse(m),
            busy: busyIds.contains(m.id),
          ),
          const SizedBox(height: 12),
        ],
        if (history.isNotEmpty) ...[
          const SizedBox(height: 8),
          Text('HISTORIQUE', style: PaText.eyebrow()),
          const SizedBox(height: 8),
          for (final m in history) ...[
            MandatCard(
              mandat: m,
              onAccept: () {},
              onRefuse: () {},
            ),
            const SizedBox(height: 12),
          ],
        ],
      ],
    );
  }
}

class _Loading extends StatelessWidget {
  const _Loading();
  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 32),
      children: const [
        Skeleton(height: 180, borderRadius: 16),
        SizedBox(height: 12),
        Skeleton(height: 180, borderRadius: 16),
        SizedBox(height: 12),
        Skeleton(height: 180, borderRadius: 16),
      ],
    );
  }
}
