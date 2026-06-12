import 'package:flutter/foundation.dart';

import 'loan_request.dart';

/// CH-7 — Frais d'étude renvoyés par le backend à la création d'une demande.
///
/// Le membre doit régler ces frais via `POST /payments/init/`
/// (`type=frais_demande_credit`) pour que la demande passe de `en_attente`
/// à `en_instruction`. Le montant est piloté admin (FeeType DEMANDE_CREDIT).
/// Ces frais sont **non-remboursables**, y compris en cas de refus.
@immutable
class LoanRequestStudyFee {
  const LoanRequestStudyFee({
    required this.montant,
    required this.libelle,
    required this.notice,
    required this.nonRemboursable,
  });

  /// Montant en XAF.
  final num montant;

  /// Libellé court ("Frais d'étude du dossier").
  final String libelle;

  /// Mention longue non-remboursable (texte serveur, configurable AppSetting
  /// `loans.study_fee.non_refundable_notice`).
  final String notice;

  /// Toujours `true` actuellement — gardé en champ pour future flexibilité
  /// si l'admin doit pouvoir débrayer la mention pour certaines campagnes.
  final bool nonRemboursable;
}

/// CH-7 — Résultat composite de la soumission d'une demande de crédit :
/// la LoanRequest créée + les frais d'étude à régler ensuite.
///
/// [studyFee] peut être null si le backend a déjà encaissé les frais via
/// un autre canal (ex. mode test auto-validate), ou pour les anciennes
/// versions de l'API qui ne renvoient pas le bloc `frais_a_payer`.
@immutable
class LoanRequestSubmission {
  const LoanRequestSubmission({
    required this.request,
    this.studyFee,
  });

  final LoanRequestEntity request;
  final LoanRequestStudyFee? studyFee;
}
