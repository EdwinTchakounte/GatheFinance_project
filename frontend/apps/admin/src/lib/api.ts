/**
 * Admin API client.
 *
 * En prod, appel direct vers `https://api.gathe-finance.horus-lab.com/api/v1/*`
 * pour eviter le double-proxy (browser -> nginx -> admin Next.js -> backend)
 * qui corrompt les POST body. Cookies session/csrftoken partages via
 * COOKIE_DOMAIN=.gathe-finance.horus-lab.com cote Django.
 * En dev local, chemin relatif via le rewrite Next.js (cf. next.config.mjs).
 */
function resolveApiBase(): string {
  if (typeof window === "undefined") return "/api/v1";
  const host = window.location.hostname;
  if (host.endsWith(".gathe-finance.horus-lab.com")) {
    return "https://api.gathe-finance.horus-lab.com/api/v1";
  }
  return "/api/v1";
}
const API_BASE = resolveApiBase();

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
  // Ordre de résolution du message affiché à l'utilisateur :
  //   1. ``body.detail`` (forme DRF standard pour les 4xx métier)
  //   2. ``body.<field>`` (DRF ValidationError — on prend les 3 premiers
  //      champs et on les humanise en "nom : Champ requis.")
  //   3. ``body`` string brut (fallback si le backend ne renvoie pas du
  //      JSON propre — utile pour le 500 + ngrok HTML page)
  let detail: string | undefined;
  if (typeof body === "object" && body !== null) {
    const obj = body as Record<string, unknown>;
    if ("detail" in obj && obj.detail != null) {
      detail = String(obj.detail);
    } else {
      const pairs: string[] = [];
      for (const [field, value] of Object.entries(obj).slice(0, 3)) {
        if (Array.isArray(value) && value.length > 0) {
          pairs.push(`${field} : ${String(value[0])}`);
        } else if (typeof value === "string") {
          pairs.push(`${field} : ${value}`);
        }
      }
      if (pairs.length > 0) detail = pairs.join(" — ");
    }
  } else if (typeof body === "string" && body.trim().length > 0) {
    detail = body.slice(0, 240);
  }
  return { status: response.status, detail, body };
}

// C1 . Prime CSRF on demand . expose pour la retry interne du request().
// Inline pour eviter une dependance circulaire avec adminApi.primeCsrf.
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

// Session expirée (401 / 403-non-authentifié DRF) — PAS un CSRF, PAS une
// permission RBAC ("ressource non autorisée"). On route vers /login.
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
  if (window.location.pathname.startsWith("/login")) return; // déjà là
  _redirectingToLogin = true;
  window.location.assign("/login?reason=expired");
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const method = (init.method || "GET").toUpperCase();
  const isMutating = method !== "GET" && method !== "HEAD";
  // FormData : laisser le navigateur poser Content-Type avec son boundary.
  const isFormData =
    typeof FormData !== "undefined" && init.body instanceof FormData;

  // C1 . Si POST et pas de cookie csrf, on tente de le poser AVANT le POST.
  // Couvre le cas ou primeCsrf() au mount de la page a echoue silencieusement
  // (par ex. blocage tiers ou perte de cookie cross-subdomain).
  if (isMutating && !readCookie("csrftoken")) {
    await _primeCsrfInternal();
  }

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

  // C1 . Si 403 CSRF, on re-prime puis on retry UNE fois. Couvre l'expiration
  // de token entre primeCsrf() initial et le POST utilisateur.
  if (!response.ok && response.status === 403 && isMutating) {
    const firstError = await readError(response);
    if (_isCsrfFailure(firstError)) {
      await _primeCsrfInternal();
      response = await send();
    } else {
      throw firstError;
    }
  }

  if (!response.ok) {
    const err = await readError(response);
    // Session expirée (hors /auth/* qui gèrent leur propre 401/403 — ex. le
    // whoami du layout) → redirection propre vers /login.
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
  // RBAC — ressources (onglets) accessibles + accès total.
  resources?: string[];
  full_access?: boolean;
};

// -- RBAC : utilisateurs & accès -------------------------------------------
export type AccessResource = { key: string; label: string };

export type StaffRole = {
  id: number;
  name: string;
  description: string;
  resources: string[];
  users_count: number;
};

export type StaffUser = {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  is_active: boolean;
  is_superuser: boolean;
  groups: string[];
  role_ids: number[];
  roles: string[];
  resources: string[];
  full_access: boolean;
  temporary_password?: string;
};

export type DashboardKpis = {
  members: {
    actif: number;
    suspendu: number;
    temporaire: number;
    brc_validated: number;
  };
  queues: {
    adhesions_en_attente: number;
    credits_en_instruction: number;
    avaliste_pending: number;
    campaign_validation_pending: number;
  };
  finance: {
    encours_credit: string;
    epargne_total: string;
    epargne_collecte: string;
    // A3 . "Epargne classique" = libre + placement actif (LenderTranche
    // DISPONIBLE + ENGAGEE). Le breakdown sert au sous-detail UI.
    epargne_classique: string;
    epargne_classique_libre: string;
    epargne_placement: string;
  };
  epargne_classique_cycle: {
    notifie: number;
    urgence: number;
    en_attente_paiement: number;
  };
  lenders: {
    consents_actifs: number;
    tranches_disponible: string;
    tranches_engagee: string;
    funding_in_progress: number;
  };
  campaigns: {
    actives: number;
  };
  contentieux: {
    loans_en_retard: number;
    loans_contentieux: number;
    escalades_ouvertes: number;
  };
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
  whatsapp: string;
  city: string;
  quartier_localite: string;
  statut_pro: string;
  urgence_nom: string;
  urgence_lien: string;
  urgence_phone: string;
  motivation: string;
  // 4 documents soumis a l'inscription (FileFields cote backend).
  cni_recto_url: string | null;
  cni_verso_url: string | null;
  plan_localisation_url: string | null;
  photo_identite_url: string | null;
  statut: "en_attente" | "approuvee" | "rejetee";
  statut_display: string;
  motif_rejet: string;
  created_at: string;
  date_decision: string | null;
};

