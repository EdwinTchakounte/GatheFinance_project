import 'package:flutter/foundation.dart';

/// Règles métier de la collecte journalière (Article 4 amendé / LOT 6).
///
/// Ces valeurs sont **alignées par défaut** sur les AppSettings backend :
/// - `collecte.min_per_day` (défaut 1000 XAF)
/// - `collecte.prepay.max_days` (défaut 30 jours)
///
/// Ces constantes servent désormais de **repli** : le formulaire de dépôt lit
/// en priorité `GET /savings/info/` (via `savingsInfoProvider`) pour rester
/// synchronisé avec les seuils admin ; il ne retombe sur ces valeurs que si
/// l'appel échoue ou n'a pas encore abouti.
const int kCollecteMinPerDay = 1000;

/// Plancher de versement minimum accepté par la validation client.
/// **Release** = plancher réglementaire ([kCollecteMinPerDay], 1 000 XAF).
/// **Debug/profile** = 100 XAF pour valider les flows Tara en sandbox
/// (le backend doit alors avoir `PAYMENTS_TEST_ALLOW_ANY_AMOUNT=1`).
const int kTestMinDeposit = kReleaseMode ? kCollecteMinPerDay : 100;

/// Plafond du multi-jours pré-payé (verse N jours à l'avance, max 30).
const int kCollectePrepayMaxDays = 30;

/// Pas du montant de collecte : tout versement doit être un multiple de 50 FCFA
/// (contrainte opérationnelle de la coopérative). Le multi-jours autorise un
/// montant libre tant qu'il respecte ce pas ET le minimum de 1 000/jour.
const int kCollecteAmountStep = 50;
