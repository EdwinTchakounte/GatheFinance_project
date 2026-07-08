import 'dart:async';
import 'package:file_picker/file_picker.dart';
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
import '../../../avaliste/domain/entities/avaliste_candidate.dart';
import '../../../forms/domain/form_validation.dart';
import '../../../forms/presentation/widgets/dynamic_fields.dart';
import '../../../home_feed/domain/entities/feed_item.dart';
import '../../../home_feed/presentation/state/feed_notifier.dart';
import '../../domain/entities/eligibility.dart';
import '../../domain/entities/loan_request.dart';
import '../../domain/entities/loan_request_submission.dart';
import '../../domain/loan_terms.dart';
import '../state/loans_notifier.dart';

/// Campagnes micro-crédit actives . fetch unique à l'ouverture du sheet quand
/// le membre coche "Je postule à une campagne". Paginé côté backend mais on
/// se contente des 50 premières (les listes sont courtes en pratique).
final _activeCampaignsForPickerProvider =
    FutureProvider.autoDispose<List<CampaignFlyer>>((ref) async {
  final ds = ref.read(feedDataSourceProvider);
  final page = await ds.activeCampaigns(limit: 50, offset: 0);
  return page.items;
});

/// CH-5 . Champs hardcoded du sheet : déjà rendus par l'UI métier dédiée
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

/// Les voies d'éligibilité présentées sur la page crédit. Permet d'ouvrir
/// le sheet en présélectionnant la voie que le membre a touchée. La voie
/// « garantie matérielle » (L4) route vers EligibilityRoute.GARANTIE_MATERIELLE
/// quand le membre n'a ni auto-couverture ni avaliste et propose un bien.
enum LoanRequestVoie { brc, avaliste, campaign, garantieMaterielle }

/// Modale demande de crédit . 2 étapes :
/// 1. Eligibility check + formulaire (montant slider + durée slider + motif)
/// 2. Success (demande créée, lien vers paiement frais à venir)
class LoanRequestSheet extends ConsumerStatefulWidget {
  const LoanRequestSheet({
    super.key,
    required this.eligibility,
    this.prefillCampaignId,
    this.initialVoie,
  });

  final Eligibility eligibility;

  /// Id de campagne à présélectionner . utilisé quand le sheet est ouvert
  /// depuis la Home ou la liste in-app `/campaigns`. Active automatiquement
  /// la voie campagne du formulaire.
  final int? prefillCampaignId;

  /// Voie présélectionnée quand le membre ouvre le sheet en touchant une
  /// carte « voie de crédit » sur la page crédit. `null` → voie BRC (défaut).
  final LoanRequestVoie? initialVoie;

