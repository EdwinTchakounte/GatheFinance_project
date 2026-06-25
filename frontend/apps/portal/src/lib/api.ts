/**
 * Portal API client.
 *
 * En prod, on appelle directement `https://api.gathe-finance.horus-lab.com/api/v1/*`
 * pour eviter le double-proxy (browser -> nginx -> portal Next.js -> backend)
 * qui corrompt les POST body et casse la session CSRF.
 * Les cookies sont partages via le COOKIE_DOMAIN=.gathe-finance.horus-lab.com
 * cote Django, donc la session marche d'un sous-domaine a l'autre.
 *
 * En dev local, on garde le chemin relatif `/api/v1` proxy par le rewrite
 * Next.js (cf. next.config.mjs).
 */

function resolveApiBase(): string {
  // Build-time / SSR : URL relative (cookie scope local).
  if (typeof window === "undefined") return "/api/v1";
  const host = window.location.hostname;
  // Prod : tape direct sur l'API publique pour eviter Next.js comme middle-man.
  if (host.endsWith(".gathe-finance.horus-lab.com")) {
    return "https://api.gathe-finance.horus-lab.com/api/v1";
  }
  // Dev local : passe par le rewrite Next.js configure dans next.config.mjs.
  return "/api/v1";
}

const API_BASE = resolveApiBase();

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
  type:
    | "epargne"
    | "epargne_classique"
    | "remboursement"
    | "frais_adhesion"
    | "frais_inscription"
    | "frais_demande_credit"
    | "frais_reconduction"
    | "frais_carnet";
  montant: number;
  phone: string;
  network: "MTN" | "ORANGE" | "WAVE" | "AIRTEL";
  loan_id?: number | null;
  loan_installment_id?: number | null;
  // CH-3 — Sous-canal placement épargne classique (ignoré si type ≠ "epargne_classique").
  is_placement?: boolean;
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

// CH-4 — FormSchema (réponse publique)
export type FormSchemaPublic = {
  id: number;
  kind: "adhesion" | "loan_request" | "loan_renewal";
  version: number;
  title: string;
  description: string;
  schema: { sections: Array<Record<string, unknown>> };
};

export const portalApi = {
  primeCsrf: () => request<{ csrfToken: string }>("/auth/csrf/"),

  // CH-4 — Charge le schéma actif d'un formulaire dynamique.
  formSchema: (kind: "adhesion" | "loan_request" | "loan_renewal") =>
    request<FormSchemaPublic>(`/forms/schemas/${kind}/active/`),

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
      // CH-9 — Canal de réception choisi par le membre à la soumission.
      moyen_reception?: "tara_om" | "tara_momo" | "agence_especes";
      recipient_phone?: string;
      // CH-4 — Champs ajoutés via FormSchema actif côté admin.
      // Routés vers extra_payload par le backend (apply_form_schema).
      [extraField: string]: unknown;
    }) =>
      request<{
        loan_request: LoanRequest;
        route: "senior_brc" | "avaliste" | "campaign" | "none";
        route_details: Record<string, unknown>;
        frais_a_payer: { code: string; libelle: string; montant: string };
      }>("/loans/requests/", { method: "POST", body: JSON.stringify(data) }),

    // CH-9 — URL absolue pour télécharger la note PDF d'une demande.
    noteUrl: (requestId: number) => `${API_BASE}/loans/requests/${requestId}/note/`,

    // CH-5 — Upload d'un fichier rattaché à un LoanRequest (multipart).
    // Idempotent par schema_field_id : re-upload remplace le précédent.
    uploadAttachment: async (
      loanRequestId: number,
      schemaFieldId: string,
      file: File,
    ) => {
      const form = new FormData();
      form.append("fichier", file);
      form.append("schema_field_id", schemaFieldId);
      // On contourne `request` (qui force Content-Type JSON) et fait l'appel
      // directement avec FormData — le navigateur pose le boundary.
      const csrf =
        document.cookie
          .split("; ")
          .find((c) => c.startsWith("csrftoken="))
          ?.slice("csrftoken=".length) ?? "";
      const res = await fetch(
        `${API_BASE}/loans/requests/${loanRequestId}/attachments/`,
        {
          method: "POST",
          credentials: "include",
          headers: { "X-CSRFToken": csrf },
          body: form,
        },
      );
      if (!res.ok) {
        let detail = "Upload échoué.";
        try {
          const j = await res.json();
          if (j.detail) detail = j.detail;
        } catch {
          /* ignore */
        }
        throw { status: res.status, detail } as ApiError;
      }
      return (await res.json()) as {
        id: number;
        schema_field_id: string;
        nom_original: string;
        taille: number;
        url: string | null;
      };
    },
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
    // CH-4 — Accepte aussi des champs ajoutés via FormSchema 'loan_renewal',
    // routés vers LoanRenewal.extra_payload côté backend.
    requestRenewal: (
      loanId: number,
      data: {
        nouvelle_duree_mois?: number;
        interets_au_comptant?: boolean;
        [extraField: string]: unknown;
      } = {},
    ) =>
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
    /** Historique des paiements du membre courant — utilisé notamment par
     *  l'écran d'activation pour identifier quels frais sont déjà réglés. */
    me: (type?: string) =>
      request<{ results: PaymentRead[] }>(
        type ? `/payments/me/?type=${type}` : `/payments/me/`,
      ),
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

  // Carnet : liste des commandes du membre (statut : payee / en_impression / delivree).
  booklet: {
    me: () =>
      request<{ results: { id: number; statut: string; created_at: string; date_impression?: string; date_delivrance?: string }[] }>(
        "/booklet/me/",
      ),
  },

  // Documents officiels coopérative (règlement + spécimen carnet).
  coopDocuments: () =>
    request<{
      reglement_interieur: { url: string | null; uploaded_at: string | null; label: string };
      carnet_specimen: { url: string | null; uploaded_at: string | null; label: string };
    }>("/audit/coop-documents/"),

  // Profil membre — éditer + changer mot de passe.
  profile: {
    update: (data: { first_name?: string; last_name?: string; phone?: string }) =>
      request<Identity>("/members/me/", {
        method: "PATCH",
        body: JSON.stringify(data),
      }),
    changePassword: (current_password: string, new_password: string) =>
      request<{ detail: string }>("/auth/change-password/", {
        method: "POST",
        body: JSON.stringify({ current_password, new_password }),
      }),
  },
};
