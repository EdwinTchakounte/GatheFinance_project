import 'dart:async';
import 'dart:io';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../app/theme/app_radii.dart';
import '../../../../app/theme/paysika/pa_colors.dart';
import '../../../../app/theme/paysika/pa_typography.dart';
import '../../../../core/di/providers.dart';
import '../../../../core/widgets/brand_loader.dart';
import '../../../../core/widgets/paysika/pa_brand_hero.dart';
import '../../../../l10n/gen/app_localizations.dart';
import '../../../forms/domain/form_validation.dart';
import '../../../forms/presentation/widgets/dynamic_fields.dart';

/// Champs hardcoded dans ce sheet . exclus du renderer DynamicFields pour
/// éviter les doublons. Doit refléter `_MEMBERSHIP_HARDCODED` dans
/// `apps_coop/members/serializers.py`.
const Set<String> _hardcodedAdhesionFields = {
  'name', 'email', 'phone', 'whatsapp', 'city',
  'quartier_localite', 'statut_pro', 'urgence_nom',
  'urgence_lien', 'urgence_phone', 'message', 'language',
  'cni_recto', 'cni_verso', 'plan_localisation', 'photo_identite',
};

/// Taille max d'une pièce uploadée . alignée sur le serializer backend
/// (`_MAX_PIECE_SIZE` dans `apps_coop/members/serializers.py`).
const int _kMaxPieceBytes = 5 * 1024 * 1024;

/// Extensions acceptées pour les pièces "document" (CNI + plan). On reste
/// volontairement permissif (image + PDF) car les utilisateurs photographient
/// souvent la pièce avec le smartphone.
const List<String> _kDocExts = ['jpg', 'jpeg', 'png', 'pdf', 'heic'];

/// Une seule pièce uploadée . sert au `_FilePickerTile` pour les 4 champs.
class _Piece {
  const _Piece({required this.file, required this.name, required this.size});
  final File file;
  final String name;
  final int size;
}

enum _Step { form, loading, success }

/// Statut professionnel . aligné sur `MembershipRequest.StatutPro` backend.
enum _StatutPro { salarie, commercant, artisan, sansEmploi, autre }

/// Formulaire d'adhésion . recueille les 8 informations de l'Article 2 du
/// Règlement Intérieur pour soumettre une `MembershipRequest`.
///
/// Identité (nom complet, email), téléphone + WhatsApp, ville + lieu précis,
/// statut pro, contact d'urgence (nom + lien + téléphone), motivation.
/// Pièces (CNI, plan de localisation) remises à l'entretien (Art. 3).
///
/// Mock-only : flow visuel complet, persistance branchée plus tard via
/// `SubmitMembershipRequest`.
class MembershipFormSheet extends ConsumerStatefulWidget {
  const MembershipFormSheet({super.key});

  static Future<void> show(BuildContext context) {
    return showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      constraints: BoxConstraints(
        maxHeight: MediaQuery.sizeOf(context).height * 0.9,
      ),
      backgroundColor: PaColors.canvas,
      barrierColor: PaColors.navyDeep.withValues(alpha: 0.55),
      shape: const RoundedRectangleBorder(borderRadius: AppRadii.sheet),
      builder: (_) => const MembershipFormSheet(),
    );
  }

  @override
  ConsumerState<MembershipFormSheet> createState() => _MembershipFormSheetState();
}

