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

/** Reconduction de crédit vue par le membre. */
export type LoanRenewal = {
  id: number;
  loan_id: number;
  numero_dossier?: string;
  nouvelle_duree_mois: number;
  statut: string;
  date_demande: string;
  frais_reconduction_payment_id: number | null;
  interets_au_comptant: boolean;
  /** Intérêts figés à la demande (taux × capital restant). */
  interets_dus: string;
  montant_a_reconduire_snapshot: string;
  interets_payes: boolean;
  interets_payes_at: string | null;
  /** Reste à verser. Payable avant OU après la décision du comité. */
  reste_a_payer: string;
};

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

// C1 . Prime CSRF on demand . expose pour la retry interne du request().
// Inline pour eviter une dependance circulaire avec portalApi.primeCsrf.
async function _primeCsrfInternal(): Promise<void> {
  try {
    await fetch(`${API_BASE}/auth/csrf/`, {
      method: "GET",
      credentials: "include",
      headers: { Accept: "application/json" },
    });
  } catch {
    // Best-effort . on remonte l'erreur d'origine si le retry echoue aussi.
  }
}


function _isCsrfFailure(err: unknown): boolean {
  if (typeof err !== "object" || err === null) return false;
  const e = err as { status?: number; detail?: string };
  if (e.status !== 403) return false;
  const msg = (e.detail || "").toLowerCase();
  return msg.includes("csrf") || msg.includes("forbidden");
}

// Session expirée (401 / 403-non-authentifié DRF) — PAS un CSRF ni une
// permission. On route alors proprement vers /connexion au lieu de laisser la
// page marteler l'API en erreur.
function _isSessionExpired(status: number, detail: string): boolean {
  if (status === 401) return true;
  if (status !== 403) return false;
  const msg = detail.toLowerCase();
  return (
    msg.includes("not provided") ||
    msg.includes("non fournies") ||
    msg.includes("authentication credentials") ||
    msg.includes("authentification non fournies")
  );
}

let _redirectingToLogin = false;
function _redirectToLogin(): void {
  if (typeof window === "undefined" || _redirectingToLogin) return;
  const seg = window.location.pathname.split("/")[1];
  const locale = seg === "en" ? "en" : "fr";
  const target = locale === "fr" ? "/connexion" : `/${locale}/connexion`;
  if (window.location.pathname.endsWith("/connexion")) return; // déjà là
  _redirectingToLogin = true;
  window.location.assign(target);
}


async function request<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const method = (init.method || "GET").toUpperCase();
  const isMutating = method !== "GET" && method !== "HEAD";

  // C1 . Si POST et pas de cookie csrf, on tente de le poser AVANT le POST.
  // Couvre le cas ou primeCsrf() au mount de la page a echoue silencieusement
  // (par ex. blocage tiers ou perte de cookie cross-subdomain).
  if (isMutating && !readCookie("csrftoken")) {
    await _primeCsrfInternal();
  }

  // FormData : laisser le navigateur poser Content-Type avec son boundary.
  const isFormData =
    typeof FormData !== "undefined" && init.body instanceof FormData;

  async function send(): Promise<Response> {
    const headers = new Headers(init.headers);
    if (!headers.has("Accept")) headers.set("Accept", "application/json");
    if (init.body && !isFormData && !headers.has("Content-Type")) {
      headers.set("Content-Type", "application/json");
    }
    if (isMutating) {
      const csrf = readCookie("csrftoken");
      if (csrf) headers.set("X-CSRFToken", csrf);
    }
    return fetch(`${API_BASE}${path}`, {
      ...init,
      method,
      headers,
      credentials: "include",
    });
  }

  let response = await send();

  // C1 . Sur TOUT 403 d'une requête mutante, on re-prime le CSRF puis on retry
  // UNE fois. Élargi volontairement au-delà de la détection `_isCsrfFailure` :
  // selon la couche (DRF vs middleware Django) le corps du 403 varie, et rater
  // la détection ferait échouer le retry alors qu'un simple re-prime suffisait.
  // Un vrai 403 de permission re-tombera en 403 au 2e essai (comportement
  // inchangé pour l'utilisateur), donc le retry est sûr.
  if (!response.ok && response.status === 403 && isMutating) {
    await _primeCsrfInternal();
    response = await send();
  }

  if (!response.ok) {
    const err = await readError(response);
    // Session expirée (hors endpoints /auth/* qui gèrent leur propre 401/403 —
    // ex. le check d'identité, pour ne pas forcer le login sur une page ouverte)
    // → redirection propre vers /connexion.
    if (
      !path.startsWith("/auth/") &&
      _isSessionExpired(response.status, err.detail || "")
    ) {
      _redirectToLogin();
      throw err;
    }
    // C1 . Message clair si malgre le retry on a toujours CSRF echec.
    if (response.status === 403 && _isCsrfFailure(err) && isMutating) {
      err.detail =
        "Session de securite expiree. Recharge la page (Ctrl+R) puis reessaie.";
    }
    throw err;
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
  // Le backend a bien plus de types que ces 3 (interet_placement,
  // restitution_maturite, restitution_placement, bascule_collecte…). On garde
  // `string` et on s'appuie sur `type_display` (libellé) + `sens` (credit/debit)
  // du backend plutôt que de maintenir un switch codé en dur.
  type_op: string;
  type_display: string;
  sens?: "credit" | "debit";
  montant: string;
  solde_apres: string;
  date: string;
};

