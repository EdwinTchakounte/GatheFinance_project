"use client";

import { useEffect, useState } from "react";
import {
  Megaphone,
  Send,
  Trash2,
  Users,
  UserCheck,
  UserX,
  ListChecks,
  AlertCircle,
  CheckCircle2,
} from "lucide-react";

import { buttonClasses } from "@gathe/ui";

import {
  adminApi,
  type AnnouncementAudience,
  type AnnouncementRow,
  type ApiError,
} from "@/lib/api";


const AUDIENCE_LABEL: Record<AnnouncementAudience, string> = {
  all: "Tous les membres",
  actifs: "Membres actifs uniquement",
  suspendus: "Membres suspendus uniquement",
  selection: "Sélection manuelle (ids)",
};

const AUDIENCE_ICON: Record<AnnouncementAudience, typeof Users> = {
  all: Users,
  actifs: UserCheck,
  suspendus: UserX,
  selection: ListChecks,
};


export default function AnnouncementsPage() {
  const [rows, setRows] = useState<AnnouncementRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState<{
    tone: "ok" | "err";
    text: string;
  } | null>(null);

  async function reload() {
    setLoading(true);
    try {
      const data = await adminApi.announcements.list();
      setRows(data.results);
    } catch (err) {
      const apiErr = err as ApiError;
      setMessage({
        tone: "err",
        text: apiErr.detail ?? "Chargement impossible.",
      });
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    adminApi.primeCsrf().catch(() => undefined);
    reload();
  }, []);

  async function onDelete(row: AnnouncementRow) {
    if (
      !window.confirm(
        `Supprimer l'annonce "${row.titre}" ? Les notifications déjà reçues par les membres sont conservées.`,
      )
    ) {
      return;
    }
    try {
      await adminApi.announcements.remove(row.id);
      setMessage({ tone: "ok", text: "Annonce supprimée." });
      await reload();
    } catch (err) {
      const apiErr = err as ApiError;
      setMessage({
        tone: "err",
        text: apiErr.detail ?? "Suppression impossible.",
      });
    }
  }

  return (
    <section className="space-y-6">
      <header className="space-y-1">
        <h1 className="font-display text-2xl text-ink-900">
          Annonces broadcast
        </h1>
        <p className="max-w-2xl text-sm text-ink-500">
          Diffuse un message à tous les membres ou à un sous-ensemble. Chaque
          membre cible reçoit une notification in-app (mobile + portail). Idéal
          pour les communications exceptionnelles (fermeture, AG, nouvelle
          campagne…).
        </p>
      </header>

      {message ? (
        <div
          className={`flex items-center gap-2 rounded-2xl border px-4 py-3 text-sm ${
            message.tone === "ok"
              ? "border-emerald-200 bg-emerald-50 text-emerald-800"
              : "border-rose-200 bg-rose-50 text-rose-800"
          }`}
        >
          {message.tone === "ok" ? (
            <CheckCircle2 className="size-4 shrink-0" />
          ) : (
            <AlertCircle className="size-4 shrink-0" />
          )}
          <span>{message.text}</span>
        </div>
      ) : null}

      <CreateForm
        onCreated={(created) => {
          setRows((prev) => [created, ...prev]);
          setMessage({
            tone: "ok",
            text: `Annonce diffusée à ${created.recipients_count} membre(s).`,
          });
        }}
        onError={(text) => setMessage({ tone: "err", text })}
      />

      <section className="space-y-3">
        <h2 className="font-display text-lg text-ink-900">
          Historique ({rows.length})
        </h2>
        {loading ? (
          <p className="text-sm text-ink-500">Chargement…</p>
        ) : rows.length === 0 ? (
          <p className="rounded-2xl border border-dashed border-ink-200 bg-cream p-8 text-center text-sm text-ink-500">
            Aucune annonce diffusée pour l&apos;instant.
          </p>
        ) : (
          <ul className="space-y-3">
            {rows.map((row) => (
              <AnnouncementCard
                key={row.id}
                row={row}
                onDelete={() => onDelete(row)}
              />
            ))}
          </ul>
        )}
      </section>
    </section>
  );
}


