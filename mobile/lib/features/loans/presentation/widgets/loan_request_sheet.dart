import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../app/theme/paysika/pa_colors.dart';
import '../../../../app/theme/app_radii.dart';
import '../../../../app/theme/app_spacing.dart';
import '../../../../app/theme/app_typography.dart';
import '../../../../core/di/providers.dart';
import '../../../../core/formatters/xaf_formatter.dart';
import '../../../../core/widgets/brand_loader.dart';
import '../../../../core/widgets/paysika/pa_button.dart';
import '../../../../l10n/gen/app_localizations.dart';
import '../../../forms/domain/form_validation.dart';
import '../../../forms/presentation/widgets/dynamic_fields.dart';
import '../../domain/entities/eligibility.dart';
import '../../domain/entities/loan_request.dart';
import '../../domain/entities/loan_request_submission.dart';
import '../../domain/loan_terms.dart';
import '../state/loans_notifier.dart';

/// CH-5 — Champs hardcoded du sheet : déjà rendus par l'UI métier dédiée
/// (slider montant, sliders durée, motif, sélecteur canal). Le renderer
/// dynamique exclut ces ids pour ne rien dupliquer côté membre.
const Set<String> _hardcodedLoanFields = {
  'montant_demande',
  'duree_mois',
  'motif',
  'modalite_paiement',
  'avaliste_numero',
  'avaliste_nom',
  'campaign_id',
  'profil_cible',
  'moyen_reception',
  'recipient_phone',
};

/// Modale demande de crédit — 2 étapes :
/// 1. Eligibility check + formulaire (montant slider + durée slider + motif)
/// 2. Success (demande créée, lien vers paiement frais à venir)
class LoanRequestSheet extends ConsumerStatefulWidget {
  const LoanRequestSheet({super.key, required this.eligibility});

  final Eligibility eligibility;

  static Future<void> show(BuildContext context, Eligibility eligibility) {
    return showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      // Plafonne le sheet pour qu'il flotte avec une marge sous la status bar
      // (corners arrondis visibles) au lieu de grimper plein écran. Le contenu
      // scrolle à l'intérieur si besoin.
      constraints: BoxConstraints(
        maxHeight: MediaQuery.sizeOf(context).height * 0.9,
      ),
      backgroundColor: Theme.of(context).colorScheme.surface,
      barrierColor: Colors.black.withValues(alpha: 0.45),
      shape: const RoundedRectangleBorder(borderRadius: AppRadii.sheet),
      builder: (_) => LoanRequestSheet(eligibility: eligibility),
    );
  }

  @override
  ConsumerState<LoanRequestSheet> createState() => _LoanRequestSheetState();
}

/// Étapes du sheet de demande :
/// `form` → `loading` → `success` (affiche les frais d'étude CH-7).
/// Depuis `success`, le membre peut payer maintenant (`payForm` → `payLoading`
/// → `paySuccess`) ou fermer ; les frais resteront à régler depuis la liste.
enum _Step { form, loading, success, payForm, payLoading, paySuccess }