class _MembershipFormSheetState extends ConsumerState<MembershipFormSheet>
    with TickerProviderStateMixin {
  // CH-5 . Valeurs des champs dynamiques (FormSchema adhesion).
  Map<String, Object?> _extraValues = {};
  Map<String, String> _extraErrors = {};
  String? _submitError;
  final _formKey = GlobalKey<FormState>();

  final _prenomCtrl = TextEditingController();
  final _nomCtrl = TextEditingController();
  final _emailCtrl = TextEditingController();
  final _phoneCtrl = TextEditingController();
  final _whatsappCtrl = TextEditingController();
  final _cityCtrl = TextEditingController();
  final _quartierCtrl = TextEditingController();
  final _urgenceNomCtrl = TextEditingController();
  final _urgenceLienCtrl = TextEditingController();
  final _urgencePhoneCtrl = TextEditingController();
  final _motivationCtrl = TextEditingController();
  _StatutPro? _statutPro;

  // Pièces obligatoires uploadées par le demandeur. `null` tant que pas
  // choisies. Validées au moment du `_submit` (taille + présence).
  _Piece? _cniRecto;
  _Piece? _cniVerso;
  _Piece? _planLocalisation;
  _Piece? _photoIdentite;
  String? _piecesError;

  _Step _step = _Step.form;
  late final AnimationController _checkCtrl;

  @override
  void initState() {
    super.initState();
    _checkCtrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 700),
    );
  }

  @override
  void dispose() {
    for (final c in [
      _prenomCtrl,
      _nomCtrl,
      _emailCtrl,
      _phoneCtrl,
      _whatsappCtrl,
      _cityCtrl,
      _quartierCtrl,
      _urgenceNomCtrl,
      _urgenceLienCtrl,
      _urgencePhoneCtrl,
      _motivationCtrl,
    ]) {
      c.dispose();
    }
    _checkCtrl.dispose();
    super.dispose();
  }

  String _statutProValue() {
    switch (_statutPro) {
      case _StatutPro.salarie:
        return 'salarie';
      case _StatutPro.commercant:
        return 'commercant';
      case _StatutPro.artisan:
        return 'artisan';
      case _StatutPro.sansEmploi:
        return 'sans_emploi';
      case _StatutPro.autre:
        return 'autre';
      case null:
        return '';
    }
  }

  Future<void> _pickPiece({
    required bool imageOnly,
    required ValueChanged<_Piece> onPicked,
  }) async {
    try {
      final res = await FilePicker.pickFiles(
        type: imageOnly ? FileType.image : FileType.custom,
        allowedExtensions: imageOnly ? null : _kDocExts,
        allowMultiple: false,
        withData: false,
      );
      if (res == null || res.files.isEmpty) return;
      final f = res.files.single;
      final path = f.path;
      if (path == null) return;
      final size = f.size;
      if (size > _kMaxPieceBytes) {
        if (!mounted) return;
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(AppL10n.of(context).mf_piece_too_large)),
        );
        return;
      }
      onPicked(_Piece(file: File(path), name: f.name, size: size));
    } on PlatformException {
      // Permission refusée ou picker indisponible . silencieux.
    }
  }

  bool get _allPiecesPicked =>
      _cniRecto != null &&
      _cniVerso != null &&
      _planLocalisation != null &&
      _photoIdentite != null;

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    // Pièces obligatoires : ne tentons pas le réseau si l'une manque.
    if (!_allPiecesPicked) {
      setState(() => _piecesError = AppL10n.of(context).mf_pieces_required);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(AppL10n.of(context).mf_pieces_required)),
      );
      return;
    }
    setState(() => _piecesError = null);
    // CH-5 . Validation locale des champs dynamiques avant l'envoi.
    final schema = ref.read(activeAdhesionSchemaProvider).valueOrNull;
    if (schema != null) {
      final errs = validateSchema(
        schema,
        _extraValues,
        excludeIds: _hardcodedAdhesionFields,
      );
      if (errs.isNotEmpty) {
        setState(() => _extraErrors = errs);
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Certains champs supplémentaires sont à compléter.'),
          ),
        );
        return;
      }
      setState(() => _extraErrors = const {});
    }
    FocusScope.of(context).unfocus();
    unawaited(HapticFeedback.mediumImpact());
    setState(() {
      _step = _Step.loading;
      _submitError = null;
    });
    try {
      // 1. Captcha auto-résolu (challenge math signé côté backend).
      final ds = ref.read(membershipDataSourceProvider);
      final challenge = await ds.getCaptcha();
      final answer = challenge.solve();
      if (answer == null || challenge.token.isEmpty) {
        throw 'Captcha indisponible . réessaie dans un instant.';
      }
      // 2. Construit le body backend depuis les hardcoded + extras (scalaires).
      //    On passe par une Map<String,Object?> ; le datasource convertit en
      //    FormData multipart (pièces + champs texte) en gardant les fichiers.
      final scalarExtras = <String, Object?>{};
      for (final entry in _extraValues.entries) {
        final v = entry.value;
        // Le sheet adhésion ne porte pas (encore) d'upload via FormSchema.
        if (v is PickedFile) continue;
        if (v != null && v != '') scalarExtras[entry.key] = v;
      }
      final body = <String, Object?>{
        'name': '${_prenomCtrl.text.trim()} ${_nomCtrl.text.trim()}'.trim(),
        'email': _emailCtrl.text.trim().toLowerCase(),
        'phone': _phoneCtrl.text.trim(),
        'whatsapp': _whatsappCtrl.text.trim(),
        'city': _cityCtrl.text.trim(),
        'quartier_localite': _quartierCtrl.text.trim(),
        'statut_pro': _statutProValue(),
        'urgence_nom': _urgenceNomCtrl.text.trim(),
        'urgence_lien': _urgenceLienCtrl.text.trim(),
        'urgence_phone': _urgencePhoneCtrl.text.trim(),
        'message': _motivationCtrl.text.trim(),
        'language': 'fr',
        'captcha_token': challenge.token,
        'captcha_answer': answer.toString(),
        // Pièces (FileFields backend) . déjà validées non-null en amont.
        'cni_recto': _cniRecto!.file,
        'cni_verso': _cniVerso!.file,
        'plan_localisation': _planLocalisation!.file,
        'photo_identite': _photoIdentite!.file,
        ...scalarExtras,
      };
      final err = await ds.submit(body: body);
      if (!mounted) return;
      if (err != null) {
        setState(() {
          _step = _Step.form;
          _submitError = err;
        });
        return;
      }
      setState(() => _step = _Step.success);
      unawaited(HapticFeedback.heavyImpact());
      unawaited(_checkCtrl.forward());
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _step = _Step.form;
        _submitError = e is String ? e : 'Soumission échouée : $e';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedSize(
      duration: const Duration(milliseconds: 280),
      curve: Curves.easeOutCubic,
      alignment: Alignment.topCenter,
      child: Padding(
        padding: EdgeInsets.only(bottom: MediaQuery.viewInsetsOf(context).bottom),
        child: ConstrainedBox(
          constraints: BoxConstraints(
            maxHeight: MediaQuery.sizeOf(context).height * 0.92,
          ),
          child: SafeArea(
            top: false,
            child: switch (_step) {
              _Step.form => _formStep(),
              _Step.loading => _loadingStep(),
              _Step.success => _successStep(),
            },
          ),
        ),
      ),
    );
  }

  // ── Étape formulaire ────────────────────────────────────────────────────
  Widget _formStep() {
    final l = AppL10n.of(context);
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        // Grabber discret tout en haut
        const SizedBox(height: 6),
        const _Grabber(),
        const SizedBox(height: 6),
        // Hero aurore + logo pont (transition vers cream)
        Stack(
          clipBehavior: Clip.none,
          alignment: Alignment.bottomCenter,
          children: [
            PaBrandHero(
              bottomRadius: 26,
              contentPadding: const EdgeInsets.fromLTRB(20, 12, 20, 48),
              child: Center(
                child: Text(
                  l.mf_title,
                  textAlign: TextAlign.center,
                  style: PaText.display(
                    size: 19,
                    weight: FontWeight.w700,
                    color: Colors.white,
                    letterSpacing: -0.3,
                  ),
                ),
              ),
            ),
            const Positioned(
              bottom: -32,
              child: PaBrandHeroBridgeLogo(size: 64),
            ),
          ],
        ),
        const SizedBox(height: 44),
        Padding(
          padding: const EdgeInsets.fromLTRB(22, 0, 22, 6),
          child: Text(
            l.mf_intro,
            textAlign: TextAlign.center,
            style: PaText.body(
              size: 13,
              color: PaColors.inkSecondary,
              height: 1.5,
            ),
          ),
        ),
        Flexible(
          child: Form(
            key: _formKey,
            child: ListView(
              padding: const EdgeInsets.fromLTRB(20, 16, 20, 16),
              children: [
                _section(l.mf_section_identity),
                Row(
                  children: [
                    Expanded(child: _field(_prenomCtrl, l.common_firstname, required: true)),
                    const SizedBox(width: 10),
                    Expanded(child: _field(_nomCtrl, 'Nom', required: true)),
                  ],
                ),
                _field(_emailCtrl, l.common_email,
                    required: true,
                    keyboard: TextInputType.emailAddress,
                    validator: _emailValidator,),

                _section(l.mf_section_contact),
                _field(_phoneCtrl, l.common_phone,
                    required: true, keyboard: TextInputType.phone, prefix: '+237 ',),
                _field(_whatsappCtrl, l.mf_whatsapp,
                    keyboard: TextInputType.phone, prefix: '+237 ',),

                _section(l.mf_section_location),
                _field(_cityCtrl, l.mf_city, required: true),
                _field(_quartierCtrl, l.mf_quartier, required: true),

                _section(l.mf_section_statut),
                _statutProField(),

                _section(l.mf_section_urgence),
                _field(_urgenceNomCtrl, l.mf_urgence_nom, required: true),
                Row(
                  children: [
                    Expanded(
                        child: _field(_urgenceLienCtrl, l.mf_urgence_lien,
                            required: true,),),
                    const SizedBox(width: 10),
                    Expanded(
                        child: _field(_urgencePhoneCtrl, l.common_phone,
                            required: true, keyboard: TextInputType.phone,),),
                  ],
                ),

                _section(l.mf_section_motivation),
                _field(_motivationCtrl, l.mf_motivation_q,
                    maxLines: 3,),

                _section(l.mf_section_pieces),
                Padding(
                  padding: const EdgeInsets.only(bottom: 8),
                  child: Text(
                    l.mf_pieces_intro,
                    style: const TextStyle(
                      color: PaColors.inkMuted,
                      fontSize: 12.5,
                      height: 1.45,
                    ),
                  ),
                ),
                _FilePickerTile(
                  label: l.mf_piece_cni_recto,
                  piece: _cniRecto,
                  icon: Icons.badge_outlined,
                  onPick: () => _pickPiece(
                    imageOnly: false,
                    onPicked: (p) => setState(() {
                      _cniRecto = p;
                      _piecesError = null;
                    }),
                  ),
                  onClear: () => setState(() => _cniRecto = null),
                ),
                _FilePickerTile(
                  label: l.mf_piece_cni_verso,
                  piece: _cniVerso,
                  icon: Icons.badge_outlined,
                  onPick: () => _pickPiece(
                    imageOnly: false,
                    onPicked: (p) => setState(() {
                      _cniVerso = p;
                      _piecesError = null;
                    }),
                  ),
                  onClear: () => setState(() => _cniVerso = null),
                ),
                _FilePickerTile(
                  label: l.mf_piece_plan,
                  piece: _planLocalisation,
                  icon: Icons.map_outlined,
                  onPick: () => _pickPiece(
                    imageOnly: false,
                    onPicked: (p) => setState(() {
                      _planLocalisation = p;
                      _piecesError = null;
                    }),
                  ),
                  onClear: () => setState(() => _planLocalisation = null),
                ),
                _FilePickerTile(
                  label: l.mf_piece_photo,
                  piece: _photoIdentite,
                  icon: Icons.face_outlined,
                  onPick: () => _pickPiece(
                    imageOnly: true,
                    onPicked: (p) => setState(() {
                      _photoIdentite = p;
                      _piecesError = null;
                    }),
                  ),
                  onClear: () => setState(() => _photoIdentite = null),
                ),
                if (_piecesError != null) ...[
                  const SizedBox(height: 6),
                  Text(
                    _piecesError!,
                    style: const TextStyle(
                      color: PaColors.danger,
                      fontSize: 12,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ],

                // CH-5 . Champs supplémentaires définis par l'admin via le
                // FormSchema actif (kind=adhesion). En 404 ou erreur transport,
                // on garde le sheet legacy intact.
                Consumer(
                  builder: (context, ref, _) {
                    final schemaAsync =
                        ref.watch(activeAdhesionSchemaProvider);
                    final schema = schemaAsync.valueOrNull;
                    if (schema == null) return const SizedBox.shrink();
                    return Padding(
                      padding: const EdgeInsets.only(top: 18),
                      child: DynamicFields(
                        schema: schema,
                        values: _extraValues,
                        onChange: (v) => setState(() => _extraValues = v),
                        excludeIds: _hardcodedAdhesionFields,
                        errors: _extraErrors,
                      ),
                    );
                  },
                ),

                if (_submitError != null) ...[
                  const SizedBox(height: 14),
                  Container(
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: PaColors.danger.withValues(alpha: 0.08),
                      borderRadius: BorderRadius.circular(10),
                      border: Border.all(
                        color: PaColors.danger.withValues(alpha: 0.3),
                      ),
                    ),
                    child: Text(
                      _submitError!,
                      style: const TextStyle(
                        color: PaColors.danger,
                        fontSize: 13,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ),
                ],

                const SizedBox(height: 14),
                _feesNote(),
                const SizedBox(height: 18),
                _PrimaryButton(label: l.mf_submit, onTap: _submit),
              ],
            ),
          ),
        ),
      ],
    );
  }

  Widget _section(String title) => Padding(
        padding: const EdgeInsets.only(top: 18, bottom: 8),
        child: Text(
          title.toUpperCase(),
          style: const TextStyle(
            color: PaColors.inkMuted,
            fontSize: 11,
            fontWeight: FontWeight.w700,
            letterSpacing: 1.4,
          ),
        ),
      );

  Widget _field(
    TextEditingController ctrl,
    String label, {
    bool required = false,
    int maxLines = 1,
    TextInputType? keyboard,
    String? prefix,
    String? Function(String?)? validator,
  }) {
    final l = AppL10n.of(context);
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: TextFormField(
        controller: ctrl,
        keyboardType: keyboard,
        maxLines: maxLines,
        style: const TextStyle(color: PaColors.inkPrimary, fontSize: 15),
        decoration: InputDecoration(
          labelText: label,
          labelStyle: const TextStyle(color: PaColors.inkMuted, fontSize: 14),
          prefixText: prefix,
          prefixStyle: const TextStyle(
            color: PaColors.inkSecondary,
            fontWeight: FontWeight.w600,
          ),
          filled: true,
          fillColor: PaColors.cardBg,
          contentPadding:
              const EdgeInsets.symmetric(horizontal: 14, vertical: 14),
          border: OutlineInputBorder(
            borderRadius: BorderRadius.circular(12),
            borderSide: BorderSide.none,
          ),
          enabledBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(12),
            borderSide: BorderSide.none,
          ),
          focusedBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(12),
            borderSide: const BorderSide(color: PaColors.teal, width: 1.5),
          ),
        ),
        validator: validator ??
            (required
                ? (v) => (v == null || v.trim().isEmpty) ? l.common_required : null
                : null),
      ),
    );
  }

  Widget _statutProField() {
    final l = AppL10n.of(context);
    String statutLabel(_StatutPro s) => switch (s) {
          _StatutPro.salarie => l.mf_statut_salarie,
          _StatutPro.commercant => l.mf_statut_commercant,
          _StatutPro.artisan => l.mf_statut_artisan,
          _StatutPro.sansEmploi => l.mf_statut_sansemploi,
          _StatutPro.autre => l.mf_statut_autre,
        };
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: DropdownButtonFormField<_StatutPro>(
        initialValue: _statutPro,
        isExpanded: true,
        decoration: InputDecoration(
          labelText: l.mf_statut,
          labelStyle: const TextStyle(color: PaColors.inkMuted, fontSize: 14),
          filled: true,
          fillColor: PaColors.cardBg,
          contentPadding:
              const EdgeInsets.symmetric(horizontal: 14, vertical: 14),
          border: OutlineInputBorder(
            borderRadius: BorderRadius.circular(12),
            borderSide: BorderSide.none,
          ),
          enabledBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(12),
            borderSide: BorderSide.none,
          ),
          focusedBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(12),
            borderSide: const BorderSide(color: PaColors.teal, width: 1.5),
          ),
        ),
        items: [
          for (final s in _StatutPro.values)
            DropdownMenuItem(value: s, child: Text(statutLabel(s))),
        ],
        onChanged: (v) => setState(() => _statutPro = v),
        validator: (v) => v == null ? l.common_required : null,
      ),
    );
  }

  Widget _feesNote() {
    final l = AppL10n.of(context);
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: PaColors.tealSurface,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Icon(Icons.info_outline, color: PaColors.teal, size: 18),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              l.mf_fees_note,
              style: const TextStyle(
                color: PaColors.inkSecondary,
                fontSize: 12.5,
                height: 1.45,
              ),
            ),
          ),
        ],
      ),
    );
  }

  String? _emailValidator(String? v) {
    final l = AppL10n.of(context);
    final t = (v ?? '').trim();
    if (t.isEmpty) return l.common_required;
    if (!RegExp(r'^[^\s@]+@[^\s@]+\.[^\s@]+$').hasMatch(t)) {
      return l.mf_email_invalid;
    }
    return null;
  }

  // ── Étape loading ────────────────────────────────────────────────────────
  Widget _loadingStep() {
    final l = AppL10n.of(context);
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 10, 20, 40),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const _Grabber(),
          const SizedBox(height: 36),
          const BrandLoader(size: BrandLoaderSize.large),
          const SizedBox(height: 26),
          Text(
            l.mf_sending,
            style: const TextStyle(
              color: PaColors.inkPrimary,
              fontSize: 17,
              fontWeight: FontWeight.w700,
            ),
          ),
        ],
      ),
    );
  }

  // ── Étape succès ───────────────────────────────────────────────────────
  Widget _successStep() {
    final l = AppL10n.of(context);
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 10, 20, 30),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const _Grabber(),
          const SizedBox(height: 28),
          ScaleTransition(
            scale: CurvedAnimation(parent: _checkCtrl, curve: Curves.elasticOut),
            child: Container(
              width: 76,
              height: 76,
              decoration: const BoxDecoration(
                color: PaColors.successSurface,
                shape: BoxShape.circle,
              ),
              alignment: Alignment.center,
              child: const Icon(Icons.check_rounded,
                  color: PaColors.success, size: 40,),
            ),
          ),
          const SizedBox(height: 20),
          Text(
            l.mf_sent_title,
            style: const TextStyle(
              color: PaColors.inkPrimary,
              fontSize: 21,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 6),
          Text(
            l.mf_sent_body,
            textAlign: TextAlign.center,
            style: const TextStyle(color: PaColors.inkMuted, fontSize: 14, height: 1.5),
          ),
          const SizedBox(height: 24),
          _PrimaryButton(
            label: l.common_done,
            onTap: () => Navigator.of(context).pop(),
          ),
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
        width: 40,
        height: 4,
        decoration: BoxDecoration(
          color: PaColors.line,
          borderRadius: BorderRadius.circular(2),
        ),
      ),
    );
  }
}