function CreateForm({
  onCreated,
  onError,
}: {
  onCreated: (row: AnnouncementRow) => void;
  onError: (text: string) => void;
}) {
  const [titre, setTitre] = useState("");
  const [corps, setCorps] = useState("");
  const [audience, setAudience] = useState<AnnouncementAudience>("all");
  const [memberIdsRaw, setMemberIdsRaw] = useState("");
  const [lien, setLien] = useState("");
  const [image, setImage] = useState<File | null>(null);
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const [sending, setSending] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (titre.trim().length === 0 || corps.trim().length === 0) {
      onError("Le titre et le corps sont obligatoires.");
      return;
    }

    let memberIds: number[] | undefined;
    if (audience === "selection") {
      const parsed = memberIdsRaw
        .split(/[,\s]+/)
        .map((s) => s.trim())
        .filter(Boolean)
        .map((s) => Number(s))
        .filter((n) => Number.isInteger(n) && n > 0);
      if (parsed.length === 0) {
        onError(
          "Sélection manuelle : merci de saisir au moins un identifiant membre numérique.",
        );
        return;
      }
      memberIds = parsed;
    }

    setSending(true);
    try {
      const created = await adminApi.announcements.create({
        titre: titre.trim(),
        corps: corps.trim(),
        audience,
        audience_member_ids: memberIds,
        lien: lien.trim() || undefined,
        image: image ?? undefined,
      });
      onCreated(created);
      setTitre("");
      setCorps("");
      setLien("");
      setMemberIdsRaw("");
      setAudience("all");
      setImage(null);
      setImagePreview(null);
    } catch (err) {
      const apiErr = err as ApiError;
      onError(apiErr.detail ?? "Diffusion impossible.");
    } finally {
      setSending(false);
    }
  }

  return (
    <form
      onSubmit={submit}
      className="space-y-4 rounded-3xl border border-ink-100 bg-paper p-6 shadow-sm"
    >
      <div className="flex items-center gap-2">
        <Megaphone className="size-5 text-cobalt" />
        <h2 className="font-display text-lg text-ink-900">
          Nouvelle annonce
        </h2>
      </div>

      <div className="grid gap-2">
        <label htmlFor="titre" className="text-sm font-medium text-ink-700">
          Titre <span className="text-rose-500">*</span>
        </label>
        <input
          id="titre"
          type="text"
          required
          maxLength={200}
          value={titre}
          onChange={(e) => setTitre(e.target.value)}
          placeholder="Ex. : Fermeture exceptionnelle vendredi 12 juin"
          className="rounded-xl border border-ink-200 bg-paper px-3 py-2 text-sm text-ink-900 outline-none focus:border-cobalt focus:ring-2 focus:ring-cobalt/20"
        />
      </div>

      <div className="grid gap-2">
        <label htmlFor="corps" className="text-sm font-medium text-ink-700">
          Message <span className="text-rose-500">*</span>
        </label>
        <textarea
          id="corps"
          required
          rows={5}
          value={corps}
          onChange={(e) => setCorps(e.target.value)}
          placeholder="Détaillez votre message. Les sauts de ligne sont préservés."
          className="rounded-xl border border-ink-200 bg-paper px-3 py-2 text-sm text-ink-900 outline-none focus:border-cobalt focus:ring-2 focus:ring-cobalt/20"
        />
      </div>

      <div className="grid gap-2">
        <label className="text-sm font-medium text-ink-700">Audience</label>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          {(Object.keys(AUDIENCE_LABEL) as AnnouncementAudience[]).map(
            (key) => {
              const Icon = AUDIENCE_ICON[key];
              const active = audience === key;
              return (
                <button
                  key={key}
                  type="button"
                  onClick={() => setAudience(key)}
                  className={`flex items-center gap-2 rounded-xl border px-3 py-2 text-left text-xs transition ${
                    active
                      ? "border-cobalt bg-cobalt/5 text-cobalt"
                      : "border-ink-200 bg-paper text-ink-600 hover:border-cobalt/40"
                  }`}
                >
                  <Icon className="size-4 shrink-0" />
                  <span className="font-medium">{AUDIENCE_LABEL[key]}</span>
                </button>
              );
            },
          )}
        </div>
      </div>

      {audience === "selection" ? (
        <div className="grid gap-2">
          <label htmlFor="ids" className="text-sm font-medium text-ink-700">
            Identifiants membres (séparés par des virgules ou espaces)
          </label>
          <input
            id="ids"
            type="text"
            value={memberIdsRaw}
            onChange={(e) => setMemberIdsRaw(e.target.value)}
            placeholder="12, 34, 56"
            className="rounded-xl border border-ink-200 bg-paper px-3 py-2 text-sm text-ink-900 outline-none focus:border-cobalt focus:ring-2 focus:ring-cobalt/20"
          />
          <p className="text-xs text-ink-500">
            Visible dans la colonne <code>id</code> de la page Membres.
          </p>
        </div>
      ) : null}

      <div className="grid gap-2">
        <label htmlFor="lien" className="text-sm font-medium text-ink-700">
          Lien interne (optionnel)
        </label>
        <input
          id="lien"
          type="text"
          value={lien}
          onChange={(e) => setLien(e.target.value)}
          placeholder="Ex. : /campaigns/42"
          className="rounded-xl border border-ink-200 bg-paper px-3 py-2 text-sm text-ink-900 outline-none focus:border-cobalt focus:ring-2 focus:ring-cobalt/20"
        />
      </div>

      <div className="grid gap-2">
        <label htmlFor="image" className="text-sm font-medium text-ink-700">
          Image illustrative (optionnel)
        </label>
        <div className="flex items-start gap-3">
          {imagePreview ? (
            <div className="relative size-24 shrink-0 overflow-hidden rounded-xl border border-ink-200 bg-ink-50">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={imagePreview} alt="Aperçu" className="size-full object-cover" />
              <button
                type="button"
                onClick={() => { setImage(null); setImagePreview(null); }}
                className="absolute right-1 top-1 rounded-full bg-rose-500 px-1.5 py-0.5 text-[0.65rem] font-bold text-white shadow"
                aria-label="Retirer l'image"
              >
                X
              </button>
            </div>
          ) : null}
          <div className="flex-1">
            <input
              id="image"
              type="file"
              accept="image/png,image/jpeg,image/webp"
              onChange={(e) => {
                const f = e.target.files?.[0] ?? null;
                setImage(f);
                if (f) {
                  const reader = new FileReader();
                  reader.onload = (ev) => setImagePreview(ev.target?.result as string);
                  reader.readAsDataURL(f);
                } else {
                  setImagePreview(null);
                }
              }}
              className="block w-full rounded-xl border border-ink-200 bg-paper px-3 py-2 text-sm text-ink-700 file:mr-3 file:rounded-md file:border-0 file:bg-cobalt/10 file:px-3 file:py-1 file:text-sm file:font-medium file:text-cobalt hover:file:bg-cobalt/20"
            />
            <p className="mt-1 text-xs text-ink-500">
              JPG/PNG/WebP recommandé 1200×630px. Affiché en tête de la notif
              mobile.
            </p>
          </div>
        </div>
      </div>

      <div className="flex items-center justify-between gap-3 pt-3">
        <p className="text-xs text-ink-500">
          La diffusion est immédiate et matérialise une notification mobile +
          portail pour chaque membre ciblé.
        </p>
        <button
          type="submit"
          disabled={sending}
          className={`${buttonClasses({ variant: "primary", size: "md" })} shrink-0`}
        >
          <Send className="size-4" />
          {sending ? "Diffusion…" : "Diffuser maintenant"}
        </button>
      </div>
    </form>
  );
}


