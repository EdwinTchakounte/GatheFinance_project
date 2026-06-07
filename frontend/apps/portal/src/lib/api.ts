/**
 * Portal API client — calls the Django cooperative API (/api/v1/*).
 *
 *  - All requests go through Next.js rewrites configured in `next.config.mjs`
 *    so the browser sees one origin → session cookies and CSRF behave normally.
 *  - Mutating requests automatically attach the CSRF header read from the
 *    `csrftoken` cookie set by `GET /api/v1/auth/csrf/`.
 *
 * Tactical placement inside apps/site for the MVP. Will move to
 * `apps/portal/src/lib/api.ts` when we extract the portal.
 */

const API_BASE = "/api/v1";

export type ApiError = {
  status: number;
  detail?: string;
  body?: unknown;
};

function readCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.match(new RegExp(`(?:^|;\\s*)${name}=([^;]+)`));
  const value = match?.[1];
  return value ? decodeURIComponent(value) : null;
}

async function readError(response: Response): Promise<ApiError> {
  let body: unknown;
  try {
    body = await response.json();
  } catch {
    body = await response.text().catch(() => "");
  }
  const detail =
    typeof body === "object" && body !== null && "detail" in body
      ? String((body as { detail?: unknown }).detail)
      : undefined;
  return { status: response.status, detail, body };
}

async function request<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const method = (init.method || "GET").toUpperCase();
  const headers = new Headers(init.headers);
  if (!headers.has("Accept")) headers.set("Accept", "application/json");
  if (init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (method !== "GET" && method !== "HEAD") {
    const csrf = readCookie("csrftoken");
    if (csrf) headers.set("X-CSRFToken", csrf);
  }
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    method,
    headers,
    credentials: "include",
  });
  if (!response.ok) {
    throw await readError(response);
  }
  if (response.status === 204) return undefined as unknown as T;
  return (await response.json()) as T;
}

// -- Public surface used by the portal pages ---------------------------------

export type Identity = {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  is_staff: boolean;
  is_superuser: boolean;
  groups: string[];
  member: {
    id: number;
    numero_membre: string;
    nom: string;
    prenom: string;
    statut: "actif" | "suspendu" | "radie";
  } | null;
};

export type SavingsTransaction = {
  id: number;
  type_op: "depot" | "retrait" | "interet";
  type_display: string;
  montant: string;
  solde_apres: string;
  date: string;
};

export type SavingsSnapshot = {
  id: number;
  solde: string;
  date_ouverture: string;
  taux_interet_applique: string;
  transactions_recentes: SavingsTransaction[];
};

export type PaymentRead = {
  id: number;
  montant: string;
  type: string;
  type_display: string;
  source: string;
  statut: "en_attente" | "valide" | "rejete";
  statut_display: string;
  provider_code: string;
  reference_externe: string;
  date_versement: string;
  date_validation: string | null;
  motif_rejet: string;
  created_at: string;
};

export type LoanRequest = {
  id: number;
  montant_demande: string;
  duree_mois: number;
  motif: string;
  statut:
    | "en_attente"
    | "en_instruction"
    | "en_attente_acceptation_membre"
    | "approuvee"
    | "rejetee"
    | "en_attente_avaliste"
    | "rejetee_avaliste"
    | "en_validation_campagne"
    | "rejetee_campagne";
  statut_display: string;
  motif_rejet: string;
  montant_revise: string | null;
  duree_revisee: number | null;
  date_soumission: string;
  date_decision: string | null;
};

// Refonte 2026 LOT 19 — Espace prêteur (épargne-prêteur).
export type LenderConsent = {
  id: number;
  is_global: boolean;
  is_active: boolean;
  convention_signed_at: string;
  revoked_at: string | null;
};

export type LenderTranche = {
  id: number;
  montant: string;
  statut: "disponible" | "engagee" | "liberee" | "annulee";
  statut_display: string;
  engaged_in_loan_id: number | null;
  engaged_at: string | null;
  released_at: string | null;
  created_at: string;
};

export type LenderPendingFunding = {
  id: number;
  statut: string;
  montant_propose: string;
  deadline: string;
  funding_request_id: number;
  wave_number: number;
  loan: {
    id: number;
    numero_dossier: string;
    montant_total: string;
    duree_mois: number;
  };
  borrower: {
    id: number;
    numero_membre: string;
    prenom: string;
    nom: string;
  };
};