class _LoanRequestSheetState extends ConsumerState<LoanRequestSheet>
    with TickerProviderStateMixin {
  final _motifCtrl = TextEditingController();
  // §7.2 BUSINESS_RULES_2026 — Désignation optionnelle d'un avaliste senior+BRC.
  // Si renseignés, le backend bascule la voie EligibilityRoute.AVALISTE.
  bool _withAvaliste = false;
  final _avalisteNumeroCtrl = TextEditingController();
  final _avalisteNomCtrl = TextEditingController();
  // CH-9 — Canal de réception choisi par le membre + numéro Mobile Money.
  final _phoneCtrl = TextEditingController();
  // CH-7 — Numéro Mobile Money pour régler les frais d'étude.
  final _feePhoneCtrl = TextEditingController();
  LoanReceiveChannel _canal = LoanReceiveChannel.taraMomo;
  // CH-7 — Réseau choisi pour le paiement des frais ('mtn' | 'orange').
  String _feeNetwork = 'mtn';
  LoanRequestSubmission? _submission;

  // CH-5 — Valeurs des champs supplémentaires du FormSchema actif. Le
  // renderer expose des [PickedFile] pour les champs `file` ; le submit
  // les sépare des scalaires pour appeler un upload multipart à part.
  Map<String, Object?> _extraValues = {};
  Map<String, String> _extraErrors = {};

  double _montant = 200000;
  // Durée NON saisie manuellement : dérivée du montant (Art. 7).
  PaymentModality _modalite = PaymentModality.mensuel;
  _Step _step = _Step.form;
  late final AnimationController _checkCtrl;

  /// Décomposition règlementaire live (taux 10 %, durée par palier, échéancier).
  LoanBreakdown get _bd => computeLoanBreakdown(_montant, modalite: _modalite);

  @override
  void initState() {
    super.initState();
    final cap = widget.eligibility.plafondMax.toDouble();
    _montant = (cap >= 200000 ? 200000 : cap).toDouble();
    _checkCtrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 700),
    );
  }

  @override
  void dispose() {
    _motifCtrl.dispose();
    _phoneCtrl.dispose();
    _feePhoneCtrl.dispose();
    _avalisteNumeroCtrl.dispose();
    _avalisteNomCtrl.dispose();
    _checkCtrl.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (_motifCtrl.text.trim().length < 10) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(AppL10n.of(context).lreq_motive_short)),
      );
      return;
    }
    // BUSINESS_RULES §7.2 — Si avaliste activé, les 2 champs sont requis.
    final avalisteNumero = _avalisteNumeroCtrl.text.trim();
    final avalisteNom = _avalisteNomCtrl.text.trim();
    if (_withAvaliste &&
        (avalisteNumero.length < 4 || avalisteNom.length < 2)) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text(
            "Renseigne le numéro et le nom de l'avaliste (ou décoche).",
          ),
        ),
      );
      return;
    }
    // CH-9 — Si canal Tara MoMo/OM, un numéro est requis (validation locale
    // avant l'appel use case qui re-vérifie).
    final phone = _phoneCtrl.text.trim();
    final needsPhone = _canal == LoanReceiveChannel.taraOm ||
        _canal == LoanReceiveChannel.taraMomo;
    if (needsPhone && phone.length < 9) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Numéro Mobile Money requis (au moins 9 chiffres).'),
        ),
      );
      return;
    }
    // CH-5 — Validation locale des champs dynamiques (FormSchema actif).
    final schema = ref.read(activeLoanRequestSchemaProvider).valueOrNull;
    if (schema != null) {
      final errs = validateSchema(
        schema,
        _extraValues,
        excludeIds: _hardcodedLoanFields,
      );
      if (errs.isNotEmpty) {
        setState(() => _extraErrors = errs);
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text(
              'Certains champs supplémentaires sont à compléter.',
            ),
          ),
        );
        return;
      }
      setState(() => _extraErrors = const {});
    }
    HapticFeedback.mediumImpact();
    setState(() => _step = _Step.loading);
    try {
      // CH-5 — Sépare les fichiers (PickedFile) des scalaires : seuls les
      // scalaires partent dans le body POST ; les fichiers sont uploadés
      // séparément après création du LoanRequest.
      final scalarExtras = <String, Object?>{};
      final fileEntries = <MapEntry<String, PickedFile>>[];
      for (final entry in _extraValues.entries) {
        final v = entry.value;
        if (v is PickedFile) {
          fileEntries.add(MapEntry(entry.key, v));
        } else if (v != null && v != '') {
          scalarExtras[entry.key] = v;
        }
      }
      // BUSINESS_RULES §7.2 — Injecte les champs avaliste dans le body
      // attendu par LoanRequestSubmitSerializer (clés snake_case backend).
      if (_withAvaliste) {
        scalarExtras['avaliste_numero'] = avalisteNumero;
        scalarExtras['avaliste_nom'] = avalisteNom;
      }
      final submission =
          await ref.read(loanRequestsProvider.notifier).submit(
                montantDemande: _montant.round(),
                dureeMois: _bd.dureeMois, // dérivée du montant (Art. 7)
                motif: _motifCtrl.text.trim(),
                moyenReception: _canal,
                recipientPhone: needsPhone ? phone : null,
                extraValues: scalarExtras,
              );
      // CH-5 — Upload best-effort des pièces jointes. Un échec d'upload ne
      // bloque pas la création : la demande existe ; l'admin demandera
      // un re-upload si besoin.
      for (final entry in fileEntries) {
        try {
          await ref.read(loanRequestsProvider.notifier).uploadAttachment(
                loanRequestId: submission.request.id,
                schemaFieldId: entry.key,
                filePath: entry.value.path,
                fileName: entry.value.name,
              );
        } catch (_) {
          // Best-effort — log silencieux côté mobile (pas d'analytics ici).
        }
      }
      if (!mounted) return;
      // CH-7 — Pré-remplit le téléphone côté paiement des frais : si le canal
      // de réception choisi est Tara MoMo, on reprend le numéro saisi ; sinon
      // on laisse vide pour que le membre choisisse.
      if (needsPhone && _feePhoneCtrl.text.isEmpty) {
        _feePhoneCtrl.text = phone;
        _feeNetwork = _canal == LoanReceiveChannel.taraOm ? 'orange' : 'mtn';
      }
      setState(() {
        _submission = submission;
        _step = _Step.success;
      });
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

  /// CH-7 — Lance le paiement des frais d'étude via Mobile Money.
  Future<void> _payStudyFee() async {
    final phone = _feePhoneCtrl.text.trim();
    if (phone.length < 9) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Numéro Mobile Money requis (au moins 9 chiffres).'),
        ),
      );
      return;
    }
    HapticFeedback.mediumImpact();
    setState(() => _step = _Step.payLoading);
    try {
      await ref.read(loanRequestsProvider.notifier).payStudyFee(
            phone: phone,
            network: _feeNetwork,
          );
      if (!mounted) return;
      setState(() => _step = _Step.paySuccess);
      HapticFeedback.heavyImpact();
    } catch (err) {
      if (!mounted) return;
      setState(() => _step = _Step.payForm);
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
            _Step.form => _formStep(),
            _Step.loading => _loadingStep(),
            _Step.success => _successStep(context),
            _Step.payForm => _payFormStep(context),
            _Step.payLoading => _loadingStep(),
            _Step.paySuccess => _paySuccessStep(context),
          },
        ),
      ),
    );
  }

  Widget _formStep() {
    final l = AppL10n.of(context);
    final cap = widget.eligibility.plafondMax.toDouble();
    final maxSlider = cap > kMinLoanAmount ? cap : kMinLoanAmount.toDouble();
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 8, 20, 24),
      child: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const _Grabber(),
            const SizedBox(height: AppSpacing.l),
            Text(l.lreq_title, style: AppTypography.headingMedium),
            const SizedBox(height: 4),
            Text(
              l.lreq_intro,
              style: AppTypography.bodySmall.copyWith(
                color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.5),
                height: 1.5,
              ),
            ),

            const SizedBox(height: AppSpacing.xl),

            // --- Montant ---
            Row(
              children: [
                Text(l.lreq_amount, style: AppTypography.labelMedium),
                const Spacer(),
                Text(
                  XAFFormatter.format(_montant),
                  style: AppTypography.headingSmall.copyWith(
                    color: PaColors.teal,
                    fontFeatures: const [FontFeature.tabularFigures()],
                  ),
                ),
              ],
            ),
            const SizedBox(height: 4),
            SliderTheme(
              data: SliderThemeData(
                trackHeight: 6,
                activeTrackColor: PaColors.teal,
                inactiveTrackColor: PaColors.tealSurface,
                thumbColor: PaColors.teal,
                overlayColor: PaColors.teal.withValues(alpha: 0.12),
                thumbShape: const RoundSliderThumbShape(enabledThumbRadius: 11),
                overlayShape: const RoundSliderOverlayShape(overlayRadius: 22),
              ),
              child: Slider(
                min: kMinLoanAmount.toDouble(),
                max: maxSlider,
                divisions: 40,
                value: _montant.clamp(kMinLoanAmount.toDouble(), maxSlider),
                onChanged: (v) => setState(() => _montant = (v / 1000).round() * 1000),
              ),
            ),

            const SizedBox(height: AppSpacing.l),

            // --- Modalité de remboursement (Art. 8) ---
            Text(l.lreq_modality, style: AppTypography.labelMedium),
            const SizedBox(height: AppSpacing.s),
            Row(
              children: [
                for (final m in PaymentModality.values) ...[
                  Expanded(
                    child: _ModalityChip(
                      label: m.label,
                      selected: _modalite == m,
                      onTap: () => setState(() => _modalite = m),
                    ),
                  ),
                  if (m != PaymentModality.values.last)
                    const SizedBox(width: 8),
                ],
              ],
            ),

            const SizedBox(height: AppSpacing.l),

            // --- Récapitulatif échéancier (dérivé du montant + modalité) ---
            _ScheduleRecap(bd: _bd),

            const SizedBox(height: AppSpacing.l),

            // --- Motivation ---
            Text(l.lreq_motive, style: AppTypography.labelMedium),
            const SizedBox(height: AppSpacing.s),
            TextFormField(
              controller: _motifCtrl,
              maxLines: 4,
              maxLength: 500,
              style: AppTypography.bodyLarge,
              decoration: InputDecoration(
                hintText: l.lreq_motive_hint,
                contentPadding:
                    const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
              ),
            ),

            const SizedBox(height: AppSpacing.l),

            // --- BUSINESS_RULES §7.2 — Désignation optionnelle d'un avaliste ---
            //
            // Si le membre veut emprunter sur la voie AVALISTE (typiquement
            // parce qu'il n'est pas senior+BRC ou qu'il a déjà un crédit en
            // cours), il saisit ici le numéro d'identification + nom de
            // famille de l'avaliste, qui recevra une notification de consent.
            // Si laissé fermé, le backend tente d'abord la voie SENIOR_BRC.
            SwitchListTile.adaptive(
              dense: true,
              contentPadding: EdgeInsets.zero,
              value: _withAvaliste,
              onChanged: (v) => setState(() => _withAvaliste = v),
              title: Text(
                'Désigner un avaliste',
                style: AppTypography.labelMedium,
              ),
              subtitle: const Text(
                'Membre senior+BRC qui garantit le crédit (§7.2).',
                style: TextStyle(fontSize: 12),
              ),
            ),
            if (_withAvaliste) ...[
              const SizedBox(height: AppSpacing.s),
              TextFormField(
                controller: _avalisteNumeroCtrl,
                style: AppTypography.bodyLarge,
                textCapitalization: TextCapitalization.characters,
                decoration: const InputDecoration(
                  hintText: 'Numéro d\'identification (ex. GF-2024-0042)',
                  prefixIcon: Icon(Icons.badge_outlined, size: 20),
                  contentPadding:
                      EdgeInsets.symmetric(horizontal: 16, vertical: 14),
                ),
              ),
              const SizedBox(height: AppSpacing.s),
              TextFormField(
                controller: _avalisteNomCtrl,
                style: AppTypography.bodyLarge,
                textCapitalization: TextCapitalization.words,
                decoration: const InputDecoration(
                  hintText: 'Nom de famille de l\'avaliste',
                  prefixIcon: Icon(Icons.person_outline, size: 20),
                  contentPadding:
                      EdgeInsets.symmetric(horizontal: 16, vertical: 14),
                ),
              ),
              const SizedBox(height: AppSpacing.m),
            ] else
              const SizedBox(height: AppSpacing.m),

            // --- CH-9 — Canal de réception du décaissement ---
            Text('Comment recevoir l\'argent ?',
                style: AppTypography.labelMedium),
            const SizedBox(height: AppSpacing.s),
            _ChannelPicker(
              selected: _canal,
              onChanged: (c) => setState(() => _canal = c),
            ),

            // Champ téléphone, visible seulement pour Tara MoMo/OM.
            if (_canal == LoanReceiveChannel.taraOm ||
                _canal == LoanReceiveChannel.taraMomo) ...[
              const SizedBox(height: AppSpacing.s),
              TextFormField(
                controller: _phoneCtrl,
                keyboardType: TextInputType.phone,
                style: AppTypography.bodyLarge,
                decoration: const InputDecoration(
                  hintText: '+237 6XX XX XX XX',
                  prefixIcon: Icon(Icons.phone_iphone_rounded, size: 20),
                  contentPadding:
                      EdgeInsets.symmetric(horizontal: 16, vertical: 14),
                ),
              ),
            ],

            const SizedBox(height: AppSpacing.m),

            // Estimation des frais
            Container(
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                color: PaColors.warningSurface,
                borderRadius: BorderRadius.circular(14),
              ),
              child: Row(
                children: [
                  const Icon(Icons.info_outline_rounded,
                      size: 18, color: PaColors.warning),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      l.lreq_fees_note,
                      style: const TextStyle(
                        color: PaColors.warning,
                        fontSize: 12.5,
                        height: 1.45,
                      ),
                    ),
                  ),
                ],
              ),
            ),

            // CH-5 — Section dynamique : champs supplémentaires configurés
            // par l'admin via FormSchema actif (`loan_request`). En 404 ou
            // erreur transport, on garde le formulaire legacy intact.
            Consumer(
              builder: (context, ref, _) {
                final schemaAsync =
                    ref.watch(activeLoanRequestSchemaProvider);
                final schema = schemaAsync.valueOrNull;
                if (schema == null) return const SizedBox.shrink();
                return Padding(
                  padding: const EdgeInsets.only(top: AppSpacing.l),
                  child: DynamicFields(
                    schema: schema,
                    values: _extraValues,
                    onChange: (v) => setState(() => _extraValues = v),
                    excludeIds: _hardcodedLoanFields,
                    errors: _extraErrors,
                  ),
                );
              },
            ),

            const SizedBox(height: AppSpacing.xl),

            PaButton(label: l.lreq_submit, onPressed: _submit),
          ],
        ),
      ),
    );
  }

  Widget _loadingStep() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 8, 20, 36),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const _Grabber(),
          const SizedBox(height: 36),
          const BrandLoader(size: BrandLoaderSize.large),
          const SizedBox(height: 24),
          Text(AppL10n.of(context).lreq_sending,
              style: AppTypography.headingSmall),
        ],
      ),
    );
  }

  Widget _successStep(BuildContext context) {
    final l = AppL10n.of(context);
    final studyFee = _submission?.studyFee;
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 8, 20, 28),
      child: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const _Grabber(),
            const SizedBox(height: 24),
            ScaleTransition(
              scale:
                  CurvedAnimation(parent: _checkCtrl, curve: Curves.elasticOut),
              child: Container(
                width: 64,
                height: 64,
                decoration: BoxDecoration(
                  color: PaColors.success.withValues(alpha: 0.14),
                  shape: BoxShape.circle,
                ),
                alignment: Alignment.center,
                child: const Icon(Icons.check_rounded,
                    color: PaColors.success, size: 34),
              ),
            ),
            const SizedBox(height: 16),
            Text(l.lreq_sent_title, style: AppTypography.headingMedium),
            const SizedBox(height: 6),
            Text(
              l.lreq_sent_body,
              textAlign: TextAlign.center,
              style: AppTypography.bodyMedium.copyWith(
                color: Theme.of(context)
                    .colorScheme
                    .onSurface
                    .withValues(alpha: 0.7),
                height: 1.45,
              ),
            ),
            if (studyFee != null) ...[
              const SizedBox(height: 22),
              _StudyFeeCard(fee: studyFee),
              const SizedBox(height: 18),
              PaButton(
                label:
                    'Payer ${XAFFormatter.format(studyFee.montant)} maintenant',
                onPressed: () => setState(() => _step = _Step.payForm),
              ),
              const SizedBox(height: 10),
              TextButton(
                onPressed: () => Navigator.of(context).pop(),
                style: TextButton.styleFrom(
                  foregroundColor: PaColors.inkSecondary,
                  padding:
                      const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                ),
                child: const Text(
                  'Payer plus tard',
                  style:
                      TextStyle(fontWeight: FontWeight.w600, fontSize: 13.5),
                ),
              ),
            ] else ...[
              const SizedBox(height: 22),
              PaButton(
                label: l.common_understood,
                onPressed: () => Navigator.of(context).pop(),
              ),
            ],
          ],
        ),
      ),
    );
  }

  /// CH-7 — Formulaire de paiement Mobile Money pour les frais d'étude.
  Widget _payFormStep(BuildContext context) {
    final studyFee = _submission?.studyFee;
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 8, 20, 28),
      child: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const _Grabber(),
            const SizedBox(height: AppSpacing.l),
            Text(
              'Régler les frais d\'étude',
              style: AppTypography.headingMedium,
            ),
            const SizedBox(height: 6),
            if (studyFee != null)
              Text(
                'Montant : ${XAFFormatter.format(studyFee.montant)}',
                style: AppTypography.bodyMedium.copyWith(
                  color: PaColors.teal,
                  fontWeight: FontWeight.w700,
                ),
              ),
            const SizedBox(height: AppSpacing.l),

            // Sélecteur réseau MTN / Orange.
            Text('Opérateur', style: AppTypography.labelMedium),
            const SizedBox(height: AppSpacing.s),
            Row(
              children: [
                Expanded(
                  child: _NetworkChip(
                    label: 'MTN Mobile Money',
                    selected: _feeNetwork == 'mtn',
                    onTap: () => setState(() => _feeNetwork = 'mtn'),
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: _NetworkChip(
                    label: 'Orange Money',
                    selected: _feeNetwork == 'orange',
                    onTap: () => setState(() => _feeNetwork = 'orange'),
                  ),
                ),
              ],
            ),

            const SizedBox(height: AppSpacing.l),
            Text('Numéro Mobile Money', style: AppTypography.labelMedium),
            const SizedBox(height: AppSpacing.s),
            TextFormField(
              controller: _feePhoneCtrl,
              keyboardType: TextInputType.phone,
              style: AppTypography.bodyLarge,
              decoration: const InputDecoration(
                hintText: '+237 6XX XX XX XX',
                prefixIcon: Icon(Icons.phone_iphone_rounded, size: 20),
                contentPadding:
                    EdgeInsets.symmetric(horizontal: 16, vertical: 14),
              ),
            ),

            const SizedBox(height: AppSpacing.m),
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: PaColors.tealSurface,
                borderRadius: BorderRadius.circular(12),
              ),
              child: Row(
                children: [
                  const Icon(Icons.info_outline_rounded,
                      size: 18, color: PaColors.teal),
                  const SizedBox(width: 10),
                  const Expanded(
                    child: Text(
                      'Vous allez recevoir une notification Mobile Money sur '
                      'ce numéro pour valider le paiement.',
                      style: TextStyle(
                        color: PaColors.navy,
                        fontSize: 12.5,
                        height: 1.4,
                      ),
                    ),
                  ),
                ],
              ),
            ),

            const SizedBox(height: AppSpacing.xl),
            PaButton(
              label: studyFee != null
                  ? 'Payer ${XAFFormatter.format(studyFee.montant)}'
                  : 'Payer maintenant',
              onPressed: _payStudyFee,
            ),
            const SizedBox(height: 8),
            TextButton(
              onPressed: () => setState(() => _step = _Step.success),
              style: TextButton.styleFrom(
                foregroundColor: PaColors.inkSecondary,
                padding:
                    const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
              ),
              child: const Text('Retour'),
            ),
          ],
        ),
      ),
    );
  }

  /// CH-7 — Confirmation après init Tara du paiement des frais.
  Widget _paySuccessStep(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 8, 20, 28),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const _Grabber(),
          const SizedBox(height: 28),
          Container(
            width: 72,
            height: 72,
            decoration: BoxDecoration(
              color: PaColors.success.withValues(alpha: 0.14),
              shape: BoxShape.circle,
            ),
            alignment: Alignment.center,
            child: const Icon(Icons.payments_outlined,
                color: PaColors.success, size: 38),
          ),
          const SizedBox(height: 18),
          const Text(
            'Paiement en cours',
            style: TextStyle(
              fontSize: 22,
              fontWeight: FontWeight.w700,
              color: PaColors.navy,
            ),
          ),
          const SizedBox(height: 6),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 12),
            child: Text(
              'Validez la notification Mobile Money sur votre téléphone. '
              'Dès confirmation, votre demande passera en instruction.',
              textAlign: TextAlign.center,
              style: AppTypography.bodyMedium.copyWith(
                color: Theme.of(context)
                    .colorScheme
                    .onSurface
                    .withValues(alpha: 0.7),
                height: 1.45,
              ),
            ),
          ),
          const SizedBox(height: 24),
          PaButton(
            label: 'J\'ai compris',
            onPressed: () => Navigator.of(context).pop(),
          ),
        ],
      ),
    );
  }
}

