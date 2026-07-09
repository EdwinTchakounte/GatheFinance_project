/// Règles métier du crédit — miroir mobile du backend `apps_coop/loans/terms.py`.
///
/// Source de vérité : Règlement Intérieur GATHE Finance 2025.
/// Toute divergence avec le backend est un bug. Permet à l'app de calculer
/// localement (mock + affichage) une durée / un échéancier conformes.
library;

/// Modalité de remboursement (Article 8).
enum PaymentModality { journalier, hebdomadaire, mensuel }

extension PaymentModalityX on PaymentModality {
  String get label => switch (this) {
        PaymentModality.journalier => 'Journalier',
        PaymentModality.hebdomadaire => 'Hebdomadaire',
        PaymentModality.mensuel => 'Mensuel',
      };

  /// Nombre d'échéances par mois pour cette cadence.
  int get installmentsPerMonth => switch (this) {
        PaymentModality.journalier => 30,
        PaymentModality.hebdomadaire => 4,
        PaymentModality.mensuel => 1,
      };
}

/// Taux flat appliqué une fois sur le capital (Article 5) — 10 % par transaction.
const double kLoanInterestRate = 0.10;

/// Montant minimum d'un crédit (premier palier).
const num kMinLoanAmount = 5000;

/// Table des paliers (montant_min, montant_max ou null, durée_mois) — Article 7.
const List<(num, num?, int)> kLoanDurationTiers = [
  (5000, 50000, 2),
  (51000, 200000, 3),
  (201000, 350000, 4),
  (351000, 500000, 5),
  (501000, 650000, 6),
  (651000, 800000, 7),
  (801000, 950000, 8),
  (951000, null, 9),
];

/// Renvoie la durée de remboursement (mois) pour [montant] (Article 7).
///
/// Si [montant] tombe dans un « trou » entre deux paliers (ex. 50 500, entre
/// 5 000–50 000 et 51 000–200 000), on retient le palier SUPÉRIEUR — la durée
/// la plus longue protège l'emprunteur.
int durationMonthsFor(num montant) {
  for (final (_, hi, months) in kLoanDurationTiers) {
    // Dès que le montant est sous (ou dans) le plafond du palier courant, ce
    // palier le couvre — y compris s'il tombe dans un « trou » sous la borne
    // basse, auquel cas le plafond du palier précédent est déjà dépassé et
    // c'est bien le palier supérieur (le courant) qui s'applique.
    if (hi == null || montant <= hi) return months;
  }
  return kLoanDurationTiers.last.$3;
}

/// Nombre total d'échéances pour (durée, modalité).
int installmentCount(int dureeMois, PaymentModality modalite) =>
    dureeMois * modalite.installmentsPerMonth;

/// Décomposition complète d'un crédit selon le règlement.
class LoanBreakdown {
  const LoanBreakdown({
    required this.montant,
    required this.dureeMois,
    required this.modalite,
    required this.interetsTotaux,
    required this.montantTotalDu,
    required this.nbEcheances,
    required this.capitalParEcheance,
    required this.interetsParEcheance,
    required this.montantParEcheance,
  });

  final num montant;
  final int dureeMois;
  final PaymentModality modalite;
  final num interetsTotaux;
  final num montantTotalDu;
  final int nbEcheances;
  final num capitalParEcheance;
  final num interetsParEcheance;
  final num montantParEcheance;
}

/// Calcule la décomposition d'un crédit (flat 10 %, paliers, modalité).
LoanBreakdown computeLoanBreakdown(
  num montant, {
  PaymentModality modalite = PaymentModality.mensuel,
}) {
  final duree = durationMonthsFor(montant);
  final interetsTotaux = (montant * kLoanInterestRate).roundToDouble();
  final montantTotalDu = montant + interetsTotaux;
  final n = installmentCount(duree, modalite);
  final capitalParEch = (montant / n);
  final interetsParEch = (interetsTotaux / n);
  return LoanBreakdown(
    montant: montant,
    dureeMois: duree,
    modalite: modalite,
    interetsTotaux: interetsTotaux,
    montantTotalDu: montantTotalDu,
    nbEcheances: n,
    capitalParEcheance: capitalParEch,
    interetsParEcheance: interetsParEch,
    montantParEcheance: capitalParEch + interetsParEch,
  );
}

/// Taux d'intérêt épargne mensuel (Article 4) — 1 % par mois.
const double kSavingsMonthlyRate = 0.01;

/// Cotisation journalière suggérée (Article 4).
const num kDailyContribution = 1000;

// === Reconduction (Articles 10-11) ========================================

/// Prorogation fixe accordée à la reconduction (Article 10) — +1 mois.
const int kRenewalExtraMonths = 1;

/// Taux de reconduction AVEC versement des intérêts au comptant (Article 11).
const double kRenewalRateComptant = 0.10;

/// Taux de reconduction SANS versement (intérêts reportés, Article 11).
const double kRenewalRateReporte = 0.15;

/// Intérêts de reconduction = taux × capital restant (Article 11).
///
/// Le taux porte UNIQUEMENT sur le capital restant dû : pas d'intérêt sur les
/// intérêts déjà courus (« pas d'intérêt sur intérêt »).
num renewalInterest(num capitalRestant, {required bool comptant}) {
  final taux = comptant ? kRenewalRateComptant : kRenewalRateReporte;
  return (capitalRestant * taux).roundToDouble();
}

// === Pénalité de retard (Article 12) ======================================

/// Taux de pénalité sur versement partiel manqué (Article 12) — 50 %.
const double kLatePenaltyRate = 0.50;

/// Pénalité de retard = 50 % des intérêts dus sur la somme non versée
/// (Article 12). [interetsDus] = part d'intérêts de l'échéance en retard.
num latePenalty(num interetsDus) =>
    (interetsDus * kLatePenaltyRate).roundToDouble();
