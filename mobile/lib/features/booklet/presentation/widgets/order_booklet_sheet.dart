import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../../../app/theme/paysika/pa_colors.dart';
import '../../../../app/theme/app_radii.dart';
import '../../../../app/theme/app_spacing.dart';
import '../../../../app/theme/app_typography.dart';
import '../../../../core/di/providers.dart';
import '../../../../core/services/tara_checkout_launcher.dart';
import '../../../../core/widgets/brand_loader.dart';
import '../../../../core/widgets/paysika/pa_button.dart';
import '../../../../l10n/gen/app_localizations.dart';
import '../state/booklet_notifier.dart';

enum _Step { form, loading, success }

/// Sheet "Commander mon carnet" : versement Mobile Money + accès aux
/// documents officiels de la coopérative (spécimen carnet + règlement).
class OrderBookletSheet extends ConsumerStatefulWidget {
  const OrderBookletSheet({super.key});

  static Future<void> show(BuildContext context) {
    return showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      constraints: BoxConstraints(
        maxHeight: MediaQuery.sizeOf(context).height * 0.92,
      ),
      backgroundColor: Theme.of(context).colorScheme.surface,
      barrierColor: Colors.black.withValues(alpha: 0.45),
      shape: const RoundedRectangleBorder(borderRadius: AppRadii.sheet),
      builder: (_) => const OrderBookletSheet(),
    );
  }

  @override
  ConsumerState<OrderBookletSheet> createState() => _OrderBookletSheetState();
}

