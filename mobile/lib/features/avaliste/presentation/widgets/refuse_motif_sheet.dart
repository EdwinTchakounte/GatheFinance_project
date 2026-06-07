import 'package:flutter/material.dart';

import '../../../../app/theme/paysika/pa_colors.dart';
import '../../../../app/theme/paysika/pa_typography.dart';
import '../../../../core/widgets/paysika/pa_button.dart';

/// Bottom sheet pour saisir un motif de refus de mandat d'avaliste.
/// Renvoie le motif (peut être vide) si l'utilisateur valide, `null` s'il
/// annule.
Future<String?> showRefuseMotifSheet(BuildContext context) {
  return showModalBottomSheet<String?>(
    context: context,
    isScrollControlled: true,
    backgroundColor: Colors.transparent,
    builder: (_) => const _RefuseMotifSheet(),
  );
}

class _RefuseMotifSheet extends StatefulWidget {
  const _RefuseMotifSheet();

  @override
  State<_RefuseMotifSheet> createState() => _RefuseMotifSheetState();
}

class _RefuseMotifSheetState extends State<_RefuseMotifSheet> {
  final _ctl = TextEditingController();
  bool _submitting = false;

  @override
  void dispose() {
    _ctl.dispose();
    super.dispose();
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
              Text('REFUSER LE MANDAT', style: PaText.eyebrow()),
              const SizedBox(height: 6),
              Text(
                'Pourquoi refuses-tu ?',
                style: PaText.heading(size: 22),
              ),
              const SizedBox(height: 8),
              Text(
                'Le demandeur recevra ton motif. Sois bienveillant — '
                'il peut chercher un autre garant. (optionnel)',
                style: PaText.body(),
              ),
              const SizedBox(height: 16),
              TextField(
                controller: _ctl,
                maxLength: 240,
                maxLines: 4,
                decoration: const InputDecoration(
                  border: OutlineInputBorder(),
                  hintText:
                      'Ex : Je n\'ai pas la capacité de garantir ce montant.',
                ),
              ),
              const SizedBox(height: 12),
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
                      label: 'Refuser',
                      loading: _submitting,
                      onPressed: _submitting
                          ? null
                          : () {
                              setState(() => _submitting = true);
                              Navigator.of(context).pop(_ctl.text.trim());
                            },
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
