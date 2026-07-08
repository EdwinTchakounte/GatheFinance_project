import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';

import '../../../../app/theme/paysika/pa_colors.dart';
import '../../../../app/theme/paysika/pa_typography.dart';
import '../../../../core/widgets/paysika/pa_button.dart';

/// L5 identité . Résultat de la saisie d'acceptation d'un mandat d'avaliste :
/// numéro de CNI + justificatif (chemin + nom du fichier pické).
@immutable
class AcceptCniResult {
  const AcceptCniResult({
    required this.cniNumero,
    required this.filePath,
    required this.fileName,
  });

  final String cniNumero;
  final String filePath;
  final String fileName;
}

/// Bottom sheet pour capter le numéro de CNI de l'avaliste + son justificatif
/// avant d'accepter un mandat. Renvoie un [AcceptCniResult] si l'utilisateur
/// valide (les deux champs sont requis), `null` s'il annule.
Future<AcceptCniResult?> showAcceptCniSheet(BuildContext context) {
  return showModalBottomSheet<AcceptCniResult?>(
    context: context,
    isScrollControlled: true,
    backgroundColor: Colors.transparent,
    builder: (_) => const _AcceptCniSheet(),
  );
}

class _AcceptCniSheet extends StatefulWidget {
  const _AcceptCniSheet();

  @override
  State<_AcceptCniSheet> createState() => _AcceptCniSheetState();
}

class _AcceptCniSheetState extends State<_AcceptCniSheet> {
  final _ctl = TextEditingController();
  String? _filePath;
  String? _fileName;
  bool _submitting = false;

  @override
  void dispose() {
    _ctl.dispose();
    super.dispose();
  }

  bool get _canSubmit =>
      _ctl.text.trim().isNotEmpty && _filePath != null && !_submitting;

  /// Ouvre le file picker système (images + PDF), borne à 10 Mo. Réutilise
  /// le même pattern que le sheet de demande de crédit.
  Future<void> _pickFile() async {
    try {
      final res = await FilePicker.pickFiles(
        type: FileType.custom,
        allowedExtensions: const ['jpg', 'jpeg', 'png', 'pdf'],
        withData: false,
      );
      final f = res?.files.single;
      if (f == null || f.path == null) return;
      const maxBytes = 10 * 1024 * 1024;
      if (f.size > maxBytes) {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Text('Fichier trop volumineux (10 Mo max).'),
            ),
          );
        }
        return;
      }
      setState(() {
        _filePath = f.path;
        _fileName = f.name;
      });
    } catch (_) {
      // Annulation / permission refusée : rien à faire.
    }
  }

  @override
  Widget build(BuildContext context) {
    final viewInsets = MediaQuery.of(context).viewInsets;
    final maxH = MediaQuery.of(context).size.height * 0.9;
    return Padding(
      padding: EdgeInsets.only(bottom: viewInsets.bottom),
      child: Container(
        constraints: BoxConstraints(maxHeight: maxH),
        decoration: const BoxDecoration(
          color: PaColors.paper,
          borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
        ),
        padding: const EdgeInsets.fromLTRB(20, 12, 20, 20),
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Center(
                child: Container(
                  width: 36,
                  height: 4,
                  margin: const EdgeInsets.only(bottom: 16),
                  decoration: BoxDecoration(
                    color: PaColors.inkPrimary.withValues(alpha: 0.18),
                    borderRadius: BorderRadius.circular(2),
                  ),
                ),
              ),
              Text('ACCEPTER LE MANDAT', style: PaText.eyebrow()),
              const SizedBox(height: 6),
              Text(
                'Confirme ton identité',
                style: PaText.heading(size: 22),
              ),
              const SizedBox(height: 8),
              Text(
                'Renseigne ton numéro de CNI et joins une photo / un scan '
                'lisible de ta pièce pour te porter garant.',
                style: PaText.body(),
              ),
              const SizedBox(height: 16),
              Text('Votre numéro de CNI', style: PaText.eyebrow()),
              const SizedBox(height: 6),
              TextField(
                controller: _ctl,
                textCapitalization: TextCapitalization.characters,
                onChanged: (_) => setState(() {}),
                decoration: const InputDecoration(
                  border: OutlineInputBorder(),
                  hintText: 'Ex : 123456789',
                  prefixIcon: Icon(Icons.badge_outlined, size: 20),
                ),
              ),
              const SizedBox(height: 16),
              Text('Justificatif CNI', style: PaText.eyebrow()),
              const SizedBox(height: 6),
              _CniFileTile(
                fileName: _fileName,
                onPick: _pickFile,
                onClear: () => setState(() {
                  _filePath = null;
                  _fileName = null;
                }),
              ),
              const SizedBox(height: 16),
              Row(
                children: [
                  Expanded(
                    child: PaButton(
                      label: 'Annuler',
                      variant: PaButtonVariant.outline,
                      onPressed: _submitting
                          ? null
                          : () => Navigator.of(context).pop(null),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: PaButton(
                      label: 'Accepter',
                      loading: _submitting,
                      onPressed: _canSubmit
                          ? () {
                              setState(() => _submitting = true);
                              Navigator.of(context).pop(
                                AcceptCniResult(
                                  cniNumero: _ctl.text.trim(),
                                  filePath: _filePath!,
                                  fileName: _fileName ?? 'cni',
                                ),
                              );
                            }
                          : null,
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// Tuile de sélection du justificatif CNI . vide (bouton "Joindre") ou
/// remplie (nom du fichier + croix pour retirer).
class _CniFileTile extends StatelessWidget {
  const _CniFileTile({
    required this.fileName,
    required this.onPick,
    required this.onClear,
  });

  final String? fileName;
  final VoidCallback onPick;
  final VoidCallback onClear;

  @override
  Widget build(BuildContext context) {
    if (fileName == null) {
      return OutlinedButton.icon(
        onPressed: onPick,
        icon: const Icon(Icons.attach_file_rounded, size: 18),
        label: const Text('Joindre une photo / un PDF'),
        style: OutlinedButton.styleFrom(
          foregroundColor: PaColors.teal,
          minimumSize: const Size.fromHeight(48),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
          ),
        ),
      );
    }
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(
        color: PaColors.tealSurface,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Row(
        children: [
          const Icon(Icons.check_circle, color: PaColors.teal, size: 18),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              fileName!,
              overflow: TextOverflow.ellipsis,
              style: PaText.body().copyWith(fontSize: 13),
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