  static Future<void> show(
    BuildContext context,
    Eligibility eligibility, {
    int? prefillCampaignId,
    LoanRequestVoie? initialVoie,
  }) {
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
      builder: (_) => LoanRequestSheet(
        eligibility: eligibility,
        prefillCampaignId: prefillCampaignId,
        initialVoie: initialVoie,
      ),
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
  // L5 identité . Numéro de CNI du demandeur, capté à la demande de crédit et
  // envoyé au backend (champ `cni_demandeur` du LoanRequestSubmitSerializer).
  final _cniCtrl = TextEditingController();
  // §7.2 BUSINESS_RULES_2026 . Désignation optionnelle d'un avaliste senior+BRC.
  // Si renseignés, le backend bascule la voie EligibilityRoute.AVALISTE.
  bool _withAvaliste = false;
  final _avalisteNumeroCtrl = TextEditingController();
  final _avalisteNomCtrl = TextEditingController();
  // §6 / LOT 11 . Voie campagne : si une campagne est sélectionnée, le
  // backend route vers EligibilityRoute.CAMPAGNE et applique les paramètres
  // (taux, recouvrement) de la campagne. Mutuellement exclusif avec
  // [_withAvaliste] côté UI.
  bool _withCampaign = false;
  int? _selectedCampaignId;
  // L4 (refonte crédit) . Voie garantie matérielle : quand le membre n'a ni
  // auto-couverture (épargne) ni avaliste, il peut proposer un bien en garantie.
  // Le backend route vers EligibilityRoute.GARANTIE_MATERIELLE si `garantie_
  // materielle=true` et absence de couverture. Le titre de propriété est uploadé
  // après création via le même mécanisme d'attachment (clé `titre_propriete`).
  // Mutuellement exclusif avec [_withAvaliste] et [_withCampaign] côté UI.
  bool _withGarantieMaterielle = false;
  final _garantieDescCtrl = TextEditingController();
  PickedFile? _titreProprieteFile;
  // CH-9 . Canal de réception choisi par le membre + numéro Mobile Money.
  final _phoneCtrl = TextEditingController();
  // CH-7 . Numéro Mobile Money pour régler les frais d'étude.
  final _feePhoneCtrl = TextEditingController();
  // TODO: REMOVE_FOR_PROD . montant éditable pour tester STK Push à 100 XAF.
  final _feeAmountCtrl = TextEditingController(text: '100');
  LoanReceiveChannel _canal = LoanReceiveChannel.taraMomo;
  LoanRequestSubmission? _submission;

  // CH-5 . Valeurs des champs supplémentaires du FormSchema actif. Le
  // renderer expose des [PickedFile] pour les champs `file` ; le submit
  // les sépare des scalaires pour appeler un upload multipart à part.
  Map<String, Object?> _extraValues = {};
  Map<String, String> _extraErrors = {};

  // Champs "profil emprunteur" rendus EN DUR dans le sheet (en attendant
  // que le seed FormSchema soit poussé sur la prod). Les ids correspondent
  // exactement aux noms des champs définis dans `seed_form_schemas.py` :
  // §7.1 Voie BRC . a la demande de credit on capte 2 flags qui
  // determinent la voie privilegiee (un seul des deux suffit) :
  //   . _cgaBrcMember : membre actuel du CGA BRC (Centre Gestion Agree)
  //     -> upload de la carte/attestation CGA BRC
  //   . _cfpBrcApprenant : ancien apprenant du CFP BRC (Centre Formation
  //     Professionnelle BRC) -> upload attestation de formation
  // Le backend les recoit dans extra_payload :
  //   cga_brc_member / cga_brc_preuve / cfp_brc_apprenant / cfp_brc_preuve
  // et recalcule is_brc_member = (cga_brc_member OR cfp_brc_apprenant)
  // pour evaluer la Voie 1 SENIOR_BRC.
  bool _cgaBrcMember = false;
  PickedFile? _cgaBrcProof;
  bool _cfpBrcApprenant = false;
  PickedFile? _cfpBrcProof;

  // Montant LIBRE (refonte crédit 2026) : plus de plafond côté UI. Le backend
  // arbitre la garantie (épargne classique dispo sans avaliste, sinon avaliste
  // requis) ; l'UI se contente d'un minimum réglementaire (kMinLoanAmount) et,
  // en voie campagne, des bornes montant_min/montant_max de la campagne.
  final _montantCtrl = TextEditingController(text: '200000');
  double _montant = 200000;
  // Ni la durée ni la cadence ne sont choisies par le membre : la PÉRIODE de
  // remboursement est entièrement dérivée du montant emprunté (paliers Art. 7),
  // à cadence mensuelle. Le sélecteur de modalité a été retiré de l'UI.
  _Step _step = _Step.form;
  late final AnimationController _checkCtrl;

  /// Décomposition règlementaire live (taux 10 %, durée par palier, échéancier).
  /// Cadence figée à mensuel : n_échéances = durée_mois (fonction du montant).
  /// On borne au minimum réglementaire pour éviter une décomposition absurde
  /// tant que le membre n'a pas saisi un montant valide (le récap est masqué
  /// sous ce seuil, mais le getter reste appelé par le submit).
  LoanBreakdown get _bd => computeLoanBreakdown(
        _montant < kMinLoanAmount ? kMinLoanAmount.toDouble() : _montant,
        modalite: PaymentModality.mensuel,
      );

  /// Campagne actuellement sélectionnée (voie campagne), retrouvée dans la
  /// liste chargée par le picker. `null` hors voie campagne ou si la liste
  /// n'est pas encore disponible.
  CampaignFlyer? _findSelectedCampaign(List<CampaignFlyer>? campaigns) {
    if (!_withCampaign || _selectedCampaignId == null || campaigns == null) {
      return null;
    }
    for (final c in campaigns) {
      if (c.id == _selectedCampaignId) return c;
    }
    return null;
  }

  /// Erreur de validation du montant (min réglementaire + bornes campagne).
  /// `null` = montant valide. Utilisée à la fois pour l'affichage inline et
  /// pour bloquer le submit.
  String? _amountErrorFor(CampaignFlyer? camp) {
    if (_montant < kMinLoanAmount) {
      return 'Montant minimum : ${XAFFormatter.format(kMinLoanAmount)}.';
    }
    if (camp != null &&
        (_montant < camp.montantMin || _montant > camp.montantMax)) {
      return 'Cette campagne accepte de ${XAFFormatter.format(camp.montantMin)} '
          'à ${XAFFormatter.format(camp.montantMax)}.';
    }
    return null;
  }

  @override
  void initState() {
    super.initState();
    // Montant libre : on part sur une valeur par défaut lisible (200 000) sans
    // la borner au plafond « sans avaliste » (qui n'est plus qu'indicatif).
    _montant = 200000;
    _montantCtrl.text = _montant.round().toString();
    _checkCtrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 700),
    );
    // §6 / LOT 11 . Si la sheet est ouverte depuis une carte campagne sur
    // la Home, on présélectionne la voie campagne avec l'id passé.
    if (widget.prefillCampaignId != null) {
      _withCampaign = true;
      _selectedCampaignId = widget.prefillCampaignId;
    }
    // Présélection de la voie quand on arrive depuis une carte « voie de
    // crédit » de la page crédit. BRC = défaut (aucun toggle à activer).
    switch (widget.initialVoie) {
      case LoanRequestVoie.avaliste:
        _withAvaliste = true;
      case LoanRequestVoie.campaign:
        _withCampaign = true;
      case LoanRequestVoie.garantieMaterielle:
        _withGarantieMaterielle = true;
      case LoanRequestVoie.brc:
      case null:
        break;
    }
  }

  @override
  void dispose() {
    _motifCtrl.dispose();
    _cniCtrl.dispose();
    _montantCtrl.dispose();
    _phoneCtrl.dispose();
    _feePhoneCtrl.dispose();
    _feeAmountCtrl.dispose();
    _avalisteNumeroCtrl.dispose();
    _avalisteNomCtrl.dispose();
    _garantieDescCtrl.dispose();
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
    // L5 identité . Le numéro de CNI du demandeur est requis.
    final cniDemandeur = _cniCtrl.text.trim();
    if (cniDemandeur.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Numéro de CNI requis.')),
      );
      return;
    }
    // Montant libre : valide le minimum réglementaire + les bornes de la
    // campagne sélectionnée le cas échéant (le backend re-vérifie côté serveur).
    final camp = _findSelectedCampaign(
      ref.read(_activeCampaignsForPickerProvider).valueOrNull,
    );
    final amountError = _amountErrorFor(camp);
    if (amountError != null) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(amountError)),
      );
      return;
    }
    // BUSINESS_RULES §7.2 . Si avaliste activé, les 2 champs sont requis.
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
    // §7.1 Voie BRC . si tu coches CGA BRC ou CFP BRC, il faut joindre
    // le justificatif correspondant (sinon snackbar + return).
    if (_cgaBrcMember && _cgaBrcProof == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text(
            'Joins ta carte / attestation CGA BRC (ou decoche).',),
        ),
      );
      return;
    }
    if (_cfpBrcApprenant && _cfpBrcProof == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text(
            'Joins ton attestation de formation CFP BRC (ou decoche).',),
        ),
      );
      return;
    }
    // §6 / LOT 11 . Voie campagne : si activée, exiger un id sélectionné.
    if (_withCampaign && _selectedCampaignId == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(AppL10n.of(context).lreq_campaign_required),
        ),
      );
      return;
    }
    // L4 . Voie garantie matérielle : si activée, une description du bien
    // (min 10 caractères) et le titre de propriété sont requis.
    final garantieDesc = _garantieDescCtrl.text.trim();
    if (_withGarantieMaterielle && garantieDesc.length < 10) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text(
            'Décris le bien proposé en garantie (au moins 10 caractères).',
          ),
        ),
      );
      return;
    }
    if (_withGarantieMaterielle && _titreProprieteFile == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Joins le titre de propriété du bien (ou décoche).'),
        ),
      );
      return;
    }
    // CH-9 . Si canal Tara MoMo/OM, un numéro est requis (validation locale
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
    // CH-5 . Validation locale des champs dynamiques (FormSchema actif).
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
    unawaited(HapticFeedback.mediumImpact());
    setState(() => _step = _Step.loading);
    try {
      // CH-5 . Sépare les fichiers (PickedFile) des scalaires : seuls les
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
      // L5 identité . Numéro de CNI du demandeur (champ top-level du serializer).
      scalarExtras['cni_demandeur'] = cniDemandeur;
      // §7.1 Voie BRC . envoie au backend les 2 flags + les fichiers.
      // Le backend recalcule is_brc_member = OR pour evaluer la Voie 1.
      scalarExtras['cga_brc_member'] = _cgaBrcMember ? 'oui' : 'non';
      scalarExtras['cfp_brc_apprenant'] = _cfpBrcApprenant ? 'oui' : 'non';
      if (_cgaBrcMember && _cgaBrcProof != null) {
        fileEntries.add(MapEntry('cga_brc_preuve', _cgaBrcProof!));
      }
      if (_cfpBrcApprenant && _cfpBrcProof != null) {
        fileEntries.add(MapEntry('cfp_brc_preuve', _cfpBrcProof!));
      }

      // BUSINESS_RULES §7.2 . Injecte les champs avaliste dans le body
      // attendu par LoanRequestSubmitSerializer (clés snake_case backend).
      if (_withAvaliste) {
        scalarExtras['avaliste_numero'] = avalisteNumero;
        scalarExtras['avaliste_nom'] = avalisteNom;
      }
      // §6 / LOT 11 . Voie campagne : le backend route automatiquement
      // sur EligibilityRoute.CAMPAGNE quand `campaign_id` est présent et
      // valide (le serveur vérifie que la campagne est active).
      if (_withCampaign && _selectedCampaignId != null) {
        scalarExtras['campaign_id'] = _selectedCampaignId;
      }
      // L4 . Voie garantie matérielle : le backend route sur
      // EligibilityRoute.GARANTIE_MATERIELLE quand `garantie_materielle=true`
      // et absence d'auto-couverture/avaliste. Le titre de propriété part en
      // pièce jointe après création (même mécanisme que les preuves BRC).
      if (_withGarantieMaterielle) {
        scalarExtras['garantie_materielle'] = true;
        scalarExtras['garantie_description'] = garantieDesc;
        if (_titreProprieteFile != null) {
          fileEntries.add(MapEntry('titre_propriete', _titreProprieteFile!));
        }
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
      // CH-5 . Upload best-effort des pièces jointes. Un échec d'upload ne
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
          // Best-effort . log silencieux côté mobile (pas d'analytics ici).
        }
      }
      if (!mounted) return;
      // CH-7 . Pré-remplit le téléphone côté paiement des frais : si le canal
      // de réception choisi est Tara MoMo, on reprend le numéro saisi ; sinon
      // on laisse vide pour que le membre choisisse.
      if (needsPhone && _feePhoneCtrl.text.isEmpty) {
        _feePhoneCtrl.text = phone;
      }
      setState(() {
        _submission = submission;
        _step = _Step.success;
      });
      unawaited(HapticFeedback.heavyImpact());
      unawaited(_checkCtrl.forward());
    } catch (err) {
      if (!mounted) return;
      setState(() => _step = _Step.form);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(err.toString())),
      );
    }
  }

  /// Ouvre le file picker système (images + PDF), borne à 10 Mo, retourne
  /// un [PickedFile] prêt pour upload multipart. `null` si l'utilisateur
  /// annule, si la taille dépasse, ou si la permission est refusée.
  Future<PickedFile?> _pickFile() async {
    try {
      final res = await FilePicker.pickFiles(
        type: FileType.custom,
        allowedExtensions: const ['jpg', 'jpeg', 'png', 'pdf'],
        withData: false,
      );
      final f = res?.files.single;
      if (f == null || f.path == null) return null;
      const maxBytes = 10 * 1024 * 1024;
      if (f.size > maxBytes) {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Fichier trop volumineux (10 Mo max).')),
          );
        }
        return null;
      }
      return PickedFile(path: f.path!, name: f.name, sizeBytes: f.size);
    } catch (_) {
      return null;
    }
  }

  /// CH-7 . Lance le paiement des frais d'étude via Mobile Money.
  /// Tara détecte automatiquement le réseau (MTN/Orange) via le préfixe du
  /// téléphone . pas besoin de sélecteur opérateur côté UI.
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
    final amount = int.tryParse(_feeAmountCtrl.text.trim());
    if (amount == null || amount < 100) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Montant min : 100 XAF.')),
      );
      return;
    }
    unawaited(HapticFeedback.mediumImpact());
    setState(() => _step = _Step.payLoading);
    try {
      await ref.read(loanRequestsProvider.notifier).payStudyFee(
            phone: phone,
            network: '',
            montant: amount,
          );
      if (!mounted) return;
      setState(() => _step = _Step.paySuccess);
      unawaited(HapticFeedback.heavyImpact());
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
    // Voie campagne : on surveille la liste des campagnes pour retrouver la
    // sélection courante et valider ses bornes montant en direct.
    final campaigns = _withCampaign
        ? ref.watch(_activeCampaignsForPickerProvider).valueOrNull
        : null;
    final selectedCampaign = _findSelectedCampaign(campaigns);
    final amountError = _amountErrorFor(selectedCampaign);
    // Bloque le submit tant que le montant est invalide ou qu'une campagne est
    // exigée mais non sélectionnée.
    final submitBlocked =
        amountError != null || (_withCampaign && _selectedCampaignId == null);
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 18, 20, 24),
      child: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const _Grabber(),
            const SizedBox(height: AppSpacing.xl),
            Text(l.lreq_title, style: AppTypography.headingMedium),
            const SizedBox(height: AppSpacing.s),
            Text(
              l.lreq_intro,
              style: AppTypography.bodySmall.copyWith(
                color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.5),
                height: 1.5,
              ),
            ),

            const SizedBox(height: AppSpacing.xl),

            // --- Montant (saisie libre) ---
            //
            // Refonte crédit 2026 : le montant n'est plus plafonné côté UI. Le
            // membre saisit librement la somme voulue ; c'est le backend qui
            // arbitre la garantie (épargne classique dispo, sinon avaliste).
            Text(l.lreq_amount, style: AppTypography.labelMedium),
            const SizedBox(height: AppSpacing.s),
            TextFormField(
              controller: _montantCtrl,
              keyboardType: TextInputType.number,
              inputFormatters: [FilteringTextInputFormatter.digitsOnly],
              style: AppTypography.headingSmall.copyWith(
                color: PaColors.teal,
                fontFeatures: const [FontFeature.tabularFigures()],
              ),
              decoration: InputDecoration(
                suffixText: 'XAF',
                hintText: '0',
                errorText: amountError,
                contentPadding:
                    const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
              ),
              onChanged: (v) {
                final parsed = int.tryParse(v.trim()) ?? 0;
                setState(() => _montant = parsed.toDouble());
              },
            ),
            const SizedBox(height: 6),
            // Plafond « sans avaliste » désormais purement indicatif.
            Text(
              'Sans avaliste jusqu\'à '
              '${XAFFormatter.format(widget.eligibility.plafondMax)}. '
              'Au-delà, désigne un avaliste.',
              style: AppTypography.bodySmall.copyWith(
                color: Theme.of(context)
                    .colorScheme
                    .onSurface
                    .withValues(alpha: 0.5),
                fontSize: 12,
                height: 1.4,
              ),
            ),

            const SizedBox(height: AppSpacing.l),

            // --- Récap période + montant par échéance (CH-11 source) ---
            //
            // La période de remboursement n'est plus choisie par le membre :
            // elle découle du montant emprunté (paliers Art. 7), en versements
            // mensuels. Le récap ci-dessous l'affiche à titre indicatif.
            //
            // On NE montre PAS de tableau "intérêts par échéance" car les
            // intérêts sont retenus à la source dès le décaissement
            // (mode_retenue_interets = source). Chaque échéance contient
            // UNIQUEMENT du capital. On annonce aussi explicitement le
            // montant net que le membre recevra.
            //
            // Masqué tant que le montant saisi est sous le minimum
            // réglementaire (décomposition non pertinente).
            if (_montant >= kMinLoanAmount) ...[
              _RepaymentRecap(bd: _bd),
              const SizedBox(height: AppSpacing.l),
            ],

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

            // --- L5 identité . Numéro de CNI du demandeur ---
            Text('Numéro de CNI', style: AppTypography.labelMedium),
            const SizedBox(height: AppSpacing.s),
            TextFormField(
              controller: _cniCtrl,
              keyboardType: TextInputType.text,
              textCapitalization: TextCapitalization.characters,
              style: AppTypography.bodyLarge,
              decoration: const InputDecoration(
                hintText: 'Ex : 123456789',
                prefixIcon: Icon(Icons.badge_outlined, size: 20),
                contentPadding:
                    EdgeInsets.symmetric(horizontal: 16, vertical: 14),
              ),
            ),

            const SizedBox(height: AppSpacing.l),

            // §7.1 Voie BRC . 2 questions independantes . cocher l'une OU
            // l'autre OU les deux ouvre la Voie 1 SENIOR_BRC (en plus de
            // l'anciennete >= 12 mois). Sans BRC, le membre tombe en
            // Voie 2 (avaliste) ou Voie 3 (campagne).
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: const Color(0xFFF1F5F9),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: const Color(0xFFCBD5E1)),
              ),
              child: const Row(
                children: [
                  Icon(Icons.workspace_premium_rounded,
                      color: Color(0xFF1E3A8A), size: 18,),
                  SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      'Voie BRC . si tu es membre du CGA BRC ou ancien apprenant CFP BRC, joins ton justificatif pour beneficier de la voie privilegiee.',
                      style: TextStyle(
                        color: Color(0xFF1E3A8A),
                        fontSize: 12.5,
                        height: 1.4,
                      ),
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: AppSpacing.m),

            SwitchListTile.adaptive(
              dense: true,
              contentPadding: EdgeInsets.zero,
              value: _cgaBrcMember,
              onChanged: (v) => setState(() {
                _cgaBrcMember = v;
                if (!v) _cgaBrcProof = null;
              }),
              title: const Text(
                'Es-tu membre du CGA BRC ?',
                style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600),
              ),
              subtitle: const Text(
                'Centre de Gestion Agree . Broad Range Consulting.',
                style: TextStyle(fontSize: 12),
              ),
            ),
            if (_cgaBrcMember) ...[
              const SizedBox(height: AppSpacing.s),
              _ProofPickerTile(
                label: 'Carte / attestation CGA BRC',
                picked: _cgaBrcProof,
                onPick: () async {
                  final f = await _pickFile();
                  if (f != null) setState(() => _cgaBrcProof = f);
                },
                onClear: () => setState(() => _cgaBrcProof = null),
              ),
            ],

            const SizedBox(height: AppSpacing.m),

            SwitchListTile.adaptive(
              dense: true,
              contentPadding: EdgeInsets.zero,
              value: _cfpBrcApprenant,
              onChanged: (v) => setState(() {
                _cfpBrcApprenant = v;
                if (!v) _cfpBrcProof = null;
              }),
              title: const Text(
                'As-tu ete apprenant au CFP BRC ?',
                style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600),
              ),
              subtitle: const Text(
                'Centre de Formation Professionnelle . Broad Range Consulting.',
                style: TextStyle(fontSize: 12),
              ),
            ),
            if (_cfpBrcApprenant) ...[
              const SizedBox(height: AppSpacing.s),
              _ProofPickerTile(
                label: 'Attestation de formation CFP BRC',
                picked: _cfpBrcProof,
                onPick: () async {
                  final f = await _pickFile();
                  if (f != null) setState(() => _cfpBrcProof = f);
                },
                onClear: () => setState(() => _cfpBrcProof = null),
              ),
            ],

            const SizedBox(height: AppSpacing.l),

            // --- BUSINESS_RULES §7.2 . Désignation optionnelle d'un avaliste ---
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
              onChanged: (v) => setState(() {
                _withAvaliste = v;
                // Mutuellement exclusif avec les voies campagne et garantie.
                if (v) {
                  _withCampaign = false;
                  _selectedCampaignId = null;
                  _withGarantieMaterielle = false;
                }
              }),
              title: Text(
                AppL10n.of(context).lreq_avaliste_title,
                style: AppTypography.labelMedium,
              ),
              subtitle: Text(
                AppL10n.of(context).lreq_avaliste_subtitle,
                style: const TextStyle(fontSize: 12),
              ),
            ),
            if (_withAvaliste) ...[
              const SizedBox(height: AppSpacing.s),
              _AvalistePicker(
                onPicked: (c) {
                  _avalisteNumeroCtrl.text = c.numeroMembre;
                  _avalisteNomCtrl.text = c.nom;
                  // Force le redessin pour afficher le candidat sélectionné.
                  setState(() {});
                },
              ),
              if (_avalisteNumeroCtrl.text.isNotEmpty) ...[
                const SizedBox(height: AppSpacing.s),
                Container(
                  padding: const EdgeInsets.all(10),
                  decoration: BoxDecoration(
                    color: PaColors.tealSurface,
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Row(
                    children: [
                      const Icon(Icons.check_circle, color: PaColors.teal, size: 18),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          AppL10n.of(context).lreq_avaliste_picked(
                            _avalisteNomCtrl.text,
                            _avalisteNumeroCtrl.text,
                          ),
                          style: const TextStyle(fontSize: 13, color: PaColors.inkPrimary),
                        ),
                      ),
                      IconButton(
                        icon: const Icon(Icons.close, size: 18),
                        tooltip: AppL10n.of(context).lreq_avaliste_clear,
                        onPressed: () => setState(() {
                          _avalisteNumeroCtrl.clear();
                          _avalisteNomCtrl.clear();
                        }),
                      ),
                    ],
                  ),
                ),
              ],
              const SizedBox(height: AppSpacing.m),
            ] else
              const SizedBox(height: AppSpacing.m),

            // --- §6 / LOT 11 . Postuler à une campagne micro-crédit ---
            //
            // Si activé, le membre choisit dans la liste des campagnes
            // ouvertes (récupérées via /api/v1/loans/campaigns/active/).
            // Le backend routera automatiquement sur EligibilityRoute.CAMPAGNE
            // en fonction du champ `campaign_id` injecté dans le body.
            // Mutuellement exclusif avec le toggle avaliste : sélectionner
            // l'un décoche automatiquement l'autre.
            SwitchListTile.adaptive(
              dense: true,
              contentPadding: EdgeInsets.zero,
              value: _withCampaign,
              onChanged: (v) => setState(() {
                _withCampaign = v;
                if (v) {
                  _withAvaliste = false;
                  _withGarantieMaterielle = false;
                }
                if (!v) _selectedCampaignId = null;
              }),
              title: Text(
                AppL10n.of(context).lreq_campaign_title,
                style: AppTypography.labelMedium,
              ),
              subtitle: Text(
                AppL10n.of(context).lreq_campaign_subtitle,
                style: const TextStyle(fontSize: 12),
              ),
            ),
            if (_withCampaign) ...[
              const SizedBox(height: AppSpacing.s),
              Consumer(
                builder: (context, ref, _) {
                  final async = ref.watch(_activeCampaignsForPickerProvider);
                  return async.when(
                    data: (campaigns) {
                      if (campaigns.isEmpty) {
                        return Container(
                          padding: const EdgeInsets.all(12),
                          decoration: BoxDecoration(
                            color: const Color(0xFFFFF7E6),
                            borderRadius: BorderRadius.circular(10),
                          ),
                          child: Text(
                            AppL10n.of(context).lreq_campaign_none,
                            style: const TextStyle(fontSize: 12),
                          ),
                        );
                      }
                      return DropdownButtonFormField<int>(
                        initialValue: _selectedCampaignId,
                        isExpanded: true,
                        decoration: InputDecoration(
                          hintText: AppL10n.of(context).lreq_campaign_pick,
                          prefixIcon: const Icon(Icons.campaign_outlined, size: 20),
                          contentPadding: const EdgeInsets.symmetric(
                              horizontal: 12, vertical: 12,),
                        ),
                        items: [
                          for (final c in campaigns)
                            DropdownMenuItem<int>(
                              value: c.id,
                              child: Text(
                                '${c.nom} · ${XAFFormatter.formatCompact(c.montantMin)}–${XAFFormatter.formatCompact(c.montantMax)}',
                                overflow: TextOverflow.ellipsis,
                              ),
                            ),
                        ],
                        onChanged: (v) =>
                            setState(() => _selectedCampaignId = v),
                      );
                    },
                    loading: () => const Padding(
                      padding: EdgeInsets.symmetric(vertical: 8),
                      child: LinearProgressIndicator(minHeight: 2),
                    ),
                    error: (e, _) => Text(
                      AppL10n.of(context)
                          .lreq_campaign_error(e.toString()),
                      style: const TextStyle(color: Colors.red, fontSize: 12),
                    ),
                  );
                },
              ),
              const SizedBox(height: AppSpacing.m),
            ],

            // --- L4 . Voie garantie matérielle (bien proposé en garantie) ---
            //
            // Quand le membre n'a ni auto-couverture (épargne suffisante) ni
            // avaliste, il peut proposer un bien matériel en garantie (ex.
            // terrain titré). Le backend route alors sur
            // EligibilityRoute.GARANTIE_MATERIELLE (garantie_materielle=true +
            // absence de couverture). Le titre de propriété est uploadé après
            // création via le même mécanisme d'attachment (clé titre_propriete).
            // Mutuellement exclusif avec les toggles avaliste et campagne.
            SwitchListTile.adaptive(
              dense: true,
              contentPadding: EdgeInsets.zero,
              value: _withGarantieMaterielle,
              onChanged: (v) => setState(() {
                _withGarantieMaterielle = v;
                if (v) {
                  _withAvaliste = false;
                  _withCampaign = false;
                  _selectedCampaignId = null;
                }
              }),
              title: const Text(
                'Garantie matérielle (bien)',
                style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600),
              ),
              subtitle: const Text(
                'Propose un bien en garantie si tu n\'as ni épargne '
                'suffisante ni avaliste.',
                style: TextStyle(fontSize: 12),
              ),
            ),
            if (_withGarantieMaterielle) ...[
              const SizedBox(height: AppSpacing.s),
              TextField(
                controller: _garantieDescCtrl,
                maxLines: 3,
                maxLength: 300,
                style: AppTypography.bodyLarge,
                decoration: const InputDecoration(
                  hintText:
                      'Décris le bien proposé en garantie (ex. terrain titré à …)',
                  contentPadding:
                      EdgeInsets.symmetric(horizontal: 16, vertical: 14),
                ),
              ),
              const SizedBox(height: AppSpacing.s),
              _ProofPickerTile(
                label: 'Titre de propriété',
                picked: _titreProprieteFile,
                onPick: () async {
                  final f = await _pickFile();
                  if (f != null) setState(() => _titreProprieteFile = f);
                },
                onClear: () => setState(() => _titreProprieteFile = null),
              ),
              const SizedBox(height: AppSpacing.m),
            ],

            // --- CH-9 . Canal de réception du décaissement ---
            Text('Comment recevoir l\'argent ?',
                style: AppTypography.labelMedium,),
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
                      size: 18, color: PaColors.warning,),
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

            // CH-5 . Section dynamique : champs supplémentaires configurés
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

            // §6 / LOT 11 . Voie campagne : si toggle active mais aucune
            // campagne selectionnee, on griser le bouton et on affiche
            // un message persistent (anti-frustration : sinon l'utilisateur
            // cliquait + voyait un snackbar de 2s qu'il loupait).
            if (_withCampaign && _selectedCampaignId == null) ...[
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: const Color(0xFFFEF3C7),
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: const Color(0xFFD97706), width: 1),
                ),
                child: Row(
                  children: [
                    const Icon(Icons.info_outline_rounded,
                        size: 18, color: Color(0xFF92400E),),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Text(
                        AppL10n.of(context).lreq_campaign_required,
                        style: const TextStyle(
                          fontSize: 12.5,
                          color: Color(0xFF92400E),
                          height: 1.4,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: AppSpacing.m),
            ],

            PaButton(
              label: l.lreq_submit,
              onPressed: submitBlocked ? null : _submit,
            ),
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
              style: AppTypography.headingSmall,),
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
                    color: PaColors.success, size: 34,),
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

  /// CH-7 . Formulaire de paiement Mobile Money pour les frais d'étude.
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

            // TODO: REMOVE_FOR_PROD . montant éditable mode test.
            const SizedBox(height: AppSpacing.l),
            Text('Montant (XAF) . mode test',
                style: AppTypography.labelMedium,),
            const SizedBox(height: AppSpacing.s),
            TextFormField(
              controller: _feeAmountCtrl,
              keyboardType: TextInputType.number,
              style: AppTypography.bodyLarge,
              decoration: const InputDecoration(
                hintText: '100',
                suffixText: 'XAF',
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
              child: const Row(
                children: [
                  Icon(Icons.info_outline_rounded,
                      size: 18, color: PaColors.teal,),
                  SizedBox(width: 10),
                  Expanded(
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

  /// CH-7 . Confirmation après init Tara du paiement des frais.
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
                color: PaColors.success, size: 38,),
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

/// CH-7 . Carte récapitulative des frais d'étude (montant + notice
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
                  size: 18, color: PaColors.warning,),
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


/// Récap période + montant par échéance . aligné CH-11 (mode source).
///
/// Sous le régime CH-11, les intérêts (10 %) sont **retenus à la source dès
/// le décaissement** (`mode_retenue_interets = source`, cf.
/// `seed_demo_credits.py:252` et `LoanCreate.disburse_loan`). Conséquence
/// directe pour l'UI : chaque échéance contient **uniquement du capital**.
/// On NE doit donc PAS afficher de tableau "intérêts par échéance" /
/// "intérêts totaux à payer en plus" . ce serait factuellement faux.
///
/// Ce widget montre les seules informations encore vraies :
///   • Durée de remboursement (mois)
///   • Nombre + cadence d'échéances
///   • Montant par échéance (capital ÷ nb d'échéances)
///   • Net que le membre recevra (montant − intérêts source) . important
///     pour qu'il ne soit pas surpris au décaissement.
class _RepaymentRecap extends StatelessWidget {
  const _RepaymentRecap({required this.bd});

  final LoanBreakdown bd;

  @override
  Widget build(BuildContext context) {
    final montantNet = bd.montant - bd.interetsTotaux;
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
                'Remboursement',
                style: AppTypography.labelMedium.copyWith(
                  color: PaColors.navy,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          // Règle 2026 « date butoir unique » : pas d'échéancier fractionné.
          // La durée (fonction du montant) fixe une date limite ; le membre
          // rembourse librement d'ici là, en une ou plusieurs fois.
          _row('Délai de remboursement', '${bd.dureeMois} mois'),
          _row(
            'À rembourser (avant la date butoir)',
            XAFFormatter.format(montantNet),
            strong: true,
            accent: true,
          ),
          const Divider(height: 18, color: PaColors.line),
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Padding(
                padding: EdgeInsets.only(top: 1),
                child: Icon(Icons.bolt_rounded, size: 14, color: PaColors.success),
              ),
              const SizedBox(width: 6),
              Expanded(
                child: Text(
                  'Un seul délai, pas d\'échéances imposées : vous remboursez '
                  'librement avant la date butoir (fixée à l\'approbation). '
                  'Vous recevrez ${XAFFormatter.format(montantNet)} net — les '
                  'intérêts (10 %) sont retenus dès le décaissement.',
                  style: const TextStyle(
                    color: PaColors.inkSecondary,
                    fontSize: 12,
                    height: 1.4,
                  ),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _row(String label, String value,
      {bool strong = false, bool accent = false,}) {
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


// CH-9 . Sélecteur de canal de réception (Orange Money / MTN MoMo / espèces).
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
                        size: 20, color: PaColors.teal,),
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

/// Typeahead picker pour la sélection d'un avaliste éligible (§7.2).
/// Recherche debounced 300 ms sur `/members/search-avaliste/?q=…`. Le membre
/// tape un préfixe de numéro ou un fragment de nom et choisit dans la liste .
/// remplace la saisie texte libre du numéro+nom qui était sujette aux fautes.
class _AvalistePicker extends ConsumerStatefulWidget {
  const _AvalistePicker({required this.onPicked});

  final ValueChanged<AvalisteCandidate> onPicked;

  @override
  ConsumerState<_AvalistePicker> createState() => _AvalistePickerState();
}

class _AvalistePickerState extends ConsumerState<_AvalistePicker> {
  final _ctrl = TextEditingController();
  List<AvalisteCandidate> _results = const [];
  bool _loading = false;
  String? _error;
  int _debounceToken = 0;

  Future<void> _search(String q) async {
    final token = ++_debounceToken;
    await Future<void>.delayed(const Duration(milliseconds: 300));
    if (token != _debounceToken) return;
    if (q.trim().length < 2) {
      setState(() {
        _results = const [];
        _error = null;
      });
      return;
    }
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final ds = ref.read(avalisteDataSourceProvider);
      final list = await ds.searchEligible(query: q);
      if (token != _debounceToken) return;
      setState(() {
        _results = list;
        _loading = false;
      });
    } catch (e) {
      if (token != _debounceToken) return;
      setState(() {
        _results = const [];
        _loading = false;
        _error = e.toString().replaceFirst('Exception: ', '');
      });
    }
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        TextField(
          controller: _ctrl,
          onChanged: _search,
          decoration: InputDecoration(
            hintText: AppL10n.of(context).lreq_avaliste_search_hint,
            prefixIcon: const Icon(Icons.search, size: 20),
            suffixIcon: _loading
                ? const Padding(
                    padding: EdgeInsets.all(12),
                    child: SizedBox(
                      width: 16,
                      height: 16,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    ),
                  )
                : null,
            contentPadding:
                const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
          ),
        ),
        if (_error != null) ...[
          const SizedBox(height: 6),
          Text(
            _error!,
            style: const TextStyle(color: Colors.red, fontSize: 12),
          ),
        ],
        if (_results.isNotEmpty) ...[
          const SizedBox(height: 6),
          Container(
            constraints: const BoxConstraints(maxHeight: 220),
            decoration: BoxDecoration(
              color: PaColors.paper,
              border:
                  Border.all(color: PaColors.inkMuted.withValues(alpha: 0.2)),
              borderRadius: BorderRadius.circular(10),
            ),
            child: ListView.separated(
              shrinkWrap: true,
              itemCount: _results.length,
              separatorBuilder: (_, __) =>
                  const Divider(height: 1, color: PaColors.line),
              itemBuilder: (_, i) {
                final c = _results[i];
                // memory avaliste-cap-solde . capacite_caution = solde -
                // cautions engagées. Si 0, on désactive le tap : ce membre
                // est plein, désigner serait refusé par le backend.
                final saturated = c.capaciteCaution <= 0;
                final capacityLabel = c.soldeTotal > 0
                    ? AppL10n.of(context).lreq_avaliste_capacity(
                        XAFFormatter.formatCompact(c.capaciteCaution),
                        c.numeroMembre,
                      )
                    : c.numeroMembre;
                return ListTile(
                  dense: true,
                  enabled: !saturated,
                  leading: Icon(
                    saturated
                        ? Icons.do_not_disturb_on_outlined
                        : Icons.person_outline,
                    color: saturated
                        ? PaColors.inkMuted
                        : PaColors.teal,
                    size: 20,
                  ),
                  title: Text(
                    '${c.prenom} ${c.nom}',
                    style: TextStyle(
                      color: saturated ? PaColors.inkMuted : PaColors.inkPrimary,
                      fontSize: 14,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  subtitle: Text(
                    saturated
                        ? AppL10n.of(context).lreq_avaliste_saturated(
                            XAFFormatter.formatCompact(c.cautionsEngagees),
                          )
                        : capacityLabel,
                    style: TextStyle(
                      color: saturated
                          ? const Color(0xFFB3261E)
                          : PaColors.inkMuted,
                      fontSize: 12,
                    ),
                  ),
                  trailing: saturated
                      ? null
                      : const Icon(Icons.check_rounded,
                          color: PaColors.teal, size: 18,),
                  onTap: saturated
                      ? null
                      : () {
                          widget.onPicked(c);
                          _ctrl.clear();
                          setState(() => _results = const []);
                        },
                );
              },
            ),
          ),
        ],
        if (_ctrl.text.length >= 2 &&
            _results.isEmpty &&
            !_loading &&
            _error == null) ...[
          const SizedBox(height: 6),
          Text(
            AppL10n.of(context).lreq_avaliste_search_empty,
            style: const TextStyle(color: PaColors.inkMuted, fontSize: 12),
          ),
        ],
      ],
    );
  }
}


/// Tuile de sélection de fichier . montre soit un bouton "Joindre", soit
/// le nom du fichier sélectionné avec un bouton croix pour le retirer.
/// Utilisée pour les pièces "Attestation CFP Broad Range" et "Carte CGA".
class _ProofPickerTile extends StatelessWidget {
  const _ProofPickerTile({
    required this.label,
    required this.picked,
    required this.onPick,
    required this.onClear,
  });

  final String label;
  final PickedFile? picked;
  final Future<void> Function() onPick;
  final VoidCallback onClear;

  @override
  Widget build(BuildContext context) {
    if (picked == null) {
      return OutlinedButton.icon(
        onPressed: onPick,
        style: OutlinedButton.styleFrom(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
          side: const BorderSide(color: PaColors.line),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(10),
          ),
          foregroundColor: PaColors.inkPrimary,
        ),
        icon: const Icon(Icons.attach_file_rounded, size: 18),
        label: Text(
          'Joindre . $label',
          style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600),
        ),
      );
    }
    final kb = (picked!.sizeBytes / 1024).toStringAsFixed(0);
    return Container(
      padding: const EdgeInsets.fromLTRB(12, 10, 8, 10),
      decoration: BoxDecoration(
        color: PaColors.tealSurface,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: PaColors.teal.withValues(alpha: 0.25)),
      ),
      child: Row(
        children: [
          const Icon(Icons.check_circle, color: PaColors.teal, size: 18),
          const SizedBox(width: 8),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  picked!.name,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    fontSize: 13,
                    fontWeight: FontWeight.w600,
                    color: PaColors.inkPrimary,
                  ),
                ),
                Text(
                  '$kb Ko · prêt à envoyer',
                  style: const TextStyle(fontSize: 11, color: PaColors.inkMuted),
                ),
              ],
            ),
          ),
          IconButton(
            icon: const Icon(Icons.close, size: 18),
            tooltip: 'Retirer',
            onPressed: onClear,
          ),
        ],
      ),
    );
  }
}