class _OrderBookletSheetState extends ConsumerState<OrderBookletSheet>
    with TickerProviderStateMixin {
  final _formKey = GlobalKey<FormState>();
  final _phoneCtrl = TextEditingController();
  // TODO: REMOVE_FOR_PROD. Mode test 100 XAF, à retirer après recette STK.
  final _amountCtrl = TextEditingController(text: '100');
  _Step _step = _Step.form;
  late final AnimationController _checkCtrl;

  // Documents officiels (PDF reglement + specimen carnet) charges via
  // l'API publique. Si null, la section affiche "Bientôt disponible".
  Future<Map<String, dynamic>>? _coopDocs;

  @override
  void initState() {
    super.initState();
    _checkCtrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 700),
    );
    _coopDocs = _loadCoopDocuments();
  }

  Future<Map<String, dynamic>> _loadCoopDocuments() async {
    try {
      final dio = ref.read(apiClientProvider).dio;
      final res = await dio.get<Map<String, dynamic>>('/audit/coop-documents/');
      return res.data ?? const {};
    } on DioException {
      return const {};
    }
  }

  @override
  void dispose() {
    _phoneCtrl.dispose();
    _amountCtrl.dispose();
    _checkCtrl.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    HapticFeedback.mediumImpact();
    setState(() => _step = _Step.loading);
    try {
      final amount = int.tryParse(_amountCtrl.text.trim()) ?? 1000;
      await ref.read(bookletProvider.notifier).order(
            phone: _phoneCtrl.text,
            network: '',
            montant: amount,
          );
      if (!mounted) return;
      setState(() => _step = _Step.success);
      HapticFeedback.heavyImpact();
      _checkCtrl.forward();
    } catch (err) {
      if (!mounted) return;
      setState(() => _step = _Step.form);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(err.toString())),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedSize(
      duration: const Duration(milliseconds: 280),
      curve: Curves.easeOutCubic,
      alignment: Alignment.topCenter,
      child: Padding(
        padding: EdgeInsets.only(
          bottom: MediaQuery.viewInsetsOf(context).bottom,
        ),
        child: SafeArea(
          top: false,
          child: switch (_step) {
            _Step.form => _form(),
            _Step.loading => _loading(),
            _Step.success => _success(context),
          },
        ),
      ),
    );
  }

  Widget _form() {
    final l = AppL10n.of(context);
    return SingleChildScrollView(
      padding: const EdgeInsets.fromLTRB(20, 8, 20, 28),
      child: Form(
        key: _formKey,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const _Grabber(),
            const SizedBox(height: AppSpacing.l),

            // Hero : illustration ronde + titre + sous-titre.
            const _Hero(),
            const SizedBox(height: AppSpacing.l),

            // Section "Documents utiles" . règlement + spécimen.
            Text(
              'Documents utiles',
              style: AppTypography.labelMedium.copyWith(
                color: PaColors.inkSecondary,
                letterSpacing: 0.6,
              ),
            ),
            const SizedBox(height: 8),
            _DocumentsSection(future: _coopDocs),

            const SizedBox(height: AppSpacing.l),

            // Section formulaire versement.
            Text(
              'Versement',
              style: AppTypography.labelMedium.copyWith(
                color: PaColors.inkSecondary,
                letterSpacing: 0.6,
              ),
            ),
            const SizedBox(height: 8),

            Text(l.common_number, style: AppTypography.labelMedium),
            const SizedBox(height: AppSpacing.s),
            TextFormField(
              controller: _phoneCtrl,
              keyboardType: TextInputType.phone,
              style: AppTypography.bodyLarge,
              decoration: InputDecoration(
                hintText: '6XX XX XX XX',
                prefixIcon: Padding(
                  padding: const EdgeInsets.only(left: 14, right: 8),
                  child: Text('+237  ', style: TextStyle(
                    color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.7),
                    fontWeight: FontWeight.w600,
                  ),),
                ),
                prefixIconConstraints:
                    const BoxConstraints(minWidth: 0, minHeight: 0),
              ),
              validator: (v) {
                final digits = (v ?? '').replaceAll(RegExp(r'\D'), '');
                if (digits.length < 8) return l.err_number_incomplete;
                return null;
              },
            ),

            const SizedBox(height: AppSpacing.l),

            // TODO: REMOVE_FOR_PROD.
            Text('Montant (XAF). mode test', style: AppTypography.labelMedium),
            const SizedBox(height: AppSpacing.s),
            TextFormField(
              controller: _amountCtrl,
              keyboardType: TextInputType.number,
              style: AppTypography.bodyLarge,
              decoration: const InputDecoration(
                hintText: '100',
                suffixText: 'XAF',
              ),
              validator: (v) {
                final n = int.tryParse((v ?? '').trim());
                if (n == null || n < 100) return 'Montant min. 100 XAF.';
                return null;
              },
            ),

            const SizedBox(height: AppSpacing.l),

            Container(
              padding: const EdgeInsets.all(13),
              decoration: BoxDecoration(
                color: PaColors.warningSurface,
                borderRadius: BorderRadius.circular(12),
              ),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Icon(Icons.menu_book_rounded,
                      size: 17, color: PaColors.warning,),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      l.bko_after_note,
                      style: const TextStyle(
                        color: PaColors.warning,
                        fontSize: 12,
                        height: 1.45,
                      ),
                    ),
                  ),
                ],
              ),
            ),

            const SizedBox(height: AppSpacing.xl),

            PaButton(label: l.bko_pay, onPressed: _submit),
          ],
        ),
      ),
    );
  }

  Widget _loading() {
    final l = AppL10n.of(context);
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 8, 20, 36),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const _Grabber(),
          const SizedBox(height: 32),
          const BrandLoader(size: BrandLoaderSize.large),
          const SizedBox(height: 22),
          Text(
            l.bko_waiting_body('Mobile Money'),
            style: AppTypography.headingSmall,
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 6),
          Text(
            'Tara confirme la transaction.',
            style: AppTypography.bodyMedium.copyWith(
              color: Theme.of(context).colorScheme.onSurface
                  .withValues(alpha: 0.7),
            ),
          ),
        ],
      ),
    );
  }

  Widget _success(BuildContext context) {
    final l = AppL10n.of(context);
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 8, 20, 28),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const _Grabber(),
          const SizedBox(height: 26),
          ScaleTransition(
            scale: CurvedAnimation(
              parent: _checkCtrl,
              curve: Curves.elasticOut,
            ),
            child: Container(
              width: 68,
              height: 68,
              decoration: BoxDecoration(
                color: PaColors.success.withValues(alpha: 0.14),
                shape: BoxShape.circle,
              ),
              alignment: Alignment.center,
              child: const Icon(
                Icons.menu_book_rounded,
                color: PaColors.success,
                size: 32,
              ),
            ),
          ),
          const SizedBox(height: 16),
          Text(l.bko_done_title, style: AppTypography.headingMedium),
          const SizedBox(height: 6),
          Text(
            "L'agence va imprimer ton carnet sous 48 h.\nTu recevras une notification au retrait.",
            textAlign: TextAlign.center,
            style: AppTypography.bodyMedium.copyWith(
              color: Theme.of(context).colorScheme.onSurface
                  .withValues(alpha: 0.7),
              height: 1.45,
            ),
          ),
          if (LastTaraResponse.vendor != null
              || LastTaraResponse.status != null) ...[
            const SizedBox(height: 14),
            _TaraConfirmedBadge(),
          ],
          const SizedBox(height: 22),
          PaButton(
            label: l.common_understood,
            onPressed: () => Navigator.of(context).pop(),
          ),
        ],
      ),
    );
  }
}


// ─────────────────────────────────────────────────────────────────────────
// Composants visuels
// ─────────────────────────────────────────────────────────────────────────


class _Hero extends StatelessWidget {
  const _Hero();

  @override
  Widget build(BuildContext context) {
    final l = AppL10n.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // Cercle dégradé teal+navy avec icône carnet.
        Container(
          width: 56,
          height: 56,
          decoration: BoxDecoration(
            gradient: LinearGradient(
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
              colors: [
                PaColors.teal.withValues(alpha: 0.22),
                PaColors.navy.withValues(alpha: 0.12),
              ],
            ),
            shape: BoxShape.circle,
            border: Border.all(
              color: PaColors.teal.withValues(alpha: 0.3),
              width: 1.2,
            ),
          ),
          alignment: Alignment.center,
          child: const Icon(
            Icons.menu_book_rounded,
            color: PaColors.navy,
            size: 26,
          ),
        ),
        const SizedBox(height: 14),
        Text(l.bko_title, style: AppTypography.headingMedium),
        const SizedBox(height: 4),
        Text(
          l.bko_sub,
          style: AppTypography.bodyMedium.copyWith(
            color: Theme.of(context).colorScheme.onSurface
                .withValues(alpha: 0.65),
            height: 1.4,
          ),
        ),
      ],
    );
  }
}