export type LoanRequest = {
  id: number;
  // Membre qui a soumis la demande. Indispensable pour l'admin (cash-in
  // frais d'etude en `en_attente`, identification, contact).
  member: {
    id: number;
    numero_membre: string;
    nom: string;
    prenom: string;
    telephone: string;
  } | null;
  montant_demande: string;
  duree_mois: number;
  motif: string;
  statut: string;
  statut_display: string;
  motif_rejet: string;
  date_soumission: string;
  date_decision: string | null;
  // Échéance indicative de l'étude par la commission (soumission + ~1 mois).
  // Règlement : étude sous 1 semaine à 1 mois. Peut être null.
  date_limite_etude?: string | null;
  // Frais d'étude applicables (piloté admin / campagne) — pour préremplir le
  // montant du cash-in « Encaisser frais ». Null si non configuré.
  frais_etude_montant?: string | null;
  // CH-6 — Workflow double approbation : visite terrain entre provisoire et définitive.
  field_visit_outcome?: "" | "favorable" | "defavorable" | "a_revoir";
  field_visit_done_at?: string | null;
  field_visit_note?: string;
  // L4 — Voie « garantie matérielle » : le membre gèle un bien (titre de
  // propriété uploadé). La commission évalue le bien (informel, non bloquant)
  // puis approuve via le flux decide normal.
  garantie_materielle?: boolean;
  garantie_description?: string;
  garantie_valeur_estimee?: string;
  montant_gele_demandeur?: string;
  loan: {
    id: number;
    numero_dossier: string;
    statut: string;
    date_decaissement: string;
    disbursed: boolean;
    disbursement_pending: boolean;
  } | null;
  // Réponses FormSchema (radio/select/checkbox) + valeurs scalaires.
  // Garanti par le compat layer backend pour `ancien_apprenant` et
  // `cga_adherent` même si le seed FormSchema n'est pas à jour.
  extra_payload?: Record<string, unknown>;
  // Pièces justificatives uploadées (attestation CFP, carte CGA, …).
  // Indexées par `schema_field_id` — l'UI fait le mapping pour l'affichage.
  attachments?: Array<{
    id: number;
    schema_field_id: string;
    nom_original: string;
    taille: number;
    url: string | null;
  }>;
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
  // CH-11 — Mode de retenue d'intérêts (source = 90% versé, echeances = legacy).
  mode_retenue_interets: "source" | "echeances";
  montant_decaisse_net: string | null;
  interets_retenus_source: string | null;
  // CH-9 — Canal de réception choisi à la soumission de la demande.
  moyen_reception: "" | "tara_om" | "tara_momo" | "agence_especes";
  recipient_phone: string;
  // CH-9 — Statut du dernier décaissement (null = jamais déclenché).
  disbursement:
    | null
    | {
        payment_id: number;
        statut: "en_attente" | "valide" | "rejete";
        source: "manuel" | "mobile_money";
        reference_externe: string;
      };
};

// A1 . Detail d'un credit pour le drawer admin.
export type AdminLoanInstallment = {
  id: number;
  numero_echeance: number;
  date_echeance: string;
  montant_capital: string;
  montant_interets: string;
  montant_total: string;
  montant_paye: string;
  montant_penalite: string;
  statut: "a_venir" | "payee" | "en_retard" | "partielle";
  statut_display: string;
};

export type AdminLoanRepayment = {
  id: number;
  installment_numero: number;
  installment_id: number;
  payment_id: number;
  payment_type: string;
  payment_source: string;
  payment_reference_externe: string;
  montant_impute: string;
  date: string;
};

export type AdminLoanDetail = {
  loan: {
    id: number;
    numero_dossier: string;
    montant: string;
    montant_total_du: string;
    solde_restant: string;
    statut: string;
    statut_display: string;
    date_decaissement: string | null;
    member: {
      id: number;
      numero_membre: string;
      nom: string;
      prenom: string;
    };
  };
  installments: AdminLoanInstallment[];
  repayments: AdminLoanRepayment[];
  totaux: {
    rembourse_total: string;
    nb_repayments: number;
    nb_installments_payees: number;
    nb_installments_total: number;
  };
};

// A2 . Echeance dans le widget Suivi paiement.
export type AdminInstallmentRow = {
  id: number;
  numero_echeance: number;
  date_echeance: string;
  montant_total: string;
  montant_paye: string;
  montant_penalite: string;
  montant_restant: string;
  statut: "a_venir" | "en_retard" | "partielle" | "payee";
  statut_display: string;
  loan: {
    id: number;
    numero_dossier: string;
  };
  member: {
    id: number;
    numero_membre: string;
    nom: string;
    prenom: string;
  };
};

export type LoanDisbursementStatus = {
  loan_id: number;
  numero_dossier: string;
  has_payment: boolean;
  payment_id?: number;
  statut?: "en_attente" | "valide" | "rejete";
  source?: "manuel" | "mobile_money";
  provider_code?: string;
  reference_externe?: string;
  motif_rejet?: string;
  date_versement?: string | null;
  gateway_initiated_at?: string | null;
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
  // Refonte 2026 — LOT 1 (BRC + ancienneté).
  is_brc_member?: boolean;
  brc_validated_at?: string | null;
  seniority_months?: number;
  is_senior?: boolean;
  // Recap financier par membre (liste admin) — soldes globaux.
  epargne_collecte?: string;
  epargne_classique_libre?: string;
  epargne_placement?: string;
  epargne_total?: string;
  credit_encours?: string;
};

// Refonte 2026 — LOT 1 BRC.
export type BRCDocument = {
  id: number;
  member: number;
  member_numero: string;
  member_nom: string;
  member_prenom: string;
  fichier_url: string;
  nom_original: string;
  taille: number;
  statut: "en_attente" | "valide" | "rejete";
  statut_display: string;
  motif_rejet: string;
  validated_by: number | null;
  validated_at: string | null;
  created_at: string;
};

// Pipeline d'adhesion : funnel + KPIs + membres SUSPENDU.
export type AdhesionFeeStatus = {
  code: string;
  label: string;
  statut: "valide" | "en_attente";
};

export type AdhesionSuspendedMember = {
  member_id: number;
  numero_membre: string;
  prenom: string;
  nom: string;
  phone: string;
  email: string;
  approved_at: string | null;
  fees_status: AdhesionFeeStatus[];
  fees_paid_count: number;
  fees_total: number;
  amount_paid: string;
  amount_target: string;
  amount_remaining: string;
};

export type AdhesionPipeline = {
  funnel: {
    requests_en_attente: number;
    requests_approved_pending_payment: number;
    requests_rejected: number;
    members_actifs: number;
    members_temporaires: number;
    members_radies: number;
  };
  expected_revenue: {
    total_remaining_from_suspended: string;
  };
  required_fees: { code: string; label: string }[];
  suspended_members: AdhesionSuspendedMember[];
};