class _FilePickerTile extends StatelessWidget {
  const _FilePickerTile({
    required this.label,
    required this.piece,
    required this.icon,
    required this.onPick,
    required this.onClear,
  });

  final String label;
  final _Piece? piece;
  final IconData icon;
  final VoidCallback onPick;
  final VoidCallback onClear;

  String _formatSize(int bytes) {
    if (bytes < 1024) return '$bytes o';
    if (bytes < 1024 * 1024) return '${(bytes / 1024).toStringAsFixed(0)} ko';
    return '${(bytes / 1024 / 1024).toStringAsFixed(1)} Mo';
  }

  @override
  Widget build(BuildContext context) {
    final filled = piece != null;
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          borderRadius: BorderRadius.circular(12),
          onTap: filled ? null : onPick,
          child: Container(
            padding:
                const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
            decoration: BoxDecoration(
              color: filled
                  ? PaColors.successSurface.withValues(alpha: 0.55)
                  : PaColors.cardBg,
              borderRadius: BorderRadius.circular(12),
              border: Border.all(
                color: filled
                    ? PaColors.success.withValues(alpha: 0.6)
                    : PaColors.line,
                width: filled ? 1.2 : 1,
              ),
            ),
            child: Row(
              children: [
                Container(
                  width: 38,
                  height: 38,
                  decoration: BoxDecoration(
                    color: filled ? PaColors.success : PaColors.tealSurface,
                    borderRadius: BorderRadius.circular(10),
                  ),
                  alignment: Alignment.center,
                  child: Icon(
                    filled ? Icons.check_rounded : icon,
                    color: filled ? Colors.white : PaColors.teal,
                    size: 20,
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Text(
                        label,
                        style: const TextStyle(
                          color: PaColors.inkPrimary,
                          fontSize: 14,
                          fontWeight: FontWeight.w600,
                        ),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                      const SizedBox(height: 2),
                      Text(
                        filled
                            ? '${piece!.name} · ${_formatSize(piece!.size)}'
                            : AppL10n.of(context).mf_piece_tap_to_pick,
                        style: TextStyle(
                          color: filled
                              ? PaColors.success
                              : PaColors.inkMuted,
                          fontSize: 12,
                          fontWeight: filled ? FontWeight.w600 : FontWeight.w500,
                        ),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ],
                  ),
                ),
                const SizedBox(width: 6),
                if (filled)
                  IconButton(
                    icon: const Icon(Icons.close_rounded,
                        color: PaColors.inkMuted, size: 20,),
                    onPressed: onClear,
                    tooltip: AppL10n.of(context).mf_piece_remove,
                  )
                else
                  const Icon(Icons.upload_outlined,
                      color: PaColors.teal, size: 20,),
              ],
            ),
          ),
        ),
      ),
    );
  }
}


class _PrimaryButton extends StatelessWidget {
  const _PrimaryButton({required this.label, required this.onTap});
  final String label;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: double.infinity,
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(999),
          child: Container(
            height: 52,
            decoration: BoxDecoration(
              gradient: PaGradients.ctaPill,
              borderRadius: BorderRadius.circular(999),
            ),
            alignment: Alignment.center,
            child: Text(
              label,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(
                color: PaColors.onTeal,
                fontSize: 15,
                fontWeight: FontWeight.w700,
              ),
            ),
          ),
        ),
      ),
    );
  }
}
