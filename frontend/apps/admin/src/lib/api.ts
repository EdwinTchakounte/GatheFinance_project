/**
 * Admin API client — calls the Django cooperative API (/api/v1/*).
 * Same session-cookie + CSRF pattern as the portal.
 */
const API_BASE = "/api/v1";

export type ApiError = { status: number; detail?: string; body?: unknown };

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

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
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
  if (!response.ok) throw await readError(response);
  if (response.status === 204) return undefined as unknown as T;
  return (await response.json()) as T;
}

// -- Types ------------------------------------------------------------------

export type Identity = {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  is_staff: boolean;
  is_superuser: boolean;
  groups: string[];
  member: unknown;
};

export type DashboardKpis = {
  members: { actif: number; suspendu: number };
  queues: { adhesions_en_attente: number; credits_en_instruction: number };
  finance: { encours_credit: string; epargne_total: string };
  recent_payments: Array<{
    id: number;
    montant: string;
    type_display: string;
    statut: string;
    date_validation: string | null;
  }>;
};

export type MembershipRequest = {
  id: number;
  nom: string;
  prenom: string;
  email: string;
  phone: string;
  city: string;
  motivation: string;
  statut: "en_attente" | "approuvee" | "rejetee";
  statut_display: string;
  motif_rejet: string;
  created_at: string;
  date_decision: string | null;
};

export type LoanRequest = {
  id: number;
  montant_demande: string;
  duree_mois: number;
  motif: string;
  statut: string;
  statut_display: string;
  motif_rejet: string;
  date_soumission: string;
  date_decision: string | null;
  loan: {
    id: number;
    numero_dossier: string;
    statut: string;
    date_decaissement: string;
    disbursed: boolean;
    disbursement_pending: boolean;
  } | null;
};

export type DisburseResponse = {
  loan_id: number;
  numero_dossier: string;
  payment_id: number;
  mode: "manuel" | "tara";
  statut: "en_attente" | "valide" | "rejete";
  reference_externe: string;
};

export type AdminLoanRow = {
  id: number;
  numero_dossier: string;
  member: {
    id: number;
    numero_membre: string;
    nom: string;
    prenom: string;
  };
  montant: string;
  montant_total_du: string;
  solde_restant: string;
  taux_interet: string;
  duree_mois: number;
  date_decaissement: string;
  date_premiere_echeance: string;
  statut: "actif" | "en_retard" | "cloture" | "contentieux";
  statut_display: string;
  installments_payees: number;
  installments_total: number;
};

export type Member = {
  id: number;
  numero_membre: string;
  prenom: string;
  nom: string;
  email: string;
  phone: string;
  statut: "actif" | "suspendu" | "radie";
  statut_display: string;
  date_adhesion: string;
};

export type PaymentRow = {
  id: number;
  montant: string;
  type: string;
  type_display: string;
  source: string;
  statut: "en_attente" | "valide" | "rejete" | "annule";
  statut_display: string;
  provider_code: string;
  reference_externe: string;
  date_versement: string;
  date_validation: string | null;
  motif_rejet: string;
  created_at: string;
  member: {
    id: number;
    numero_membre: string;
    nom: string;
    prenom: string;
  };
};

export type FeeConfig = {
  code: string;
  libelle: string;
  montant: string;
  actif: boolean;
};

export type RateConfig = {
  code: string;
  libelle: string;
  valeur: string;
  actif: boolean;
};

export type CostsConfig = { fees: FeeConfig[]; rates: RateConfig[] };

export type Paginated<T> = { count: number; results: T[] };

function qs(params: Record<string, string | undefined>): string {
  const entries = Object.entries(params).filter(
    ([, v]) => v !== undefined && v !== "" && v !== null,
  );
  if (entries.length === 0) return "";
  return "?" + new URLSearchParams(entries as [string, string][]).toString();
}

export const adminApi = {
  primeCsrf: () => request<{ csrfToken: string }>("/auth/csrf/"),
  login: (email: string, password: string) =>
    request<Identity>("/auth/login/", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  logout: () => request<void>("/auth/logout/", { method: "POST" }),
  me: () => request<Identity>("/auth/me/"),

  dashboard: () => request<DashboardKpis>("/admin/dashboard/"),

  membershipRequests: {
    list: (statut?: string) =>
      request<MembershipRequest[]>(
        `/admin/membership-requests/${statut ? `?statut=${statut}` : ""}`,
      ),
    approve: (id: number, payload: { prenom?: string; nom: string }) =>
      request<MembershipRequest>(`/admin/membership-requests/${id}/approve/`, {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    reject: (id: number, motif: string) =>
      request<MembershipRequest>(`/admin/membership-requests/${id}/reject/`, {
        method: "POST",
        body: JSON.stringify({ motif }),
      }),
  },

  loanRequests: {
    list: (statut?: string) =>
      request<LoanRequest[]>(
        `/loans/admin/requests/${statut ? `?statut=${statut}` : ""}`,
      ),
    decide: (
      id: number,
      payload:
        | { decision: "approuvee"; taux_annuel: number; date_premiere_echeance: string }
        | { decision: "rejetee"; motif_rejet: string },
    ) =>
      request<LoanRequest>(`/loans/requests/${id}/decide/`, {
        method: "POST",
        body: JSON.stringify(payload),
      }),
  },

  loans: {
    list: (params: { statut?: string; q?: string } = {}) =>
      request<Paginated<AdminLoanRow>>(`/loans/admin/list/${qs(params)}`),
    disburseTara: (
      loanId: number,
      payload: { recipient_phone: string; network: "MTN" | "ORANGE" | "WAVE" | "AIRTEL" },
    ) =>
      request<DisburseResponse>(`/loans/${loanId}/disburse/`, {
        method: "POST",
        body: JSON.stringify({ mode: "tara", ...payload }),
      }),
    disburseManual: (
      loanId: number,
      payload: { reference_externe: string; note?: string },
    ) =>
      request<DisburseResponse>(`/loans/${loanId}/disburse/`, {
        method: "POST",
        body: JSON.stringify({ mode: "manuel", ...payload }),
      }),
  },

  members: {
    list: (params: { statut?: string; q?: string } = {}) =>
      request<Paginated<Member>>(`/admin/members/${qs(params)}`),
  },

  payments: {
    list: (params: { statut?: string; type?: string; q?: string } = {}) =>
      request<Paginated<PaymentRow>>(`/payments/admin/${qs(params)}`),
  },

  // Coûts modifiables — frais (FCFA) + taux (ratio) en base (BR2/BR3).
  costs: {
    config: () => request<CostsConfig>("/payments/admin/config/"),
    updateFee: (code: string, payload: { montant?: number; libelle?: string; actif?: boolean }) =>
      request<FeeConfig>(`/payments/admin/fees/${code}/`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      }),
    updateRate: (code: string, payload: { valeur?: number; libelle?: string; actif?: boolean }) =>
      request<RateConfig>(`/payments/admin/rates/${code}/`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      }),
  },
};