// Commande de carnet pilotee par l'agence (cote admin).
export type BookletOrderAdmin = {
  id: number;
  statut: "payee" | "en_impression" | "delivree";
  statut_display: string;
  date_impression: string | null;
  date_delivrance: string | null;
  notes_agence: string;
  member_id: number;
  member_nom: string;
  member_prenom: string;
  member_numero: string;
  member_phone: string;
  payment_id: number;
  payment_montant: string;
  created_at: string;
};

// Refonte 2026 — LOT 5 Renouvellements épargne classique.
export type RenewalRow = {
  id: number;
  member_id: number;
  member_numero: string;
  member_nom: string;
  member_prenom: string;
  member_email: string;
  solde: string;
  cycle_courant: number;
  date_ouverture: string;
  date_prochaine_maturite: string | null;
  statut_renouvellement:
    | "actif"
    | "notifie"
    | "urgence"
    | "en_attente_paiement"
    | "archive";
  statut_display: string;
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
  // LOT 6 — multi-jours pré-payé (collecte journalière).
  nb_jours_couverts?: number;
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

// Cron schedules (django-q).
export type CronScheduleRow = {
  id: number;
  name: string;
  func: string;
  schedule_type: string;
  cron: string;
  repeats: number;
  next_run: string | null;
  default_cron: string | null;
  is_admin_edited: boolean;
};

// Annonces broadcast — diffusion admin → membres (Notification in-app).
export type AnnouncementAudience = "all" | "actifs" | "suspendus" | "selection";

export type AnnouncementRow = {
  id: number;
  titre: string;
  corps: string;
  audience: AnnouncementAudience;
  audience_display: string;
  audience_member_ids: number[];
  lien: string;
  image_url?: string | null;
  author: number | null;
  author_email: string | null;
  published_at: string | null;
  expires_at: string | null;
  recipients_count: number;
  created_at: string;
  updated_at: string;
};

export type AnnouncementCreatePayload = {
  titre: string;
  corps: string;
  audience: AnnouncementAudience;
  audience_member_ids?: number[];
  lien?: string;
  expires_at?: string | null;
  image?: File;
};


// P2 — AppSettings tunables (refonte 2026).
export type AppSettingType = "int" | "decimal" | "bool" | "str" | "csv" | "enum";

export type AppSettingRow = {
  key: string;
  group: string;
  label: string;
  description: string;
  type: AppSettingType;
  default: string;
  value: string;
  is_admin_edited: boolean;
  choices?: string[];
  min?: number;
  max?: number;
};

export type AppSettingGroup = { key: string; label: string };

export type AppSettingsResponse = {
  groups: AppSettingGroup[];
  settings: AppSettingRow[];
};

export type Paginated<T> = {
  count: number;
  results: T[];
  // Paginees offset/limit (membres / credits / paiements) renvoient ces champs.
  // Optionnels car d'autres endpoints `count + results` historiques ne les
  // renvoient pas encore.
  limit?: number;
  offset?: number;
};

// Journal d'audit — toutes les actions tracees (HTTP middleware + events metier).
export type AuditLogUser = {
  id: number;
  email: string;
  full_name: string;
  is_staff: boolean;
  is_superuser: boolean;
};

export type AuditLogRow = {
  id: number;
  action: string;
  entite_type: string;
  entite_id: number | null;
  user: AuditLogUser | null;
  ip: string;
  user_agent: string;
  details_json: Record<string, unknown>;
  created_at: string;
};

export type AuditLogPage = {
  count: number;
  limit: number;
  offset: number;
  results: AuditLogRow[];
};

export type AuditLogFacets = { actions: string[]; entite_types: string[] };

export type AuditLogFilters = {
  q?: string;
  user?: string;
  action?: string;
  entite_type?: string;
  entite_id?: string;
  date_from?: string;
  date_to?: string;
  limit?: number;
  offset?: number;
};

// Interactions sociales — commentaires (like est suivi cote mobile uniquement).
export type SocialCommentRow = {
  id: number;
  parent_id: number | null;
  body: string;
  author_name: string;
  author_email: string;
  created_at: string;
  updated_at: string;
  hidden: boolean;
  hidden_by_email: string | null;
  hidden_at: string | null;
  hidden_reason: string;
  // ex. "cms.blogpostpage" ou "loans.microcreditcampaign"
  content_type_label: string;
  object_id: number;
};

export type SocialCommentsPage = {
  count: number;
  limit: number;
  offset: number;
  results: SocialCommentRow[];
};

export type SocialCommentsFilters = {
  q?: string;
  // "1" = uniquement masques, "0" = uniquement visibles, "" = tous.
  hidden?: "" | "1" | "0";
  // "article" | "campaign" | "" (= tous).
  content_type?: "" | "article" | "campaign";
  limit?: number;
  offset?: number;
};

// Admin blog (articles vitrine) — liste complète (publiés + brouillons).
export type AdminBlogArticle = {
  id: number;
  title: string;
  slug: string;
  date: string | null;
  live: boolean;
  has_unpublished_changes: boolean;
  html_url: string | null;
  cover_image_data: { url: string } | null;
  comment_count: number;
  author_name: string | null;
};

export type AdminBlogPage = {
  count: number;
  limit: number;
  offset: number;
  results: AdminBlogArticle[];
};

// Commentaire d'un article (vue staff — inclut les masqués).
export type ArticleCommentRow = {
  id: number;
  parent_id: number | null;
  body: string;
  author_name: string;
  created_at: string;
  hidden: boolean;
  replies: ArticleCommentRow[];
};

export type ArticleCommentsPage = {
  count: number;
  limit: number;
  offset: number;
  results: ArticleCommentRow[];
};

// Refonte 2026 — Retraits épargne avec canal MOMO/présentiel + payout Tara.
export type WithdrawalStatut =
  | "en_attente"
  | "approuvee"
  | "en_payout"
  | "completee"
  | "payout_failed"
  | "rejetee";

export type WithdrawalRow = {
  id: number;
  numero_membre: string;
  member_nom: string;
  montant: string;
  motif: string;
  // Produit débité : collecte journalière ou part libre de l'épargne classique.
  source: "collecte" | "classique_libre";
  source_display: string;
  statut: WithdrawalStatut;
  statut_display: string;
  mode_paiement: "momo" | "presentiel";
  mode_paiement_display: string;
  recipient_phone_masked: string;
  network: "" | "MTN" | "ORANGE" | "WAVE" | "AIRTEL";
  motif_rejet: string;
  date_demande: string;
  date_decision: string | null;
  handed_over_at: string | null;
  can_mark_paid: boolean;
  can_retry_payout: boolean;
};

// Reconduction de crédit (Art.10/11) — file d'attente admin.
export type LoanRenewalStatut = "demandee" | "approuvee" | "rejetee";
export type LoanRenewalRow = {
  id: number;
  statut: LoanRenewalStatut;
  statut_display: string;
  loan_id: number;
  numero_dossier: string;
  numero_membre: string;
  member_nom: string;
  montant_credit: string;
  solde_restant: string;
  duree_actuelle_mois: number;
  nouvelle_duree_mois: number;
  interets_au_comptant: boolean;
  date_demande: string | null;
  date_decision: string | null;
};

// LOT 16 — Campagnes micro-crédit (voie 3).
export type MicrocampaignRow = {
  id: number;
  nom: string;
  profil_cible: string;
  date_debut: string;
  date_fin: string;
  montant_min: string;
  montant_max: string;
  taux_interet: string;
  nb_jours_recouvrement: number;
  plafond_beneficiaires: number | null;
  membre_requis: boolean;
  frais_etude_montant: string | null;
  documents_requis: string[];
  actif: boolean;
  is_open: boolean;
  closed_at: string | null;
  close_reason: string;
  beneficiaires_count: number;
  targeted_count: number;
  flyer_url: string | null;
  created_at: string;
  created_by_id: number;
};

export type MicrocampaignTargetedMember = {
  id: number;
  numero_membre: string;
  nom: string;
  prenom: string;
  statut: string;
};

export type MicrocampaignPendingRequest = {
  id: number;
  member_id: number;
  member_nom: string;
  member_numero: string;
  montant_demande: string;
  duree_mois: number;
  motif: string;
  date_soumission: string;
};

export type MicrocampaignBeneficiaire = {
  id: number;
  numero_membre: string;
  nom: string;
  prenom: string;
  statut: string;
  date_adhesion: string;
  // Crédit issu de la campagne — null tant que pas décaissé. Permet le suivi
  // du remboursement (montant, solde restant, % remboursé, statut).
  loan: {
    id: number;
    numero_dossier: string;
    montant: string;
    solde_restant: string;
    statut: "actif" | "en_retard" | "cloture" | "contentieux";
    statut_display: string;
    date_decaissement: string | null;
    pct_rembourse: number;
  } | null;
};

export type MicrocampaignDetail = MicrocampaignRow & {
  pending_requests: MicrocampaignPendingRequest[];
  pending_count: number;
  beneficiaires: MicrocampaignBeneficiaire[];
  targeted_members: MicrocampaignTargetedMember[];
};

// 2026 — Candidature d'un visiteur non-membre à une campagne (membre_requis=False).
export type CampaignApplicationRow = {
  id: number;
  nom: string;
  prenom: string;
  phone: string;
  email: string;
  montant_demande: string;
  motif: string;
  statut: "en_attente" | "acceptee" | "rejetee";
  statut_display: string;
  created_at: string;
  member_id: number | null;
  numero_membre: string | null;
  loan_request_id: number | null;
  documents: { label: string; url: string | null }[];
};

export type MicrocampaignTargetedAddResponse = {
  campaign: MicrocampaignRow;
  added_count: number;
  not_found: { member_ids: number[]; numeros_membre: string[] };
  targeted_members: MicrocampaignTargetedMember[];
};

// LOT 17 — Escalades judiciaires (phase D/E contentieux).
export type JudicialBien = {
  description: string;
  valeur_estimee: string | null;
};

export type JudicialStatut =
  | "en_instance"
  | "decision_rendue"
  | "executee"
  | "classee_sans_suite";

export type JudicialEscalationRow = {
  id: number;
  loan_id: number;
  loan_numero_dossier: string;
  member_id: number;
  member_numero: string;
  member_nom: string;
  statut: JudicialStatut;
  statut_display: string;
  declenche_at: string;
  declenche_par_id: number | null;
  declenche_mode: string;
  motif: string;
  documents_attaches: unknown[];
  decision_date: string | null;
  biens_saisissables: JudicialBien[];
  execution_date: string | null;
  montant_recouvre: string;
  biens_saisis: JudicialBien[];
  closed_at: string | null;
  close_reason: string;
  loan_solde_restant: string;
  loan_statut: string;
};

export type MicrocampaignCreateInput = {
  nom: string;
  profil_cible: string;
  date_debut: string;
  date_fin: string;
  montant_min: string | number;
  montant_max: string | number;
  taux_interet: string | number;
  nb_jours_recouvrement: number;
  plafond_beneficiaires?: number | null;
  membre_requis?: boolean;
  frais_etude_montant?: string | number | null;
  documents_requis?: string[];
};

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

  // Mot de passe oublie (flow OTP 6 chiffres par e-mail, memes endpoints que
  // le portail membre). Reponse etape 1 opaque (anti-enumeration).
  requestPasswordReset: (email: string) =>
    request<{ detail: string }>("/auth/password-reset/request/", {
      method: "POST",
      body: JSON.stringify({ email }),
    }),
  confirmPasswordReset: (payload: {
    email: string;
    code: string;
    new_password: string;
  }) =>
    request<{ detail: string }>("/auth/password-reset/confirm/", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

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
    // CH-6 — Approbation provisoire (comité) : en_instruction → approuvee_provisoire.
    decideProvisional: (id: number, payload: { avis_provisoire: string }) =>
      request<LoanRequest>(`/loans/requests/${id}/decide-provisional/`, {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    // CH-6 — Compte-rendu visite terrain (staff) : pose field_visit_outcome.
    fieldVisit: (
      id: number,
      payload: {
        outcome: "favorable" | "defavorable" | "a_revoir";
        note: string;
      },
    ) =>
      request<LoanRequest>(`/loans/requests/${id}/field-visit/`, {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    // L4 — Évaluation du bien mis en garantie (staff, NON bloquant, purement
    // informatif). La commission juge et approuve ensuite via decide().
    evaluateGuarantee: (
      id: number,
      payload: { valeur_estimee: number; note?: string },
    ) =>
      request<LoanRequest>(`/loans/requests/${id}/evaluate-guarantee/`, {
        method: "POST",
        body: JSON.stringify(payload),
      }),
  },

  loans: {
    list: (
      params: { statut?: string; q?: string; limit?: number; offset?: number } = {},
    ) =>
      request<Paginated<AdminLoanRow>>(
        `/loans/admin/list/${qs({
          statut: params.statut,
          q: params.q,
          limit: params.limit ? String(params.limit) : undefined,
          offset: params.offset ? String(params.offset) : undefined,
        })}`,
      ),
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
    // CH-9 — Décaissement « Payer maintenant » : auto-fill depuis le
    // moyen_reception choisi par le membre à la soumission. Pour
    // `agence_especes`, le payload doit fournir `reference_externe`.
    disburseNow: (
      loanId: number,
      payload?: { reference_externe?: string; note?: string },
    ) =>
      request<DisburseResponse & { moyen_reception: string }>(
        `/loans/admin/${loanId}/disburse-now/`,
        {
          method: "POST",
          body: JSON.stringify(payload ?? {}),
        },
      ),
    disbursementStatus: (loanId: number) =>
      request<LoanDisbursementStatus>(
        `/loans/admin/${loanId}/disbursement-status/`,
      ),
    // CH-9 — URL absolue pour télécharger la note PDF (membre + admin).
    noteUrl: (requestId: number) =>
      `${API_BASE}/loans/requests/${requestId}/note/`,
    // A1 . Detail credit pour drawer (echeances + historique remboursement).
    detail: (loanId: number) =>
      request<AdminLoanDetail>(`/loans/admin/${loanId}/detail/`),
    // A2 . Liste echeances filtrables (widget "Suivi paiement").
    listInstallments: (
      params: {
        statut?: string;
        member?: number;
        loan?: number;
        from?: string;
        to?: string;
        limit?: number;
        offset?: number;
      } = {},
    ) =>
      request<Paginated<AdminInstallmentRow>>(
        `/loans/admin/installments/${qs({
          statut: params.statut,
          member: params.member ? String(params.member) : undefined,
          loan: params.loan ? String(params.loan) : undefined,
          from: params.from,
          to: params.to,
          limit: params.limit ? String(params.limit) : undefined,
          offset: params.offset ? String(params.offset) : undefined,
        })}`,
      ),
  },

  members: {
    list: (
      params: {
        statut?: string;
        q?: string;
        reinscription_overdue?: string;
        reinscription_due_soon?: string;
        limit?: number;
        offset?: number;
      } = {},
    ) =>
      request<Paginated<Member>>(
        `/admin/members/${qs({
          statut: params.statut,
          q: params.q,
          reinscription_overdue: params.reinscription_overdue,
          reinscription_due_soon: params.reinscription_due_soon,
          limit: params.limit ? String(params.limit) : undefined,
          offset: params.offset ? String(params.offset) : undefined,
        })}`,
      ),
  },

  withdrawals: {
    list: (statut?: WithdrawalStatut) =>
      request<{ results: WithdrawalRow[] }>(
        `/admin/withdrawals/${statut ? `?statut=${statut}` : ""}`,
      ),
    decide: (id: number, payload: { decision: "approuvee" | "rejetee"; motif_rejet?: string }) =>
      request<WithdrawalRow>(`/admin/withdrawals/${id}/decide/`, {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    markPaid: (id: number, note?: string) =>
      request<WithdrawalRow>(`/admin/withdrawals/${id}/mark-paid/`, {
        method: "POST",
        body: JSON.stringify({ note: note ?? "" }),
      }),
    retryPayout: (id: number) =>
      request<WithdrawalRow>(`/admin/withdrawals/${id}/retry-payout/`, {
        method: "POST",
      }),
  },

  // Reconductions de crédit (Art.10/11) — le membre demande sur mobile/portail
  // (POST /loans/{id}/renewal/), l'admin décide ici.
  loanRenewals: {
    list: (statut?: LoanRenewalStatut) =>
      request<{ results: LoanRenewalRow[] }>(
        `/loans/admin/renewals/${statut ? `?statut=${statut}` : ""}`,
      ),
    decide: (
      id: number,
      payload: {
        decision: "approuvee" | "rejetee";
        taux_annuel?: number;
        date_premiere_echeance?: string;
        motif_rejet?: string;
      },
    ) =>
      request<Record<string, unknown>>(`/loans/renewals/${id}/decide/`, {
        method: "POST",
        body: JSON.stringify(payload),
      }),
  },

  // Édition rapide des articles vitrine (image de couverture) sans passer
  // par Wagtail. Le backend republie la page → revalidation ISR de la vitrine.
  cmsBlog: {
    list: (
      params: { locale?: "fr" | "en"; limit?: number; offset?: number; q?: string } = {},
    ) => {
      const sp = new URLSearchParams();
      if (params.locale) sp.set("locale", params.locale);
      if (params.limit != null) sp.set("limit", String(params.limit));
      if (params.offset != null) sp.set("offset", String(params.offset));
      if (params.q) sp.set("q", params.q);
      return request<AdminBlogPage>(`/cms/blog/?${sp.toString()}`);
    },
    setCoverImage: (pageId: number, file: File) => {
      const fd = new FormData();
      fd.append("image", file);
      return request<{ ok: boolean; cover_image_data: { url: string } | null }>(
        `/cms/blog/${pageId}/cover-image/`,
        { method: "POST", body: fd },
      );
    },
    setLive: (pageId: number, live: boolean) =>
      request<{ id: number; live: boolean }>(`/cms/blog/${pageId}/live/`, {
        method: "POST",
        body: JSON.stringify({ live }),
      }),
    comments: (pageId: number, params: { limit?: number; offset?: number } = {}) => {
      const sp = new URLSearchParams();
      if (params.limit != null) sp.set("limit", String(params.limit));
      if (params.offset != null) sp.set("offset", String(params.offset));
      return request<ArticleCommentsPage>(
        `/social/articles/${pageId}/comments/?${sp.toString()}`,
      );
    },
  },

  payments: {
    list: (
      params: {
        statut?: string;
        type?: string;
        q?: string;
        limit?: number;
        offset?: number;
      } = {},
    ) =>
      request<Paginated<PaymentRow>>(
        `/payments/admin/${qs({
          statut: params.statut,
          type: params.type,
          q: params.q,
          limit: params.limit ? String(params.limit) : undefined,
          offset: params.offset ? String(params.offset) : undefined,
        })}`,
      ),
    // B1 . Saisie versement agence (cash-in) par admin.
    // Cree Payment(source=MANUEL, statut=VALIDE) + execute hook business.
    cashIn: (payload: {
      member_id: number;
      type:
        | "frais_adhesion"
        | "frais_inscription"
        | "frais_carnet"
        | "frais_demande_credit"
        | "epargne"
        | "epargne_classique"
        | "remboursement";
      montant: number | string;
      reference_externe?: string;
      note?: string;
      loan_id?: number;
      nb_jours_couverts?: number;
      is_placement?: boolean;
      // D6 . Flag renouvellement annuel pour frais_carnet.
      is_renewal?: boolean;
    }) =>
      request<PaymentRow>("/payments/admin/cash-in/", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
  },

  // Refonte 2026 LOT 1 — Justificatifs BRC.
  brc: {
    list: (statut?: string) =>
      request<BRCDocument[]>(
        `/admin/brc/${statut ? `?statut=${statut}` : ""}`,
      ),
    validate: (id: number) =>
      request<BRCDocument>(`/admin/brc/${id}/validate/`, { method: "POST" }),
    reject: (id: number, motif: string) =>
      request<BRCDocument>(`/admin/brc/${id}/reject/`, {
        method: "POST",
        body: JSON.stringify({ motif }),
      }),
  },

  // Pipeline d'adhesion (vue funnel + KPIs + membres SUSPENDU avec
  // progression de paiement des 3 frais requis).
  adhesions: {
    pipeline: () => request<AdhesionPipeline>("/admin/adhesions/pipeline/"),
  },

  // Pilotage commandes carnet (Article 4 - payee . en_impression . delivree).
  booklet: {
    list: (statut?: string) =>
      request<{ results: BookletOrderAdmin[]; count: number }>(
        `/admin/booklet-orders/${statut ? `?statut=${statut}` : ""}`,
      ),
    markPrinting: (id: number) =>
      request<BookletOrderAdmin>(`/admin/booklet-orders/${id}/mark-printing/`, {
        method: "POST",
      }),
    markDelivered: (id: number) =>
      request<BookletOrderAdmin>(`/admin/booklet-orders/${id}/mark-delivered/`, {
        method: "POST",
      }),
    updateNotes: (id: number, notes: string) =>
      request<BookletOrderAdmin>(`/admin/booklet-orders/${id}/notes/`, {
        method: "PATCH",
        body: JSON.stringify({ notes_agence: notes }),
      }),
  },

  // Refonte 2026 LOT 5 — Renouvellements épargne classique.
  renewals: {
    list: (statut: string = "en_attente_paiement") =>
      request<Paginated<RenewalRow>>(`/savings/admin/renewals/?statut=${statut}`),
    process: (id: number, paid_amount?: number) =>
      request<{
        id: number;
        cycle_courant: number;
        statut_renouvellement: string;
        date_prochaine_maturite: string | null;
      }>(`/savings/admin/renewals/${id}/process/`, {
        method: "POST",
        body: JSON.stringify(paid_amount !== undefined ? { paid_amount } : {}),
      }),
  },

  // P2 — Tunables AppSettings refonte 2026 (BRC, ancienneté, eligibility,
  // seizure, judicial, etc.). Catalogue côté serveur (audit/tunables.py).
  appSettings: {
    list: () => request<AppSettingsResponse>("/audit/admin/settings/"),
    update: (key: string, value: string | number | boolean) =>
      request<AppSettingRow>(
        `/audit/admin/settings/${encodeURIComponent(key)}/`,
        {
          method: "PATCH",
          body: JSON.stringify({ value }),
        },
      ),
  },

  // LOT 16 — Campagnes micro-crédit (voie 3).
  campaigns: {
    list: (
      params: { actif?: "true" | "false"; profil_cible?: string; is_open?: "true" } = {},
    ) =>
      request<Paginated<MicrocampaignRow>>(`/loans/admin/campaigns/${qs(params)}`),
    create: (payload: MicrocampaignCreateInput, flyer?: File | null) => {
      if (flyer) {
        const form = new FormData();
        Object.entries(payload).forEach(([k, v]) => {
          if (v === undefined || v === null) return;
          // Les tableaux/objets (ex. documents_requis) sont sérialisés en JSON
          // pour que le backend (JSONField) les relise correctement en multipart.
          form.append(k, typeof v === "object" ? JSON.stringify(v) : String(v));
        });
        form.append("flyer", flyer);
        return request<MicrocampaignRow>("/loans/admin/campaigns/", {
          method: "POST",
          body: form,
        });
      }
      return request<MicrocampaignRow>("/loans/admin/campaigns/", {
        method: "POST",
        body: JSON.stringify(payload),
      });
    },
    addTargeted: (
      campaignId: number,
      payload: { member_ids?: number[]; numeros_membre?: string[] },
    ) =>
      request<MicrocampaignTargetedAddResponse>(
        `/loans/admin/campaigns/${campaignId}/targeted/`,
        { method: "POST", body: JSON.stringify(payload) },
      ),
    removeTargeted: (campaignId: number, memberId: number) =>
      request<{ removed: boolean; targeted_count: number }>(
        `/loans/admin/campaigns/${campaignId}/targeted/${memberId}/`,
        { method: "DELETE" },
      ),
    detail: (id: number) =>
      request<MicrocampaignDetail>(`/loans/admin/campaigns/${id}/`),
    close: (id: number, reason?: string) =>
      request<MicrocampaignRow>(`/loans/admin/campaigns/${id}/close/`, {
        method: "PATCH",
        body: JSON.stringify(reason ? { reason } : {}),
      }),
    decideRequest: (
      requestId: number,
      payload: { decision: "valide" } | { decision: "rejete"; motif_rejet: string },
    ) =>
      request<{
        id: number;
        statut: string;
        campaign_id: number | null;
        motif_rejet?: string;
        message: string;
      }>(`/loans/admin/requests/${requestId}/campaign-decide/`, {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    // 2026 — Candidatures visiteurs (non-membres) d'une campagne.
    applications: (campaignId: number, statut?: string) =>
      request<{ count: number; results: CampaignApplicationRow[] }>(
        `/loans/admin/campaigns/${campaignId}/applications/${qs(statut ? { statut } : {})}`,
      ),
    decideApplication: (
      applicationId: number,
      payload:
        | { decision: "accepte" }
        | { decision: "rejete"; motif_rejet: string },
    ) =>
      request<{
        id: number;
        statut: string;
        member_id?: number | null;
        loan_request_id?: number | null;
        message?: string;
      }>(`/loans/admin/campaign-applications/${applicationId}/decide/`, {
        method: "POST",
        body: JSON.stringify(payload),
      }),
  },

  // LOT 17 — Escalades judiciaires (phase D/E contentieux).
  escalations: {
    list: (
      params: {
        statut?: JudicialStatut;
        open?: "true";
        member?: string;
        q?: string;
      } = {},
    ) =>
      request<Paginated<JudicialEscalationRow>>(
        `/loans/admin/escalations/${qs(params as Record<string, string | undefined>)}`,
      ),
    detail: (id: number) =>
      request<JudicialEscalationRow>(`/loans/admin/escalations/${id}/`),
    open: (loanId: number, payload: { motif: string; mode?: string }) =>
      request<JudicialEscalationRow>(
        `/loans/admin/loans/${loanId}/escalation/`,
        { method: "POST", body: JSON.stringify(payload) },
      ),
    decision: (
      id: number,
      payload: { decision_date: string; biens_saisissables: JudicialBien[] },
    ) =>
      request<JudicialEscalationRow>(
        `/loans/admin/escalations/${id}/decision/`,
        { method: "POST", body: JSON.stringify(payload) },
      ),
    execution: (
      id: number,
      payload: {
        execution_date: string;
        montant_recouvre: string | number;
        biens_saisis: JudicialBien[];
      },
    ) =>
      request<JudicialEscalationRow>(
        `/loans/admin/escalations/${id}/execution/`,
        { method: "POST", body: JSON.stringify(payload) },
      ),
    classer: (id: number, motif: string) =>
      request<JudicialEscalationRow>(
        `/loans/admin/escalations/${id}/classer/`,
        { method: "POST", body: JSON.stringify({ motif }) },
      ),
  },

  // Cron schedules — édition cadence + run-now + reset (recette).
  cronSchedules: {
    list: () =>
      request<{
        results: CronScheduleRow[];
        presets: Record<string, string>;
      }>("/audit/admin/cron-schedules/"),
    update: (name: string, cron: string) =>
      request<CronScheduleRow>(
        `/audit/admin/cron-schedules/${encodeURIComponent(name)}/`,
        { method: "PATCH", body: JSON.stringify({ cron }) },
      ),
    runNow: (name: string) =>
      request<{
        name: string;
        executed_at: string;
        summary: Record<string, unknown>;
      }>(
        `/audit/admin/cron-schedules/${encodeURIComponent(name)}/run-now/`,
        { method: "POST" },
      ),
    resetDefaults: () =>
      request<{
        restored: Array<{ name: string; from: string; to: string }>;
        count: number;
      }>("/audit/admin/cron-schedules/reset-defaults/", { method: "POST" }),
  },

  // CooperativeAsset — règlement intérieur PDF (singleton).
  cooperativeAsset: {
    get: () =>
      request<{
        reglement_interieur: {
          uploaded: boolean;
          url: string | null;
          name: string | null;
          size: number;
          uploaded_at: string | null;
          uploaded_by: string | null;
        };
      }>("/audit/admin/cooperative-asset/"),
    uploadReglement: (file: File) => {
      // Upload multipart . le wrapper request() gere FormData + CSRF + auto-recovery.
      const form = new FormData();
      form.append("file", file);
      return request<unknown>(
        "/audit/admin/cooperative-asset/reglement/",
        { method: "POST", body: form },
      );
    },
  },

  // Annonces broadcast — admin diffuse un message libre aux membres,
  // matérialisé en Notification in-app par cible.
  announcements: {
    list: () =>
      request<{ results: AnnouncementRow[] }>(
        "/notifications/admin/announcements/",
      ),
    create: (payload: AnnouncementCreatePayload) => {
      // Si une image est jointe, on passe en multipart . sinon JSON classique.
      if (payload.image) {
        const fd = new FormData();
        fd.append("titre", payload.titre);
        fd.append("corps", payload.corps);
        fd.append("audience", payload.audience);
        if (payload.audience_member_ids) {
          for (const id of payload.audience_member_ids) {
            fd.append("audience_member_ids", String(id));
          }
        }
        if (payload.lien) fd.append("lien", payload.lien);
        if (payload.expires_at) fd.append("expires_at", payload.expires_at);
        fd.append("image", payload.image);
        return request<AnnouncementRow>(
          "/notifications/admin/announcements/create/",
          { method: "POST", body: fd },
        );
      }
      return request<AnnouncementRow>(
        "/notifications/admin/announcements/create/",
        { method: "POST", body: JSON.stringify(payload) },
      );
    },
    remove: (id: number) =>
      request<void>(`/notifications/admin/announcements/${id}/`, {
        method: "DELETE",
      }),
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

  // CH-4 — Moteur FormSchema (admin CRUD + activate + duplicate).
  forms: {
    list: (kind?: FormSchemaKind) =>
      request<FormSchemaAdmin[]>(
        `/forms/admin/schemas/${kind ? `?kind=${kind}` : ""}`,
      ),
    detail: (id: number) =>
      request<FormSchemaAdmin>(`/forms/admin/schemas/${id}/`),
    create: (payload: {
      kind: FormSchemaKind;
      title: string;
      description?: string;
      schema: FormSchemaJSON;
      notes_admin?: string;
    }) =>
      request<FormSchemaAdmin>(`/forms/admin/schemas/`, {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    update: (id: number, payload: Partial<{
      title: string;
      description: string;
      schema: FormSchemaJSON;
      notes_admin: string;
    }>) =>
      request<FormSchemaAdmin>(`/forms/admin/schemas/${id}/`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      }),
    delete: (id: number) =>
      request<void>(`/forms/admin/schemas/${id}/`, { method: "DELETE" }),
    activate: (id: number) =>
      request<FormSchemaAdmin>(`/forms/admin/schemas/${id}/activate/`, {
        method: "POST",
      }),
    duplicate: (id: number) =>
      request<FormSchemaAdmin>(`/forms/admin/schemas/${id}/duplicate/`, {
        method: "POST",
      }),
  },

  // Journal d'audit centralise (toutes les actions tracees).
  audit: {
    list: (filters: AuditLogFilters = {}) =>
      request<AuditLogPage>(
        `/audit/admin/logs/${qs({
          q: filters.q,
          user: filters.user,
          action: filters.action,
          entite_type: filters.entite_type,
          entite_id: filters.entite_id,
          date_from: filters.date_from,
          date_to: filters.date_to,
          limit: filters.limit ? String(filters.limit) : undefined,
          offset: filters.offset ? String(filters.offset) : undefined,
        })}`,
      ),
    facets: () => request<AuditLogFacets>("/audit/admin/logs/facets/"),
  },

  // Commentaires sur articles / campagnes — moderation staff (hide/unhide).
  social: {
    comments: {
      list: (filters: SocialCommentsFilters = {}) =>
        request<SocialCommentsPage>(
          `/social/admin/comments/${qs({
            q: filters.q,
            hidden: filters.hidden,
            content_type: filters.content_type,
            limit: filters.limit ? String(filters.limit) : undefined,
            offset: filters.offset ? String(filters.offset) : undefined,
          })}`,
        ),
      hide: (id: number, reason: string) =>
        request<SocialCommentRow>(
          `/social/admin/comments/${id}/hide/`,
          {
            method: "POST",
            body: JSON.stringify({ reason }),
          },
        ),
      unhide: (id: number) =>
        request<SocialCommentRow>(
          `/social/admin/comments/${id}/unhide/`,
          { method: "POST" },
        ),
    },
  },

  // LA-1..3 . Pool de tranches preteur (epargne placement).
  // L'admin pilote le funding manuel d'un credit en cherry-pickant
  // les tranches DISPONIBLE des membres preteur.
  lenderTranches: {
    list: (params: {
      statut?: "disponible" | "engagee" | "liberee" | "annulee" | "all";
      member_id?: number;
      q?: string;
      montant_min?: number;
      montant_max?: number;
    } = {}) => {
      const qs = new URLSearchParams();
      if (params.statut) qs.set("statut", params.statut);
      if (params.member_id) qs.set("member_id", String(params.member_id));
      if (params.q) qs.set("q", params.q);
      if (params.montant_min) qs.set("montant_min", String(params.montant_min));
      if (params.montant_max) qs.set("montant_max", String(params.montant_max));
      const suffix = qs.toString() ? `?${qs}` : "";
      return request<LenderTranchesListResponse>(
        `/loans/admin/lender-tranches/${suffix}`,
      );
    },
    summary: () =>
      request<LenderPoolSummary>("/loans/admin/lender-tranches/summary/"),
    composeFunding: (
      loanId: number,
      payload: { selections: Array<{ tranche_id: number; montant: string }> },
    ) =>
      request<LenderFundingComposeResponse>(
        `/loans/admin/${loanId}/funding-manual/`,
        { method: "POST", body: JSON.stringify(payload) },
      ),
  },

  // RBAC — Utilisateurs & accès (staff + rôles/ressources).
  access: {
    resources: () =>
      request<{ results: AccessResource[] }>("/admin/access/resources/"),
    listRoles: () => request<{ results: StaffRole[] }>("/admin/access/roles/"),
    createRole: (payload: {
      name: string;
      description?: string;
      resources: string[];
    }) =>
      request<StaffRole>("/admin/access/roles/", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    updateRole: (
      id: number,
      payload: Partial<{ name: string; description: string; resources: string[] }>,
    ) =>
      request<StaffRole>(`/admin/access/roles/${id}/`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      }),
    deleteRole: (id: number) =>
      request<void>(`/admin/access/roles/${id}/`, { method: "DELETE" }),
    listUsers: () => request<{ results: StaffUser[] }>("/admin/access/users/"),
    createUser: (payload: {
      email: string;
      first_name?: string;
      last_name?: string;
      password?: string;
      group?: string;
      role_ids?: number[];
    }) =>
      request<StaffUser>("/admin/access/users/", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    updateUser: (
      id: number,
      payload: Partial<{
        first_name: string;
        last_name: string;
        is_active: boolean;
        group: string;
        role_ids: number[];
        reset_password: boolean;
      }>,
    ) =>
      request<StaffUser>(`/admin/access/users/${id}/`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      }),
    deactivateUser: (id: number) =>
      request<StaffUser>(`/admin/access/users/${id}/`, { method: "DELETE" }),
  },
};

// LA-1 . Types pool preteur.
export type LenderTranche = {
  id: number;
  member: {
    id: number;
    numero_membre: string;
    nom: string;
    prenom: string;
    email: string;
  };
  montant: string;
  statut: "disponible" | "engagee" | "liberee" | "annulee";
  statut_display: string;
  engaged_in_loan_id: number | null;
  engaged_in_loan_dossier: string | null;
  engaged_at: string | null;
  released_at: string | null;
  created_at: string;
};

export type LenderTranchesListResponse = {
  items: LenderTranche[];
  count: number;
};

export type LenderPoolSummary = {
  disponible: { n: number; total: string };
  engagee: { n: number; total: string };
  liberee: { n: number; total: string };
  annulee: { n: number; total: string };
};

export type LenderFundingComposeResponse = {
  status: "ok";
  loan_id: number;
  loan_dossier: string;
  n_tranches_engagees: number;
  n_tranches_splittees: number;
  total_engage: string;
  capital_loan: string;
  reste_a_couvrir: string;
};

// CH-4 — Types FormSchema (admin).
export type FormSchemaKind = "adhesion" | "loan_request" | "loan_renewal";

export type FormFieldType =
  | "text" | "email" | "tel" | "number" | "textarea"
  | "select" | "radio" | "checkbox" | "file" | "date";

export type FormFieldCondition = {
  field: string;
  operator: "equals" | "not_equals" | "in";
  value: unknown;
};

export type FormFieldOption = { value: string; label: string };

export type FormField = {
  id: string;
  type: FormFieldType;
  label: string;
  required?: boolean;
  placeholder?: string;
  help_text?: string;
  max_length?: number;
  min?: number;
  max?: number;
  accept?: string;
  max_size_mb?: number;
  options?: FormFieldOption[];
  condition?: FormFieldCondition;
  is_locked?: boolean;
};

export type FormSection = {
  id: string;
  title: string;
  description?: string;
  fields: FormField[];
};

export type FormSchemaJSON = { sections: FormSection[] };

export type FormSchemaAdmin = {
  id: number;
  kind: FormSchemaKind;
  kind_display: string;
  version: number;
  title: string;
  description: string;
  schema: FormSchemaJSON;
  is_active: boolean;
  activated_at: string | null;
  activated_by_name: string | null;
  notes_admin: string;
  created_at: string;
  updated_at: string;
};