export type SavingsSnapshot = {
  id: number;
  solde: string;
  // Disponible réel au retrait = solde − retraits déjà engagés (réservés).
  // Exposé par le backend depuis 2026-07-22 (parité avec le classique). Peut
  // être absent d'un ancien backend → l'UI retombe alors sur `solde`.
  solde_disponible_retrait?: string;
  date_ouverture: string;
  taux_interet_applique: string;
  end_of_month_preference: EomChoice;
  payout_phone: string;
  payout_network: string;
  transactions_recentes: SavingsTransaction[];
};

// Choix de fin de mois de la collecte journalière (parité mobile).
export type EomChoice = "cash" | "mobile_money" | "epargne";
export type CollecteEomPreference = {
  preference: EomChoice;
  payout_phone: string;
  payout_network: string;
};

// Parite mobile : compte epargne classique (libre + placement).
export type ClassicSavingsSnapshot = {
  id: number;
  solde: string;
  // Part librement retirable (= solde − placements encore actifs) et montant
  // bloqué en placement (garantit le funding crédit). Sert au retrait classique.
  solde_libre: string;
  solde_placement_actif: string;
  // Réforme garantie 2026 : part gelée en garantie d'un crédit (mandat avaliste
  // ou auto-garantie) et solde réellement retirable une fois ce gel déduit.
  montant_gele_credit: string;
  // Scission du gel par MOTIF (règle « mobilisable ssi motif = ce crédit ») :
  //   • apport   = collatéral de MES crédits → mobilisable pour les solder ;
  //   • avaliste = caution sur le crédit d'un AUTRE → non mobilisable, libérée
  //     à la clôture du crédit garanti.
  montant_gele_apport?: string;
  montant_gele_avaliste?: string;
  solde_disponible_retrait: string;
  // Fenêtre placement PAR MEMBRE : true tant que ce membre peut encore verser
  // en placement (verrou global + N premiers mois d'ancienneté). Quand false, le
  // portail masque le choix « placement ». `placement_eligibility_months` = la
  // durée de la fenêtre (mois) pour l'affichage.
  placement_open?: boolean;
  placement_eligibility_months?: number;
  date_ouverture: string;
  config: {
    taux_interet_annuel?: string;
    [key: string]: unknown;
  };
  transactions_recentes: SavingsTransaction[];
};

// LOT 11 — Campagne micro-crédit (voie 3). Miroir du /campaigns mobile :
// catalogue public des campagnes ouvertes + sélecteur dans la demande.
export type Campaign = {
  id: number;
  nom: string;
  profil_cible: string;
  date_debut: string;
  date_fin: string;
  montant_min: string;
  montant_max: string;
  taux_interet: string;
  nb_jours_recouvrement: number;
  flyer_url: string;
};