export type LenderState = {
  consent: LenderConsent | null;
  tranches: LenderTranche[];
  totals: {
    disponible: string;
    engagee: string;
    liberee: string;
    annulee: string;
  };
  pending_funding_requests: LenderPendingFunding[];
  pending_count: number;
};

// Refonte 2026 LOT 18 — Mandats d'avaliste (côté garant).
export type AvalisteMandat = {
  id: number;
  statut: "pending" | "accepted" | "refused";
  statut_display: string;
  responded_at: string | null;
  refus_motif: string;
  created_at: string;
  demandeur: {
    id: number;
    numero_membre: string;
    prenom: string;
    nom: string;
  };
  loan_request: {
    id: number;
    montant_demande: string;
    duree_mois: number;
    motif: string;
    statut: string;
    date_soumission: string;
  };
  couverture: {
    epargne_borrower: string;
    epargne_avaliste: string;
    ratio: string;
  };
};

export type LoanInstallment = {
  id: number;
  numero_echeance: number;
  date_echeance: string;
  montant_capital: string;
  montant_interets: string;
  montant_total: string;
  montant_paye: string;
  statut: "a_venir" | "payee" | "en_retard" | "partielle";
  statut_display: string;
};

export type Loan = {
  id: number;
  numero_dossier: string;
  montant: string;
  taux_interet: string;
  duree_mois: number;
  date_decaissement: string;
  date_premiere_echeance: string;
  montant_total_du: string;
  solde_restant: string;
  statut: "actif" | "en_retard" | "cloture" | "contentieux";
  statut_display: string;
  installments: LoanInstallment[];
  created_at: string;
};

export type PaymentInitInput = {
  type: "epargne" | "remboursement" | "frais_adhesion" | "frais_inscription" | "frais_demande_credit" | "frais_reconduction" | "frais_carnet";
  montant: number;
  phone: string;
  network: "MTN" | "ORANGE" | "WAVE" | "AIRTEL";
  loan_id?: number | null;
  loan_installment_id?: number | null;
};

export type PaymentInitResponse = {
  payment: PaymentRead;
  paymentUrl: string | null;
  instructions: string;
};

// Refonte 2026 — Retrait avec choix MOMO/présentiel
export type WithdrawalModePaiement = "momo" | "presentiel";
export type WithdrawalNetwork = "MTN" | "ORANGE" | "WAVE" | "AIRTEL";

// Notifications in-app — alimentées par les hooks métier + les annonces broadcast.
export type PortalNotification = {
  id: number;
  type: string;
  message: string;
  lien: string;
  lue: boolean;
  created_at: string;
};

export type WithdrawalRead = {
  id: number;
  montant: string;
  motif: string;
  statut:
    | "en_attente"
    | "approuvee"
    | "en_payout"
    | "completee"
    | "payout_failed"
    | "rejetee";
  statut_display: string;
  mode_paiement: WithdrawalModePaiement;
  mode_paiement_display: string;
  recipient_phone_masked: string;
  network: "" | WithdrawalNetwork;
  motif_rejet: string;
  date_demande: string;
  date_decision: string | null;
  handed_over_at: string | null;
};