/// CH-7 — Carte récapitulative des frais d'étude (montant + notice
/// non-remboursable). Apparaît juste après la soumission de la demande,
/// avant que le membre n'engage le paiement.
class _StudyFeeCard extends StatelessWidget {
  const _StudyFeeCard({required this.fee});

  final LoanRequestStudyFee fee;

  @override
  Widget build(BuildContext context) {
    final montant = fee.montant;
    final libelle = fee.libelle;
    final notice = fee.notice;
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: PaColors.warningSurface,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: PaColors.warning.withValues(alpha: 0.3)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.receipt_long_rounded,
                  size: 18, color: PaColors.warning),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  libelle,
                  style: AppTypography.labelMedium.copyWith(
                    color: PaColors.warning,
                    fontWeight: FontWeight.w800,
                  ),
                ),
              ),
              Text(
                XAFFormatter.format(montant),
                style: AppTypography.headingSmall.copyWith(
                  color: PaColors.warning,
                  fontFeatures: const [FontFeature.tabularFigures()],
                ),
              ),
            ],
          ),
          if (notice.isNotEmpty) ...[
            const SizedBox(height: 10),
            Text(
              notice,
              style: TextStyle(
                color: PaColors.warning.withValues(alpha: 0.95),
                fontSize: 12.5,
                height: 1.45,
              ),
            ),
          ],
        ],
      ),
    );
  }
}

