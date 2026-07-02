/// Règles métier de la collecte journalière (Article 4 amendé / LOT 6).
///
/// Ces valeurs sont **alignées par défaut** sur les AppSettings backend :
/// - `collecte.min_per_day` (défaut 1000 XAF)
/// - `collecte.prepay.max_days` (défaut 30 jours)
///
/// Si l'admin modifie ces seuils côté backend, le mobile continue d'envoyer
/// la valeur par défaut. La validation backend renverra alors une 400 avec
/// un message explicite. On pourra ensuite fetcher `/savings/info/` pour
/// synchroniser, mais ce n'est pas indispensable au MVP multi-jours.
const int kCollecteMinPerDay = 1000;

/// TODO: REMOVE_FOR_PROD — plancher de VALIDATION en mode test.
/// Abaisse le minimum accepté à 100 XAF pour les DEUX types de versement
/// (épargne classique + collecte journalière) afin de valider les flows Tara
/// avec de petits montants. À remettre à [kCollecteMinPerDay] (1000) avant la
/// vraie mise en prod. Le backend doit avoir PAYMENTS_TEST_ALLOW_ANY_AMOUNT=1
/// pour accepter ces montants côté serveur.
const int kTestMinDeposit = 100;

/// Plafond du multi-jours pré-payé (verse N jours à l'avance, max 30).
const int kCollectePrepayMaxDays = 30;

/// Pas du montant de collecte : tout versement doit être un multiple de 50 FCFA
/// (contrainte opérationnelle de la coopérative). Le multi-jours autorise un
/// montant libre tant qu'il respecte ce pas ET le minimum de 1 000/jour.
const int kCollecteAmountStep = 50;