// Social — likes + commentaires (fil 1 niveau). Miroir du mobile.
export type SocialKind = "articles" | "campaigns";
export type ReactionState = { liked: boolean; count: number };
export type PortalComment = {
  id: number;
  parent_id: number | null;
  body: string;
  author_name: string;
  created_at: string;
  hidden: boolean;
  replies: PortalComment[];
};
export type PortalCommentsPage = {
  count: number;
  limit: number;
  offset: number;
  results: PortalComment[];
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
  // Échéance indicative de l'étude par la commission (soumission + ~1 mois).
  // Règlement : étude sous 1 semaine à 1 mois. Peut être null.
  date_limite_etude?: string | null;
  // Porte des frais d'étude (2026) — exigibles avant toute instruction.
  // Montant piloté admin (FeeType.DEMANDE_CREDIT). null = étude gratuite.
  frais_etude_montant?: string | null;
  frais_demande_credit_paye?: boolean;
  // Part de l'épargne classique réellement ponctionnable pour ces frais
  // (hors placement et hors épargne gelée en garantie). Sert à savoir si le
  // canal « déduction » — proposé par défaut — est tenable, sans second appel.
  epargne_disponible_frais?: string;
  // Voie empruntée (prévisualisation du mode) + montant que l'avaliste couvre.
  voie?: "senior_brc" | "avaliste" | "campagne" | "garantie_materielle";
  voie_display?: string;
  avaliste_montant_a_couvrir?: string;
  // Attribut BRC déclaré — « a fréquenté le centre de formation BRC ».
  // Informatif, couplable à toute voie (le comité juge à l'évaluation).
  is_brc?: boolean;
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

export type LenderState = {
  consent: LenderConsent | null;
  tranches: LenderTranche[];
  totals: {
    disponible: string;
    engagee: string;
    liberee: string;
    annulee: string;
  };
};

// A6 . Versement d'interets recu en tant que preteur (CH-12 / LOT 9).
export type LenderInterestPayout = {
  id: number;
  montant: string;
  date: string;
  loan: { id: number; numero_dossier: string };
  allocation_id: number;
  quote_part: string;
  // "at_source" = paye a T0 (mode source CH-11) | "installment" = au remboursement
  kind: "at_source" | "installment";
  installment_numero: number | null;
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
  // Réforme garantie 2026 : montant gelé sur l'épargne de l'avaliste pour ce
  // mandat (string décimale). Absent tant que le mandat n'est pas accepté.
  montant_gele?: string;
  // L5 — Capture identité (CNI). `cni_demandeur` renseigné à la demande ;
  // `cni_avaliste` + `cni_avaliste_fichier` (url) renseignés à l'acceptation.
  cni_demandeur?: string;
  cni_avaliste?: string;
  cni_avaliste_fichier?: string | null;
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
  /** Apport personnel gelé transférable pour solder ce crédit (2026-07). */
  apport_gele?: string;
  apport_gele_motif?: string;
  created_at: string;
};

export type PaymentInitInput = {
  type:
    | "epargne"
    | "epargne_classique"
    | "caisse_scolaire"
    | "tontine_alimentaire"
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
  // LOT 6 (refonte 2026) — multi-jours pré-payé sur la collecte journalière
  // (type "epargne" uniquement). Le backend valide nb × collecte.min_per_day.
  nb_jours_couverts?: number;
};

export type PaymentInitResponse = {
  payment: PaymentRead;
  paymentUrl: string | null;
  instructions: string;
};

// ── Collectes particulières (caisse scolaire / tontine alimentaire) ──────────
export type SpecialCollectionType = "caisse_scolaire" | "tontine_alimentaire";

export type SpecialCollectionMembershipRead = {
  id: number;
  statut: "en_attente" | "valide" | "rejete" | "suspendu";
  statut_display: string;
  is_active: boolean;
  solde: string;
  objectif: string;
  montant_cible: string | null;
  motif_rejet: string;
  cycle_nom: string;
};

export type SpecialCollectionCycleRead = {
  id: number;
  nom: string;
  is_open: boolean;
  date_debut: string;
  date_fin: string | null;
};

export type SpecialCollectionSlot = {
  type: SpecialCollectionType;
  type_display: string;
  cycle: SpecialCollectionCycleRead | null;
  membership: SpecialCollectionMembershipRead | null;
};

// Refonte 2026 — Retrait avec choix MOMO/présentiel
export type WithdrawalModePaiement = "momo" | "presentiel";
export type WithdrawalNetwork = "MTN" | "ORANGE" | "WAVE" | "AIRTEL";
// Produit source du retrait : collecte journalière ou part LIBRE de l'épargne
// classique (le placement reste bloqué car il garantit le funding crédit).
export type WithdrawalSource = "collecte" | "classique_libre";

// Notifications in-app — alimentées par les hooks métier + les annonces broadcast.
export type PortalNotification = {
  id: number;
  type: string;
  message: string;
  lien: string;
  lue: boolean;
  created_at: string;
};

// Support membre — message d'un fil unique (membre ↔ support coopérative).
export type PortalSupportMessage = {
  id: number;
  sender: "member" | "staff";
  body: string;
  read_by_recipient: boolean;
  created_at: string;
};

// Annonce broadcast (lecture membre) — corps complet + pièce jointe image.
export type PortalAnnouncement = {
  id: number;
  titre: string;
  corps: string;
  lien: string | null;
  image_url: string | null;
  published_at: string | null;
};

export type WithdrawalRead = {
  id: number;
  montant: string;
  motif: string;
  source: WithdrawalSource;
  source_display: string;
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
  // P1 . Mot de passe oublie . envoie un OTP 6 chiffres par mail.
  // Reponse opaque (anti-enumeration) : on ne sait jamais si le mail existe.
  requestPasswordReset: (email: string) =>
    request<{ detail: string }>("/auth/password-reset/request/", {
      method: "POST",
      body: JSON.stringify({ email }),
    }),
  // P1 . Confirme le reset avec le code OTP et un nouveau mot de passe.
  confirmPasswordReset: (payload: {
    email: string;
    code: string;
    new_password: string;
  }) =>
    request<{ detail: string }>("/auth/password-reset/confirm/", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  // PWD Option B . Verifie un token de definition de mot de passe initial.
  // `pieces_required` = true pour un membre créé par l'admin (M1) : il doit
  // charger ses pièces (CNI, photo, plan) en même temps que le mot de passe.
  verifyPasswordSetup: (token: string) =>
    request<{ email_mask: string; expires_at: string; pieces_required?: boolean }>(
      `/auth/setup-password/verify/?token=${encodeURIComponent(token)}`,
    ),
  // PWD Option B . Consomme le token et pose le mot de passe initial. Si des
  // pièces sont fournies (cas M1), on bascule en multipart (FormData).
  confirmPasswordSetup: (payload: {
    token: string;
    password: string;
    cni?: File;
    photo?: File;
    plan?: File;
  }) => {
    const hasFiles = Boolean(payload.cni || payload.photo || payload.plan);
    if (!hasFiles) {
      return request<{ detail: string; email: string }>("/auth/setup-password/confirm/", {
        method: "POST",
        body: JSON.stringify({ token: payload.token, password: payload.password }),
      });
    }
    const fd = new FormData();
    fd.append("token", payload.token);
    fd.append("password", payload.password);
    if (payload.cni) fd.append("cni", payload.cni);
    if (payload.photo) fd.append("photo", payload.photo);
    if (payload.plan) fd.append("plan", payload.plan);
    return request<{ detail: string; email: string }>("/auth/setup-password/confirm/", {
      method: "POST",
      body: fd,
    });
  },
  logout: () => request<void>("/auth/logout/", { method: "POST" }),
  me: () => request<Identity>("/auth/me/"),
  savings: () => request<SavingsSnapshot>("/savings/me/"),
  classicSavings: () =>
    request<ClassicSavingsSnapshot>("/savings/classic/me/"),
  // Règles publiques de la collecte (source de vérité admin) — évite de coder
  // en dur min/step côté client.
  savingsInfo: () =>
    request<{
      collecte_min_per_day_xaf: number;
      collecte_prepay_max_days: number;
      collecte_amount_step_xaf: number;
    }>("/savings/info/"),
  // Choix fin de mois de la collecte : cash (agence) / mobile_money / epargne.
  collecteEomPreference: () =>
    request<CollecteEomPreference>("/savings/me/end-of-month-preference/"),
  setCollecteEomPreference: (body: {
    preference: EomChoice;
    payout_phone?: string;
    payout_network?: string;
  }) =>
    request<CollecteEomPreference>("/savings/me/end-of-month-preference/", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  // P2 . Historique paginé des transactions epargne (DRF PageNumberPagination 20/page).
  // D3 . Statut renouvellement annuel (banniere + bouton paiement carnet).
  renewalStatus: () =>
    request<{
      needs_renewal: boolean;
      in_warning_window: boolean;
      days_until_expiry: number | null;
      prochaine_echeance_iso: string | null;
      carnet_fee_xaf: string | null;
      statut: "actif" | "suspendu" | "radie" | "temporaire";
      lead_days: number;
      grace_days: number;
    }>("/members/me/renewal-status/"),
  savingsTransactions: (params: { page?: number; type_op?: "depot" | "retrait" | "interet" } = {}) => {
    const sp = new URLSearchParams();
    if (params.page) sp.set("page", String(params.page));
    if (params.type_op) sp.set("type_op", params.type_op);
    const qs = sp.toString();
    return request<{
      count: number;
      next: string | null;
      previous: string | null;
      results: SavingsTransaction[];
    }>(`/savings/transactions/${qs ? `?${qs}` : ""}`);
  },
  // Historique paginé de l'épargne classique (dissocié de la collecte).
  classicSavingsTransactions: (params: { page?: number; type_op?: "depot" | "retrait" | "interet" } = {}) => {
    const sp = new URLSearchParams();
    if (params.page) sp.set("page", String(params.page));
    if (params.type_op) sp.set("type_op", params.type_op);
    const qs = sp.toString();
    return request<{
      count: number;
      next: string | null;
      previous: string | null;
      results: SavingsTransaction[];
    }>(`/savings/classic/transactions/${qs ? `?${qs}` : ""}`);
  },

  withdrawals: {
    listMine: () =>
      request<{ results: WithdrawalRead[] }>("/savings/withdrawals/me/"),
    create: (payload: {
      montant: number;
      motif?: string;
      source?: WithdrawalSource;
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
    // Récupération d'une tranche : réservée à l'ADMIN (le membre ne l'annule
    // pas lui-même). Pas d'endpoint membre exposé.
    // A6 . Historique des interets percus en tant que preteur.
    payouts: () =>
      request<{
        count: number;
        results: LenderInterestPayout[];
      }>("/loans/me/lender-payouts/"),
  },
  loans: {
    eligibility: () =>
      request<{
        eligible: boolean;
        plafond_max: string;
        // Réforme garantie 2026 : montant empruntable SANS avaliste (= épargne
        // classique disponible du membre). Indicatif, pas un plafond dur —
        // au-delà, le membre doit désigner un avaliste.
        plafond_sans_avaliste: string;
        motifs_ineligibilite: string[];
        solde_epargne: string;
        ratio_garantie: string;
      }>("/loans/me/eligibility/"),
    listMine: () => request<LoanRequest[]>("/loans/me/requests/"),
    activeMine: () => request<Loan[]>("/loans/me/active/"),
    // P3 . Historique credits cloturees.
    closedMine: () => request<Loan[]>("/loans/me/closed/"),
    // Remboursement par TRANSFERT depuis l'épargne (parité mobile). Synchrone :
    // débite l'épargne dispo (classique retirable + collecte), impute au crédit.
    repayFromSavings: (loanId: number, montant: number) =>
      request<{
        payment_id: number;
        montant: string;
        solde_restant: string;
        statut: string;
      }>(`/loans/me/loans/${loanId}/repay-from-savings/`, {
        method: "POST",
        body: JSON.stringify({ montant }),
      }),
    /** Transfère l'apport GELÉ pour solder le crédit (montant optionnel). */
    repayFromFrozen: (loanId: number, montant?: number) =>
      request<{
        payment_id: number;
        montant: string;
        solde_restant: string;
        statut: string;
      }>(`/loans/me/loans/${loanId}/repay-from-frozen/`, {
        method: "POST",
        body: JSON.stringify(montant != null ? { montant } : {}),
      }),
    create: (data: {
      montant_demande: number;
      duree_mois: number;
      motif: string;
      // L5 — Numéro de CNI du demandeur (capture identité à la demande).
      cni_demandeur?: string;
      avaliste_numero?: string;
      avaliste_nom?: string;
      campaign_id?: number;
      profil_cible?: string;
      // Réforme crédit L4 — voie garantie matérielle (bien mis en garantie).
      garantie_materielle?: boolean;
      garantie_description?: string;
      // CH-9 — Canal de réception choisi par le membre à la soumission.
      moyen_reception?: "tara_om" | "tara_momo" | "agence_especes";
      recipient_phone?: string;
      // Attribut BRC déclaré — informatif, couplable à toute voie.
      is_brc?: boolean;
      // CH-4 — Champs ajoutés via FormSchema actif côté admin.
      // Routés vers extra_payload par le backend (apply_form_schema).
      [extraField: string]: unknown;
    }) =>
      request<{
        loan_request: LoanRequest;
        route: "senior_brc" | "avaliste" | "campaign" | "garantie_materielle" | "none";
        route_details: Record<string, unknown>;
        frais_a_payer: { code: string; libelle: string; montant: string };
      }>("/loans/requests/", { method: "POST", body: JSON.stringify(data) }),

    // Réponse du membre à une contre-proposition du comité (débloque le statut
    // en_attente_acceptation_membre).
    acceptCounterProposal: (requestId: number) =>
      request<LoanRequest>(
        `/loans/me/requests/${requestId}/counter-proposal/accept/`,
        { method: "POST" },
      ),
    refuseCounterProposal: (requestId: number, motif?: string) =>
      request<LoanRequest>(
        `/loans/me/requests/${requestId}/counter-proposal/refuse/`,
        { method: "POST", body: JSON.stringify({ motif: motif ?? "" }) },
      ),

    // CH-9 — URL absolue pour télécharger la note PDF d'une demande.
    noteUrl: (requestId: number) => `${API_BASE}/loans/requests/${requestId}/note/`,

    // LOT 11 — Catalogue public des campagnes micro-crédit ouvertes (miroir
    // du carousel/liste mobile). Endpoint AllowAny paginé limit/offset.
    activeCampaigns: (params: { limit?: number; offset?: number } = {}) => {
      const sp = new URLSearchParams();
      if (params.limit) sp.set("limit", String(params.limit));
      if (params.offset) sp.set("offset", String(params.offset));
      const qs = sp.toString();
      return request<{
        count: number;
        next: string | null;
        previous: string | null;
        results: Campaign[];
      }>(`/loans/campaigns/active/${qs ? `?${qs}` : ""}`);
    },

    // Typeahead avaliste : recherche un membre Senior actif dispo comme
    // garant. Anti-fraude : compare numero_membre ET nom cote backend lors
    // de la creation de la demande. Le mobile utilise le meme endpoint.
    searchAvaliste: (q: string) =>
      request<{
        results: Array<{
          numero_membre: string;
          nom: string;
          prenom: string;
          is_senior: boolean;
          capacite_caution: string;
        }>;
      }>(`/members/search-avaliste/?q=${encodeURIComponent(q)}`),

    // CH-5 — Upload d'un fichier rattaché à un LoanRequest (multipart).
    // Idempotent par schema_field_id : re-upload remplace le précédent.
    uploadAttachment: (
      loanRequestId: number,
      schemaFieldId: string,
      file: File,
    ) => {
      // Le wrapper request() gere FormData + CSRF + auto-recovery (C1).
      const form = new FormData();
      form.append("fichier", file);
      form.append("schema_field_id", schemaFieldId);
      return request<{
        id: number;
        schema_field_id: string;
        nom_original: string;
        taille: number;
        url: string | null;
      }>(
        `/loans/requests/${loanRequestId}/attachments/`,
        { method: "POST", body: form },
      );
    },
    // Refonte 2026 LOT 18 — Mandats d'avaliste (côté garant).
    avalisteMandats: {
      list: (statut?: "pending" | "accepted" | "refused") =>
        request<{
          count: number;
          pending: number;
          results: AvalisteMandat[];
        }>(`/loans/me/avaliste-mandats/${statut ? `?statut=${statut}` : ""}`),
      // L5 — Réponse au mandat. Contrat backend asymétrique :
      //  · ACCEPTER → multipart/form-data OBLIGATOIRE avec accept=true +
      //    cni_avaliste (n° CNI) + cni_avaliste_fichier (image/pdf). Manque
      //    l'un des deux → 400.
      //  · REFUSER → JSON inchangé { accept:false, motif }.
      respond: (
        id: number,
        payload:
          | { accept: true; cni_avaliste: string; cni_avaliste_fichier: File }
          | { accept: false; motif?: string },
      ) => {
        const path = `/loans/me/avaliste-mandats/${id}/respond/`;
        if (payload.accept) {
          // Le wrapper request() pose le boundary + le CSRF pour un FormData.
          const form = new FormData();
          form.append("accept", "true");
          form.append("cni_avaliste", payload.cni_avaliste);
          form.append("cni_avaliste_fichier", payload.cni_avaliste_fichier);
          return request<AvalisteMandat>(path, { method: "POST", body: form });
        }
        return request<AvalisteMandat>(path, {
          method: "POST",
          body: JSON.stringify({ accept: false, motif: payload.motif ?? "" }),
        });
      },
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
      request<{ renewal: LoanRenewal }>(`/loans/${loanId}/renewal/`, {
        method: "POST",
        body: JSON.stringify(data),
      }),

    /** Mes reconductions, avec le reste à verser sur les intérêts. */
    myRenewals: () =>
      request<{ results: LoanRenewal[] }>(`/loans/me/renewals/`),

    /** Règle les intérêts de reconduction par prélèvement sur l'épargne. */
    payRenewalInterestFromSavings: (renewalId: number) =>
      request<{ renewal: LoanRenewal; payment_id: number }>(
        `/loans/renewals/${renewalId}/pay-interest-from-savings/`,
        { method: "POST" },
      ),
    /** Frais d'étude — 3e canal : déduction sur l'épargne classique.
     *
     *  Ne PAS passer par `/payments/init/` : cet endpoint force
     *  `source=mobile_money` et attend un encaissement externe. Ici c'est un
     *  transfert interne, donc synchrone : pas de paymentUrl, pas de webhook,
     *  pas de polling — la demande revient déjà avec son nouveau statut.
     *
     *  409 si le retirable ne couvre pas les frais (le placement et l'épargne
     *  gelée en garantie ne sont pas ponctionnables) ou s'il n'y a pas de
     *  compte classique. */
    payStudyFeeFromSavings: (requestId: number) =>
      request<LoanRequest>(
        `/loans/requests/${requestId}/study-fee/from-savings/`,
        { method: "POST" },
      ),
  },
  specialCollections: {
    /** Par type : cycle ouvert (le cas échéant) + ma participation. */
    mine: () => request<SpecialCollectionSlot[]>("/special-collections/"),
    /** Demande de participation au cycle ouvert. */
    request: (payload: {
      type: SpecialCollectionType;
      objectif: string;
      montant_cible?: number | null;
    }) =>
      request<SpecialCollectionMembershipRead>("/special-collections/request/", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    /** Transfert interne depuis l'épargne classique disponible. */
    transfer: (payload: { type: SpecialCollectionType; montant: number }) =>
      request<{ id: number; solde_apres: string }>(
        "/special-collections/transfer/",
        { method: "POST", body: JSON.stringify(payload) },
      ),
  },
  payments: {
    init: (data: PaymentInitInput) =>
      request<PaymentInitResponse>("/payments/init/", {
        method: "POST",
        body: JSON.stringify(data),
      }),
    detail: (id: number) => request<PaymentRead>(`/payments/${id}/`),
    /** URL du reçu de versement (mini-facture PDF) — ouverte dans un onglet.
     *  Le PDF est servi inline par le backend (cookies de session inclus). */
    receiptUrl: (id: number) => `${API_BASE}/payments/${id}/receipt/`,
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
    announcements: () =>
      request<{ results: PortalAnnouncement[] }>(
        "/notifications/announcements/",
      ),
  },

  // Support membre (fil unique membre ↔ support). Parité avec le mobile.
  support: {
    thread: () =>
      request<{ thread_id: number; messages: PortalSupportMessage[] }>(
        "/support/thread/",
      ),
    send: (body: string) =>
      request<PortalSupportMessage>("/support/messages/", {
        method: "POST",
        body: JSON.stringify({ body }),
      }),
    unread: () => request<{ count: number }>("/support/unread/"),
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

  // Social — likes + commentaires (articles & campagnes). Miroir du mobile.
  social: {
    reaction: (kind: SocialKind, id: number) =>
      request<ReactionState>(`/social/${kind}/${id}/reaction/`),
    toggleLike: (kind: SocialKind, id: number) =>
      request<ReactionState>(`/social/${kind}/${id}/like/`, { method: "POST" }),
    comments: (
      kind: SocialKind,
      id: number,
      params: { limit?: number; offset?: number } = {},
    ) => {
      const sp = new URLSearchParams();
      if (params.limit != null) sp.set("limit", String(params.limit));
      if (params.offset != null) sp.set("offset", String(params.offset));
      const q = sp.toString();
      return request<PortalCommentsPage>(
        `/social/${kind}/${id}/comments/${q ? `?${q}` : ""}`,
      );
    },
    postComment: (kind: SocialKind, id: number, body: string, parentId?: number) =>
      request<PortalComment>(`/social/${kind}/${id}/comments/`, {
        method: "POST",
        body: JSON.stringify(parentId ? { body, parent_id: parentId } : { body }),
      }),
    deleteComment: (pk: number) =>
      request<void>(`/social/comments/${pk}/`, { method: "DELETE" }),
  },
};