/// CH-7 — Pastille MTN / Orange pour le paiement des frais d'étude.
class _NetworkChip extends StatelessWidget {
  const _NetworkChip({
    required this.label,
    required this.selected,
    required this.onTap,
  });

  final String label;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: selected ? PaColors.navy : PaColors.cardBg,
      borderRadius: BorderRadius.circular(12),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(12),
        child: Container(
          height: 44,
          alignment: Alignment.center,
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(12),
            border: Border.all(
              color: selected ? PaColors.navy : PaColors.line,
              width: 1,
            ),
          ),
          child: Text(
            label,
            style: AppTypography.labelMedium.copyWith(
              color: selected ? Colors.white : PaColors.inkSecondary,
              fontWeight: FontWeight.w700,
              fontSize: 12,
            ),
          ),
        ),
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


/// Chip de modalité de remboursement (journalier / hebdo / mensuel).
class _ModalityChip extends StatelessWidget {
  const _ModalityChip({
    required this.label,
    required this.selected,
    required this.onTap,
  });

  final String label;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: selected ? PaColors.navy : PaColors.cardBg,
      borderRadius: BorderRadius.circular(12),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(12),
        child: Container(
          height: 42,
          alignment: Alignment.center,
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(12),
            border: Border.all(
              color: selected ? PaColors.navy : PaColors.line,
              width: 1,
            ),
          ),
          child: Text(
            label,
            style: AppTypography.labelMedium.copyWith(
              color: selected ? Colors.white : PaColors.inkSecondary,
              fontWeight: FontWeight.w600,
              fontSize: 12.5,
            ),
          ),
        ),
      ),
    );
  }
}


