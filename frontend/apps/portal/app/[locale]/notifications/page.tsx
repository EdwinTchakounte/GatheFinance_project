"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { Container, buttonClasses } from "@gathe/ui";

import {
  portalApi,
  type ApiError,
  type PortalNotification,
} from "@/lib/api";


type NotifKind =
  | "savings"
  | "loan"
  | "payment"
  | "lender"
  | "announcement"
  | "support"
  | "system";


function kindFromType(type: string): NotifKind {
  if (type === "annonce" || type.startsWith("annonce.")) return "announcement";
  // lender.* couvre tranche engagee / interets percus / etc.
  if (type.startsWith("lender")) return "lender";
  if (type.startsWith("savings") || type.startsWith("withdrawal")) return "savings";
  if (type.startsWith("loan") || type.startsWith("repayment")) return "loan";
  if (type.startsWith("payment")) return "payment";
  if (type.startsWith("support")) return "support";
  return "system";
}

// Ordre stable des catégories (onglets dynamiques + rendu).
const KIND_ORDER: NotifKind[] = [
  "savings",
  "loan",
  "payment",
  "lender",
  "announcement",
  "support",
  "system",
];


function splitAnnouncement(message: string): { title: string; body: string } {
  const parts = message.split(/\n\n+/);
  const first = parts[0] ?? "";
  if (parts.length >= 2 && first.trim()) {
    return {
      title: first.trim(),
      body: parts.slice(1).join("\n\n").trim(),
    };
  }
  return { title: "Annonce", body: message };
}


// Libellés FR par type d'événement — parité avec le mobile
// (notifications_dio_datasource.dart). Le backend ne renvoie que le `type` ;
// sans cette table le portail « humanisait » le slug anglais (« Loan Approved »).
const NOTIF_TITLES_FR: Record<string, string> = {
  "booklet.ordered": "Carnet commandé",
  "campaign.created": "Nouvelle campagne",
  "collecte.balance_swept_to_savings": "Collecte versée sur l'épargne",
  "collecte.eom_choice_reminder": "Collecte : choix de fin de mois",
  "collecte.monthly_restitution": "Restitution de collecte",
  "lender.apport_restitution": "Restitution de votre apport",
  "lender.interest_paid": "Intérêts de prêteur crédités",
  "lender.interest_paid_at_source": "Intérêts de prêteur crédités",
  "lender.tranche_engaged": "Tranche engagée",
  "lender.tranche_released": "Tranche libérée",
  "loan.approved": "Crédit approuvé",
  "loan.avaliste_consent_accepted": "Avaliste : engagement accepté",
  "loan.avaliste_consent_refused": "Avaliste : engagement refusé",
  "loan.avaliste_consent_requested": "Demande de garantie (avaliste)",
  "loan.avaliste_gel_released": "Garantie libérée",
  "loan.biens_seized": "Saisie de biens",
  "loan.closed": "Crédit soldé",
  "loan.credit_dossier_ready": "Dossier de crédit prêt",
  "loan.disbursed": "Crédit décaissé",
  "loan.installment_due_soon": "Échéance à venir",
  "loan.installment_overdue": "Échéance en retard",
  "loan.judicial_escalation_opened": "Escalade judiciaire ouverte",
  "loan.notice": "Information crédit",
  "loan.penalite_globale_appliquee": "Pénalité appliquée",
  "loan.poursuite_engaged": "Poursuite engagée",
  "loan_renewal.approved": "Reconduction approuvée",
  "loan_renewal.rejected": "Reconduction rejetée",
  "loan_renewal.requested": "Reconduction demandée",
  "loan.repayment_confirmed": "Remboursement confirmé",
  "loan_request.fees_paid": "Frais d'étude payés",
  "loan_request.rejected": "Demande de crédit rejetée",
  "loan_request.submitted": "Demande de crédit envoyée",
  "loan.savings_seized": "Saisie sur épargne",
  "member.activated": "Compte activé",
  "member.brc_document_uploaded": "Justificatif BRC reçu",
  "member.brc_rejected": "Justificatif BRC rejeté",
  "member.brc_validated": "Justificatif BRC validé",
  "member.reinscription_confirmed": "Réinscription confirmée",
  "member.reinscription_due": "Réinscription à échéance",
  "member.reinscription_due_today": "Réinscription à régler aujourd'hui",
  "member.reinscription_due_urgent": "Réinscription urgente",
  "member.reinscription_expired_suspended": "Compte suspendu (réinscription)",
  "member.rejected": "Demande d'adhésion rejetée",
  "membership.archived_for_non_renewal": "Adhésion archivée",
  "membership.interview_scheduled": "Entretien programmé",
  "member.welcome": "Bienvenue",
  "microcampaign.closed": "Campagne clôturée",
  "placement.matured": "Placement arrivé à terme",
  "savings.deposit_confirmed": "Dépôt confirmé",
  "savings.interest_credited": "Intérêts d'épargne crédités",
  "savings.maturity_reached": "Épargne arrivée à maturité",
  "savings.renewed": "Épargne renouvelée",
  "withdrawal.admin_pending": "Retrait à traiter",
  "withdrawal.approved": "Retrait approuvé",
  "withdrawal.completed": "Retrait effectué",
  "withdrawal.rejected": "Retrait rejeté",
  "withdrawal.requested": "Retrait demandé",
};

