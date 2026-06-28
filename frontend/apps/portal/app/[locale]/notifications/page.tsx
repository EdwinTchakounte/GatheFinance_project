"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { Container, buttonClasses } from "@gathe/ui";

import {
  portalApi,
  type ApiError,
  type PortalNotification,
} from "@/lib/api";


type NotifKind = "savings" | "loan" | "payment" | "lender" | "announcement" | "system";


function kindFromType(type: string): NotifKind {
  if (type === "annonce" || type.startsWith("annonce.")) return "announcement";
  // lender.* couvre tranche engagee / interets percus / etc.
  if (type.startsWith("lender")) return "lender";
  if (type.startsWith("savings") || type.startsWith("withdrawal")) return "savings";
  if (type.startsWith("loan") || type.startsWith("repayment")) return "loan";
  if (type.startsWith("payment")) return "payment";
  return "system";
}


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


function titleFromType(type: string): string {
  if (!type) return "Notification";
  return type
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
            {items.map((notif) => (
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