/// Récapitulatif de l'échéancier dérivé du montant (Articles 5, 7, 8).
class _ScheduleRecap extends StatelessWidget {
  const _ScheduleRecap({required this.bd});

  final LoanBreakdown bd;

  @override
  Widget build(BuildContext context) {
    final l = AppL10n.of(context);
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: PaColors.tealSurface,
        borderRadius: BorderRadius.circular(16),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.event_note_outlined, size: 18, color: PaColors.teal),
              const SizedBox(width: 8),
              Text(
                l.lreq_schedule,
                style: AppTypography.labelMedium.copyWith(
                  color: PaColors.navy,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          _row(l.lreq_duration, l.states_months(bd.dureeMois)),
          _row(l.lreq_interest, XAFFormatter.format(bd.interetsTotaux)),
          _row(l.lreq_total, XAFFormatter.format(bd.montantTotalDu),
              strong: true),
          const Divider(height: 18, color: PaColors.line),
          _row(
            l.lreq_installments('${bd.nbEcheances}'),
            l.lreq_per_time(XAFFormatter.format(bd.montantParEcheance)),
            strong: true,
            accent: true,
          ),
        ],
      ),
    );
  }

  Widget _row(String label, String value,
      {bool strong = false, bool accent = false}) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 3),
      child: Row(
        children: [
          Text(
            label,
            style: AppTypography.bodySmall.copyWith(
              color: PaColors.inkSecondary,
              fontSize: 13,
            ),
          ),
          const Spacer(),
          Text(
            value,
            style: AppTypography.bodySmall.copyWith(
              color: accent ? PaColors.teal : PaColors.inkPrimary,
              fontSize: strong ? 14 : 13,
              fontWeight: strong ? FontWeight.w700 : FontWeight.w600,
              fontFeatures: const [FontFeature.tabularFigures()],
            ),
          ),
        ],
      ),
    );
  }
}


