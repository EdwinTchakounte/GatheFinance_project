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

/// Plafond du multi-jours pré-payé (verse N jours à l'avance, max 30).
const int kCollectePrepayMaxDays = 30;