const PAYMENT_KIND_FR: Record<string, string> = {
  epargne: "épargne",
  epargne_classique: "épargne",
  frais_inscription: "frais d'inscription",
  frais_adhesion: "frais d'adhésion",
  frais_demande_credit: "frais de demande de crédit",
  frais_reconduction: "frais de reconduction",
  frais_carnet: "frais de carnet",
  remboursement: "remboursement",
  decaissement: "décaissement",
};

function titleFromType(type: string): string {
  if (!type) return "Notification";

  // Clés paiement dynamiques : payment.confirmed.<kind>, .rejected., .initiated.
  if (type.startsWith("payment.")) {
    const segs = type.split(".");
    const actions: Record<string, string> = {
      confirmed: "Paiement confirmé",
      rejected: "Paiement rejeté",
      initiated: "Paiement initié",
    };
    const evt = segs[1];
    const kindKey = segs[2];
    const action = evt ? actions[evt] : undefined;
    const kind = kindKey ? PAYMENT_KIND_FR[kindKey] : undefined;
    if (action) return kind ? `${action} — ${kind}` : action;
  }

  const mapped = NOTIF_TITLES_FR[type];
  if (mapped) return mapped;

  // Repli lisible (type inconnu) : dernier segment humanisé.
  const seg = type.split(".").pop() ?? type;
  return seg
    .split(/[._]/)
    .map((p) => (p ? (p[0] ?? "").toUpperCase() + p.slice(1) : p))
    .join(" ");
}


const KIND_META: Record<NotifKind, { label: string; tint: string; ring: string }> = {
  savings: {
    label: "Épargne",
    tint: "bg-emerald-50 text-emerald-700",
    ring: "ring-emerald-200",
  },
  loan: {
    label: "Crédit",
    tint: "bg-teal-50 text-teal-700",
    ring: "ring-teal-200",
  },
  payment: {
    label: "Paiement",
    tint: "bg-slate-50 text-slate-700",
    ring: "ring-slate-200",
  },
  lender: {
    label: "Prêteur",
    tint: "bg-emerald-50 text-emerald-800",
    ring: "ring-emerald-300",
  },
  announcement: {
    label: "Annonce",
    tint: "bg-blue-50 text-blue-700",
    ring: "ring-blue-200",
  },
  support: {
    label: "Support",
    tint: "bg-teal-50 text-teal-700",
    ring: "ring-teal-200",
  },
  system: {
    label: "Notification",
    tint: "bg-amber-50 text-amber-700",
    ring: "ring-amber-200",
  },
};


function fmtRelative(iso: string): string {
  try {
    const d = new Date(iso);
    const diffMin = (Date.now() - d.getTime()) / 60_000;
    if (diffMin < 1) return "à l'instant";
    if (diffMin < 60) return `il y a ${Math.floor(diffMin)} min`;
    if (diffMin < 60 * 24) return `il y a ${Math.floor(diffMin / 60)} h`;
    return d.toLocaleDateString("fr-FR", {
      day: "2-digit",
      month: "short",
      year: "numeric",
    });
  } catch {
    return iso;
  }
}