// CH-9 — Sélecteur de canal de réception (Orange Money / MTN MoMo / espèces).
class _ChannelPicker extends StatelessWidget {
  const _ChannelPicker({required this.selected, required this.onChanged});

  final LoanReceiveChannel selected;
  final ValueChanged<LoanReceiveChannel> onChanged;

  static const _options = <(LoanReceiveChannel, String, IconData)>[
    (LoanReceiveChannel.taraMomo, 'MTN MoMo', Icons.phone_android_rounded),
    (LoanReceiveChannel.taraOm, 'Orange Money', Icons.phone_android_rounded),
    (LoanReceiveChannel.agenceEspeces, 'Espèces (agence)', Icons.payments_rounded),
  ];

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        for (final entry in _options) ...[
          InkWell(
            onTap: () => onChanged(entry.$1),
            borderRadius: BorderRadius.circular(14),
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
              decoration: BoxDecoration(
                color: selected == entry.$1
                    ? PaColors.teal.withValues(alpha: 0.08)
                    : PaColors.paper,
                borderRadius: BorderRadius.circular(14),
                border: Border.all(
                  color: selected == entry.$1
                      ? PaColors.teal
                      : PaColors.line.withValues(alpha: 0.5),
                  width: selected == entry.$1 ? 1.5 : 1,
                ),
              ),
              child: Row(
                children: [
                  Icon(
                    entry.$3,
                    size: 20,
                    color: selected == entry.$1
                        ? PaColors.teal
                        : PaColors.inkSecondary,
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Text(
                      entry.$2,
                      style: AppTypography.bodyLarge.copyWith(
                        fontWeight: FontWeight.w600,
                        color: selected == entry.$1
                            ? PaColors.teal
                            : PaColors.inkPrimary,
                      ),
                    ),
                  ),
                  if (selected == entry.$1)
                    const Icon(Icons.check_circle_rounded,
                        size: 20, color: PaColors.teal),
                ],
              ),
            ),
          ),
          if (entry != _options.last) const SizedBox(height: 8),
        ],
      ],
    );
  }
}