export const portalApi = {
  primeCsrf: () => request<{ csrfToken: string }>("/auth/csrf/"),
  login: (email: string, password: string) =>
    request<Identity>("/auth/login/", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  logout: () => request<void>("/auth/logout/", { method: "POST" }),
  me: () => request<Identity>("/auth/me/"),
  savings: () => request<SavingsSnapshot>("/savings/me/"),

  withdrawals: {
    listMine: () =>
      request<{ results: WithdrawalRead[] }>("/savings/withdrawals/me/"),
    create: (payload: {
      montant: number;
      motif?: string;
      mode_paiement: WithdrawalModePaiement;
      recipient_phone?: string;
      network?: WithdrawalNetwork;
    }) =>
      request<WithdrawalRead>("/savings/withdrawal/", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
  },
  // Refonte 2026 LOT 19 — Espace prêteur (épargne-prêteur).
  lender: {
    me: () => request<LenderState>("/savings/me/lender/"),
    optIn: (is_global: boolean) =>
      request<LenderState>("/savings/me/lender/opt-in/", {
        method: "POST",
        body: JSON.stringify({ is_global }),
      }),
    revoke: () =>
      request<LenderState>("/savings/me/lender/revoke/", { method: "POST" }),
    addTranche: (montant: number) =>
      request<LenderTranche>("/savings/me/lender/tranches/", {
        method: "POST",
        body: JSON.stringify({ montant }),
      }),
    cancelTranche: (id: number) =>
      request<LenderTranche>(`/savings/me/lender/tranches/${id}/cancel/`, {
        method: "POST",
      }),
    respondFunding: (
      id: number,
      payload: { accept: boolean; motif?: string },
    ) =>
      request<{
        id: number;
        statut: string;
        responded_at: string | null;
        refus_motif: string;
        message: string;
      }>(`/savings/me/lender/funding-requests/${id}/respond/`, {
        method: "POST",
        body: JSON.stringify(payload),
      }),
  },
  loans: {
    eligibility: () =>
      request<{
        eligible: boolean;
        plafond_max: string;
        motifs_ineligibilite: string[];
        solde_epargne: string;
        ratio_garantie: string;
      }>("/loans/me/eligibility/"),
    listMine: () => request<LoanRequest[]>("/loans/me/requests/"),
    activeMine: () => request<Loan[]>("/loans/me/active/"),
    create: (data: {
      montant_demande: number;
      duree_mois: number;
      motif: string;
      avaliste_numero?: string;
      avaliste_nom?: string;
      campaign_id?: number;
      profil_cible?: string;
    }) =>
      request<{
        loan_request: LoanRequest;
        route: "senior_brc" | "avaliste" | "campaign" | "none";
        route_details: Record<string, unknown>;
        frais_a_payer: { code: string; libelle: string; montant: string };
      }>("/loans/requests/", { method: "POST", body: JSON.stringify(data) }),
    // Refonte 2026 LOT 18 — Mandats d'avaliste (côté garant).
    avalisteMandats: {
      list: (statut?: "pending" | "accepted" | "refused") =>
        request<{
          count: number;
          pending: number;
          results: AvalisteMandat[];
        }>(`/loans/me/avaliste-mandats/${statut ? `?statut=${statut}` : ""}`),
      respond: (id: number, payload: { accept: boolean; motif?: string }) =>
        request<AvalisteMandat>(
          `/loans/me/avaliste-mandats/${id}/respond/`,
          { method: "POST", body: JSON.stringify(payload) },
        ),
    },
    // Reconduction = +1 mois fixe, SANS frais (seul le taux est majoré).
    // Le corps est optionnel : la durée éventuelle est ignorée côté backend.
    requestRenewal: (loanId: number, data: { nouvelle_duree_mois?: number } = {}) =>
      request<{
        renewal: {
          id: number;
          loan_id: number;
          nouvelle_duree_mois: number;
          statut: string;
          date_demande: string;
          frais_reconduction_payment_id: number | null;
        };
      }>(`/loans/${loanId}/renewal/`, {
        method: "POST",
        body: JSON.stringify(data),
      }),
  },
  payments: {
    init: (data: PaymentInitInput) =>
      request<PaymentInitResponse>("/payments/init/", {
        method: "POST",
        body: JSON.stringify(data),
      }),
    detail: (id: number) => request<PaymentRead>(`/payments/${id}/`),
    fees: () => request<Record<string, { libelle: string; montant: string }>>("/payments/fees/"),
    /** DEV ONLY — backend returns 404 in production. */
    devConfirm: (id: number) =>
      request<PaymentRead>(`/payments/dev/${id}/confirm/`, { method: "POST" }),
  },
  notifications: {
    list: (onlyUnread = false) =>
      request<{ results: PortalNotification[]; unread_count: number }>(
        onlyUnread ? "/notifications/?unread=1" : "/notifications/",
      ),
    markRead: (id: number) =>
      request<PortalNotification>(`/notifications/${id}/read/`, {
        method: "POST",
      }),
    markAllRead: () =>
      request<{ marked: number }>("/notifications/read-all/", {
        method: "POST",
      }),
  },
};
