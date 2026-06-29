// Portage TypeScript des regles credit du mobile (loan_terms.dart).
// Mobile = source de verite ; toute modif des paliers doit etre faite ici
// ET dans mobile/lib/features/loans/domain/loan_terms.dart en simultane.
//
// Article 7 du Reglement : la duree de remboursement est DERIVEE du montant
// (palier table) ; le membre ne choisit pas. Ca evite les abus genre
// "petit montant sur 36 mois".

export type PaymentModality = "journalier" | "hebdomadaire" | "mensuel";

export const LOAN_INTEREST_RATE = 0.1; // 10 % flat (Article 5)
export const MIN_LOAN_AMOUNT = 5000;

// Tuple : [montant_min, montant_max | null, duree_mois]
const LOAN_DURATION_TIERS: ReadonlyArray<readonly [number, number | null, number]> = [
  [5000, 50000, 2],
  [51000, 200000, 3],
  [201000, 350000, 4],
  [351000, 500000, 5],
  [501000, 650000, 6],
  [651000, 800000, 7],
  [801000, 950000, 8],
  [951000, null, 9],
];

/** Renvoie la duree de remboursement (mois) pour un montant. */
export function durationMonthsFor(montant: number): number {
  for (const [, hi, months] of LOAN_DURATION_TIERS) {
    if (hi === null || montant <= hi) return months;
  }
  const last = LOAN_DURATION_TIERS[LOAN_DURATION_TIERS.length - 1];
  return last ? last[2] : 9;
}

const MODALITY_INSTALLMENTS_PER_MONTH: Record<PaymentModality, number> = {
  journalier: 30,
  hebdomadaire: 4,
  mensuel: 1,
};

export type LoanBreakdown = {
  montant: number;
  dureeMois: number;
  modalite: PaymentModality;
  interetsTotaux: number;
  montantTotalDu: number;
  nbEcheances: number;
  montantParEcheance: number;
};

// === Reconduction (Articles 10/11) =========================================

/** Taux applique sur le capital restant si interets payes au comptant. */
export const RENEWAL_RATE_COMPTANT = 0.1;

/** Taux applique sur le capital restant si interets reportes au mois suivant. */
export const RENEWAL_RATE_REPORTE = 0.15;

/** Mois supplementaires ajoutes a la duree restante (Article 10) = +1 mois fixe. */
export const RENEWAL_EXTRA_MONTHS = 1;

/**
 * Calcule les interets de reconduction (Article 11).
 *
 * Le taux porte UNIQUEMENT sur le capital restant du (pas d'interet sur
 * interet). Le mobile fait pareil via `renewalInterest()`.
 */
export function renewalInterest(
  capitalRestant: number,
  modalite: "comptant" | "reporte",
): number {
  const taux = modalite === "comptant" ? RENEWAL_RATE_COMPTANT : RENEWAL_RATE_REPORTE;
  return Math.round(capitalRestant * taux);
}

/** Calcule le recap d'un credit (flat 10 % + paliers + modalite). */
export function computeLoanBreakdown(
  montant: number,
  modalite: PaymentModality = "mensuel",
): LoanBreakdown {
  const dureeMois = durationMonthsFor(montant);
  const interetsTotaux = Math.round(montant * LOAN_INTEREST_RATE);
  const montantTotalDu = montant + interetsTotaux;
  const nbEcheances = dureeMois * MODALITY_INSTALLMENTS_PER_MONTH[modalite];
  const montantParEcheance = Math.round(montantTotalDu / nbEcheances);
  return {
    montant,
    dureeMois,
    modalite,
    interetsTotaux,
    montantTotalDu,
    nbEcheances,
    montantParEcheance,
  };
}