class _DocumentsSection extends StatelessWidget {
  const _DocumentsSection({required this.future});

  final Future<Map<String, dynamic>>? future;

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<Map<String, dynamic>>(
      future: future,
      builder: (context, snap) {
        final docs = snap.data ?? const <String, dynamic>{};
        final reglement = docs['reglement_interieur'] as Map<String, dynamic>?;
        final carnet = docs['carnet_specimen'] as Map<String, dynamic>?;
        return Column(
          children: [
            _DocTile(
              icon: Icons.gavel_rounded,
              label: 'Reglement interieur',
              sub: 'Statuts + droits et devoirs du sociétaire.',
              url: reglement?['url'] as String?,
              loading: snap.connectionState == ConnectionState.waiting,
            ),
            const SizedBox(height: 8),
            _DocTile(
              icon: Icons.book_outlined,
              label: 'Specimen du carnet',
              sub: 'Aperçu du carnet remis après paiement.',
              url: carnet?['url'] as String?,
              loading: snap.connectionState == ConnectionState.waiting,
            ),
          ],
        );
      },
    );
  }
}


class _DocTile extends StatelessWidget {
  const _DocTile({
    required this.icon,
    required this.label,
    required this.sub,
    required this.url,
    required this.loading,
  });

  final IconData icon;
  final String label;
  final String sub;
  final String? url;
  final bool loading;

  Future<void> _open(BuildContext context) async {
    final raw = url;
    if (raw == null || raw.isEmpty) return;
    final uri = Uri.tryParse(raw);
    if (uri == null) return;
    final ok = await launchUrl(uri, mode: LaunchMode.externalApplication);
    if (!ok && context.mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Impossible d\'ouvrir le PDF.')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final available = url != null && url!.isNotEmpty && !loading;
    final color = available ? PaColors.navy : PaColors.inkMuted;
    return Material(
      color: PaColors.cardBg,
      borderRadius: BorderRadius.circular(14),
      child: InkWell(
        onTap: available ? () => _open(context) : null,
        borderRadius: BorderRadius.circular(14),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 13, vertical: 12),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(14),
            border: Border.all(color: PaColors.line, width: 1),
          ),
          child: Row(
            children: [
              Container(
                width: 38,
                height: 38,
                decoration: BoxDecoration(
                  color: color.withValues(alpha: 0.10),
                  borderRadius: BorderRadius.circular(10),
                ),
                alignment: Alignment.center,
                child: Icon(icon, color: color, size: 18),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(
                      label,
                      style: AppTypography.labelMedium.copyWith(
                        color: PaColors.inkPrimary,
                        fontWeight: FontWeight.w700,
                        fontSize: 13.5,
                      ),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      available ? sub : 'Bientôt disponible.',
                      style: AppTypography.bodySmall.copyWith(
                        color: PaColors.inkSecondary,
                        fontSize: 11.5,
                        height: 1.35,
                      ),
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ],
                ),
              ),
              if (loading)
                const SizedBox(
                  width: 16, height: 16,
                  child: CircularProgressIndicator(strokeWidth: 2),
                )
              else
                Icon(
                  available
                      ? Icons.file_download_outlined
                      : Icons.lock_clock_outlined,
                  size: 18,
                  color: color.withValues(alpha: 0.75),
                ),
            ],
          ),
        ),
      ),
    );
  }
}


class _TaraConfirmedBadge extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(11),
      decoration: BoxDecoration(
        color: PaColors.teal.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(11),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (LastTaraResponse.prettyVendor != null)
            Row(
              children: [
                const Icon(Icons.check_circle_outline_rounded,
                    size: 15, color: PaColors.teal,),
                const SizedBox(width: 8),
                Text(
                  'Confirme. ${LastTaraResponse.prettyVendor}',
                  style: AppTypography.labelMedium.copyWith(
                    color: PaColors.teal,
                    fontSize: 12,
                  ),
                ),
              ],
            ),
          if (LastTaraResponse.message != null) ...[
            const SizedBox(height: 4),
            Text(
              'Statut Tara. ${LastTaraResponse.status} '
                  '(${LastTaraResponse.message})',
              style: AppTypography.bodySmall.copyWith(
                color: Theme.of(context).colorScheme.onSurface
                    .withValues(alpha: 0.65),
                fontSize: 11,
              ),
            ),
          ],
        ],
      ),
    );
  }
}


class _Grabber extends StatelessWidget {
  const _Grabber();

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Container(
        width: 36,
        height: 4,
        decoration: BoxDecoration(
          color: Theme.of(context).colorScheme.outline,
          borderRadius: BorderRadius.circular(2),
        ),
      ),
    );
  }
}