export default function PortalNotificationsPage() {
  const router = useRouter();
  const [items, setItems] = useState<PortalNotification[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  // Filtre catégorie (null = Tout). Onglets DYNAMIQUES : seules les catégories
  // réellement présentes s'affichent (parité mobile).
  const [filter, setFilter] = useState<NotifKind | null>(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      portalApi.primeCsrf().catch(() => undefined);
      const res = await portalApi.notifications.list();
      setItems(res.results);
      setUnreadCount(res.unread_count);
    } catch (err) {
      const apiErr = err as ApiError;
      if (apiErr.status === 401 || apiErr.status === 403) {
        router.replace("/connexion");
        return;
      }
      setError(apiErr.detail ?? "Impossible de charger les notifications.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function onMarkRead(notif: PortalNotification) {
    if (notif.lue) return;
    try {
      const updated = await portalApi.notifications.markRead(notif.id);
      setItems((prev) =>
        prev.map((n) => (n.id === notif.id ? updated : n)),
      );
      setUnreadCount((c) => Math.max(0, c - 1));
    } catch {
      /* swallow — silent retry on next refresh */
    }
  }

  async function onMarkAllRead() {
    if (unreadCount === 0) return;
    try {
      await portalApi.notifications.markAllRead();
      setItems((prev) => prev.map((n) => ({ ...n, lue: true })));
      setUnreadCount(0);
    } catch {
      /* swallow */
    }
  }

  const present = KIND_ORDER.filter((k) =>
    items.some((n) => kindFromType(n.type) === k),
  );
  const active = filter && present.includes(filter) ? filter : null;
  const visible = active
    ? items.filter((n) => kindFromType(n.type) === active)
    : items;

  return (
    <main className="min-h-[60vh] py-10">
      <Container width="content">
        <header className="mb-6 flex items-end justify-between gap-4">
          <div className="space-y-1">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-terra-600">
              Espace membre
            </p>
            <h1 className="font-display text-3xl text-ink-900">
              Notifications
            </h1>
            <p className="text-sm text-ink-500">
              Activité de ton compte + annonces de la coopérative.
            </p>
            <button
              type="button"
              onClick={() => router.push("/annonces")}
              className="inline-flex items-center gap-1 text-sm font-medium text-terra-700 hover:underline"
            >
              Voir toutes les annonces →
            </button>
          </div>
          {unreadCount > 0 ? (
            <button
              type="button"
              onClick={onMarkAllRead}
              className={buttonClasses({ variant: "secondary", size: "sm" })}
            >
              Tout marquer comme lu ({unreadCount})
            </button>
          ) : null}
        </header>

        {error ? (
          <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">
            {error}
          </div>
        ) : null}

        {present.length > 1 ? (
          <div className="mb-5 flex flex-wrap gap-2">
            {([null, ...present] as (NotifKind | null)[]).map((k) => {
              const selected = k === active;
              const label = k === null ? "Tout" : KIND_META[k].label;
              return (
                <button
                  key={k ?? "all"}
                  type="button"
                  onClick={() => setFilter(k)}
                  className={[
                    "rounded-full px-3.5 py-1.5 text-xs font-semibold transition",
                    selected
                      ? "bg-teal-600 text-white"
                      : "border border-ink-200 bg-paper text-ink-600 hover:border-ink-300",
                  ].join(" ")}
                >
                  {label}
                </button>
              );
            })}
          </div>
        ) : null}

        {loading ? (
          <ul className="space-y-3">
            {[0, 1, 2].map((i) => (
              <li
                key={i}
                className="h-24 animate-pulse rounded-2xl border border-ink-100 bg-paper"
              />
            ))}
          </ul>
        ) : items.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-ink-200 bg-cream p-10 text-center">
            <p className="font-display text-lg text-ink-900">
              Aucune notification
            </p>
            <p className="mt-1 text-sm text-ink-500">
              Tu seras averti·e ici dès qu&apos;une opération est validée ou
              que la coopérative publie une annonce.
            </p>
          </div>
        ) : (
          <ul className="space-y-3">
            {visible.map((notif) => (
              <NotifCard
                key={notif.id}
                notif={notif}
                onClick={() => onMarkRead(notif)}
              />
            ))}
          </ul>
        )}
      </Container>
    </main>
  );
}


function NotifCard({
  notif,
  onClick,
}: {
  notif: PortalNotification;
  onClick: () => void;
}) {
  const kind = kindFromType(notif.type);
  const meta = KIND_META[kind];

  const { title, body } =
    kind === "announcement"
      ? splitAnnouncement(notif.message)
      : { title: titleFromType(notif.type), body: notif.message };

  const isUnread = !notif.lue;

  return (
    <li>
      <button
        type="button"
        onClick={onClick}
        className={[
          "block w-full rounded-2xl border bg-paper p-5 text-left transition",
          isUnread
            ? `border-ink-100 ring-1 ${meta.ring} shadow-sm`
            : "border-ink-100 opacity-80",
        ].join(" ")}
      >
        <div className="flex items-start justify-between gap-4">
          <div className="space-y-2">
            <div className="flex flex-wrap items-center gap-2">
              <span
                className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${meta.tint}`}
              >
                {meta.label}
              </span>
              {isUnread ? (
                <span
                  className="inline-block size-2 rounded-full bg-cobalt"
                  aria-label="Non lue"
                />
              ) : null}
            </div>
            <p
              className={`font-display text-base text-ink-900 ${
                isUnread ? "font-semibold" : ""
              }`}
            >
              {title}
            </p>
            <p className="whitespace-pre-wrap text-sm text-ink-600">{body}</p>
          </div>
          <span className="shrink-0 text-xs text-ink-400">
            {fmtRelative(notif.created_at)}
          </span>
        </div>
      </button>
    </li>
  );
}