function AnnouncementCard({
  row,
  onDelete,
}: {
  row: AnnouncementRow;
  onDelete: () => void;
}) {
  const Icon = AUDIENCE_ICON[row.audience];
  return (
    <li className="space-y-3 rounded-2xl border border-ink-100 bg-paper p-5 shadow-sm">
      <div className="flex items-start justify-between gap-4">
        <div className="space-y-1">
          <p className="font-display text-base text-ink-900">{row.titre}</p>
          <div className="flex flex-wrap items-center gap-2 text-xs text-ink-500">
            <span className="inline-flex items-center gap-1 rounded-full bg-cobalt/5 px-2 py-0.5 text-cobalt">
              <Icon className="size-3" />
              {row.audience_display}
            </span>
            <span>
              {row.recipients_count} destinataire
              {row.recipients_count > 1 ? "s" : ""}
            </span>
            {row.published_at ? (
              <span>· diffusée le {fmtDate(row.published_at)}</span>
            ) : null}
            {row.author_email ? (
              <span>· par {row.author_email}</span>
            ) : null}
          </div>
        </div>
        <button
          type="button"
          onClick={onDelete}
          className="inline-flex items-center gap-1 rounded-lg border border-rose-200 bg-rose-50 px-2 py-1 text-xs text-rose-700 hover:bg-rose-100"
          aria-label="Supprimer"
        >
          <Trash2 className="size-3.5" />
          Supprimer
        </button>
      </div>

      <pre className="whitespace-pre-wrap rounded-xl bg-cream p-4 text-sm text-ink-700">
        {row.corps}
      </pre>

      {row.lien ? (
        <p className="text-xs text-ink-500">
          Lien associé : <code className="text-ink-700">{row.lien}</code>
        </p>
      ) : null}
    </li>
  );
}


function fmtDate(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleString("fr-FR", {
      day: "2-digit",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}
