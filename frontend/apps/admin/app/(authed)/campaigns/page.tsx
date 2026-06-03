"use client";

import { useEffect, useState } from "react";
import {
  Megaphone,
  Plus,
  Power,
  Users,
  CalendarRange,
  AlertCircle,
  CheckCircle2,
  XCircle,
  ImageIcon,
  ZoomIn,
  Trash2,
  Search,
  X,
  Download,
} from "lucide-react";

import { buttonClasses } from "@gathe/ui";

import { ExportMenu } from "@/components/export-menu";
import { Modal } from "@/components/modal";
import {
  adminApi,
  type ApiError,
  type MicrocampaignCreateInput,
  type MicrocampaignDetail,
  type MicrocampaignPendingRequest,
  type MicrocampaignRow,
  type MicrocampaignTargetedMember,
} from "@/lib/api";
import type { ExportColumn } from "@/lib/export";


/**
 * Refonte 2026 — LOT 16 — CRUD admin des campagnes micro-crédit (voie 3).
 *
 * Liste les campagnes, permet d'en créer/clôturer, et de valider/rejeter
 * les LoanRequest en statut ``en_validation_campagne``.
 */
export default function CampaignsPage() {
  return <Inner />;
}


type FilterKey = "all" | "open" | "closed";


function Inner() {
  const [filter, setFilter] = useState<FilterKey>("all");
  const [items, setItems] = useState<MicrocampaignRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [createOpen, setCreateOpen] = useState(false);
  const [detailFor, setDetailFor] = useState<number | null>(null);
  const [confirmClose, setConfirmClose] = useState<MicrocampaignRow | null>(null);
  const [flyerPreview, setFlyerPreview] = useState<MicrocampaignRow | null>(null);
  const [message, setMessage] = useState<{
    tone: "ok" | "err";
    text: string;
  } | null>(null);

  async function reload() {
    setLoading(true);
    try {
      adminApi.primeCsrf().catch(() => undefined);
      const params: Parameters<typeof adminApi.campaigns.list>[0] = {};
      if (filter === "open") params.is_open = "true";
      if (filter === "closed") params.actif = "false";
      const data = await adminApi.campaigns.list(params);
      setItems(data.results);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    reload();
    /* eslint-disable-next-line react-hooks/exhaustive-deps */
  }, [filter]);

  async function onClose(c: MicrocampaignRow, reason: string) {
    try {
      await adminApi.campaigns.close(c.id, reason || undefined);
      setMessage({
        tone: "ok",
        text: `Campagne "${c.nom}" fermée.`,
      });
      setConfirmClose(null);
      await reload();
    } catch (err) {
      const apiErr = err as ApiError;
      setMessage({
        tone: "err",
        text: apiErr.detail ?? "Clôture impossible.",
      });
    }
  }

  const exportColumns: ExportColumn<MicrocampaignRow>[] = [
    { key: "id", label: "ID", value: (c) => c.id },
    { key: "nom", label: "Nom", value: (c) => c.nom },
    { key: "profil", label: "Profil cible", value: (c) => c.profil_cible },
    { key: "debut", label: "Date début", value: (c) => c.date_debut },
    { key: "fin", label: "Date fin", value: (c) => c.date_fin },
    { key: "min", label: "Montant min", value: (c) => c.montant_min },
    { key: "max", label: "Montant max", value: (c) => c.montant_max },
    { key: "taux", label: "Taux %", value: (c) => (parseFloat(c.taux_interet) * 100).toFixed(2) },
    { key: "recouv", label: "Recouvrement (j)", value: (c) => c.nb_jours_recouvrement },
    { key: "plafond", label: "Plafond bénéficiaires", value: (c) => c.plafond_beneficiaires ?? "" },
    { key: "actif", label: "Actif", value: (c) => (c.actif ? "Oui" : "Non") },
    { key: "is_open", label: "Ouverte", value: (c) => (c.is_open ? "Oui" : "Non") },
    { key: "benef", label: "Bénéficiaires", value: (c) => c.beneficiaires_count },
    { key: "targeted", label: "Audience (ciblés)", value: (c) => c.targeted_count },
    { key: "close_reason", label: "Motif clôture", value: (c) => c.close_reason },
    {
      key: "created",
      label: "Créée le",
      value: (c) => new Date(c.created_at).toLocaleDateString("fr-FR"),
    },
  ];

  return (
    <main className="space-y-6 p-8">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="space-y-1">
          <h1 className="font-display text-2xl text-ink-900">
            Campagnes micro-crédit
          </h1>
          <p className="text-sm text-ink-500">
            Voie 3 d&apos;éligibilité (refonte 2026 §8) — micro-crédits pour
            non-adhérents par profil ciblé. Bénéficiaires créés en{" "}
            <code>statut=TEMPORAIRE</code>.
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <ExportMenu
            filenamePrefix="campagnes-microcredit"
            title="Campagnes micro-crédit"
            subtitle={`Filtre : ${
              filter === "all" ? "toutes" : filter === "open" ? "ouvertes" : "fermées"
            }`}
            columns={exportColumns}
            rows={items}
          />
          <button
            onClick={() => setCreateOpen(true)}
            className={buttonClasses({ variant: "primary", size: "sm" })}
          >
            <Plus className="mr-1 h-4 w-4" />
            Nouvelle campagne
          </button>
        </div>
      </header>

      <div className="flex flex-wrap items-center gap-2">
        {(
          [
            ["all", "Toutes"],
            ["open", "Ouvertes (dans la fenêtre)"],
            ["closed", "Fermées"],
          ] as const
        ).map(([key, label]) => (
          <button
            key={key}
            onClick={() => setFilter(key)}
            className={`rounded-full border px-4 py-1.5 text-sm transition ${
              filter === key
                ? "border-terra-600 bg-terra-50 text-terra-700"
                : "border-line-200 text-ink-500 hover:bg-paper-soft"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {message && (
        <div
          className={`rounded-lg border px-4 py-3 text-sm ${
            message.tone === "ok"
              ? "border-emerald-200 bg-emerald-50 text-emerald-700"
              : "border-red-200 bg-red-50 text-red-700"
          }`}
        >
          {message.text}
        </div>
      )}

      <section className="rounded-2xl border border-line-200 bg-paper">
        {loading && (
          <p className="px-6 py-12 text-center text-sm text-ink-500">
            Chargement…
          </p>
        )}
        {!loading && items.length === 0 && (
          <p className="px-6 py-12 text-center text-sm text-ink-500">
            Aucune campagne pour ce filtre.
          </p>
        )}
        {!loading && items.length > 0 && (
          <ul className="divide-y divide-line-200">
            {items.map((row) => (
              <CampaignRow
                key={row.id}
                row={row}
                onOpenDetail={() => setDetailFor(row.id)}
                onClose={() => setConfirmClose(row)}
                onOpenFlyer={() => setFlyerPreview(row)}
              />
            ))}
          </ul>
        )}
      </section>

      {createOpen && (
        <CreateModal
          onClose={() => setCreateOpen(false)}
          onCreated={() => {
            setMessage({ tone: "ok", text: "Campagne créée." });
            setCreateOpen(false);
            reload();
          }}
        />
      )}

      {detailFor !== null && (
        <DetailModal
          campaignId={detailFor}
          onClose={() => setDetailFor(null)}
          onDecided={() => {
            setMessage({ tone: "ok", text: "Demande mise à jour." });
            reload();
          }}
        />
      )}

      {confirmClose && (
        <CloseModal
          target={confirmClose}
          onCancel={() => setConfirmClose(null)}
          onConfirm={(reason) => onClose(confirmClose, reason)}
        />
      )}

      {flyerPreview && flyerPreview.flyer_url && (
        <FlyerPreviewModal
          row={flyerPreview}
          onClose={() => setFlyerPreview(null)}
        />
      )}
    </main>
  );
}


function FlyerPreviewModal({
  row,
  onClose,
}: {
  row: MicrocampaignRow;
  onClose: () => void;
}) {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);

  const url = row.flyer_url!;
  return (
    <div
      role="dialog"
      aria-modal="true"
      onClick={onClose}
      className="fixed inset-0 z-50 flex flex-col bg-ink-900/85 backdrop-blur-sm"
    >
      <header className="flex items-center justify-between border-b border-white/10 px-6 py-3 text-paper">
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold">{row.nom}</p>
          <p className="truncate text-xs text-paper/60">
            Profil : {row.profil_cible} · {formatDate(row.date_debut)} →{" "}
            {formatDate(row.date_fin)}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <a
            href={url}
            target="_blank"
            rel="noopener noreferrer"
            onClick={(e) => e.stopPropagation()}
            className="inline-flex items-center gap-1.5 rounded-md bg-white/10 px-3 py-1.5 text-xs font-medium text-paper hover:bg-white/20"
          >
            <Download className="h-3.5 w-3.5" />
            Télécharger
          </a>
          <button
            onClick={onClose}
            className="inline-flex items-center gap-1.5 rounded-md bg-white/10 px-3 py-1.5 text-xs font-medium text-paper hover:bg-white/20"
          >
            <X className="h-3.5 w-3.5" />
            Fermer (Esc)
          </button>
        </div>
      </header>
      <div
        onClick={(e) => e.stopPropagation()}
        className="flex flex-1 items-center justify-center overflow-auto p-6"
      >
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={url}
          alt={`Flyer ${row.nom}`}
          className="max-h-full max-w-full rounded-md bg-paper shadow-2xl"
        />
      </div>
    </div>
  );
}


function CampaignRow({
  row,
  onOpenDetail,
  onClose,
  onOpenFlyer,
}: {
  row: MicrocampaignRow;
  onOpenDetail: () => void;
  onClose: () => void;
  onOpenFlyer: () => void;
}) {
  return (
    <li className="flex flex-wrap items-start gap-4 px-6 py-5">
      {/* Flyer thumbnail — cliquable si présent */}
      <button
        type="button"
        onClick={row.flyer_url ? onOpenFlyer : undefined}
        disabled={!row.flyer_url}
        className={`group relative h-28 w-20 shrink-0 overflow-hidden rounded-md border border-line-200 transition-shadow ${
          row.flyer_url
            ? "bg-paper-soft hover:shadow-md focus:outline-none focus:ring-2 focus:ring-blue-700"
            : "bg-paper-soft"
        }`}
        title={row.flyer_url ? "Voir le flyer en plein écran" : "Aucun flyer joint"}
      >
        {row.flyer_url ? (
          <>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={row.flyer_url}
              alt={`Flyer ${row.nom}`}
              className="h-full w-full object-cover"
            />
            <span className="absolute inset-0 flex items-center justify-center bg-ink-900/0 opacity-0 transition-all group-hover:bg-ink-900/30 group-hover:opacity-100">
              <ZoomIn className="h-5 w-5 text-white" />
            </span>
          </>
        ) : (
          <div className="flex h-full w-full flex-col items-center justify-center gap-1 text-ink-400">
            <ImageIcon className="h-6 w-6" />
            <span className="text-[10px]">No flyer</span>
          </div>
        )}
      </button>

      <div className="flex-1 min-w-[260px] space-y-1.5">
        <div className="flex flex-wrap items-center gap-2 text-sm font-semibold text-ink-900">
          <Megaphone className="h-4 w-4 text-terra-600" />
          {row.nom}
          {row.is_open ? (
            <span className="inline-flex items-center gap-1 rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-700">
              <CheckCircle2 className="h-3 w-3" />
              Ouverte
            </span>
          ) : (
            <span className="inline-flex items-center gap-1 rounded-full bg-stone-200 px-2 py-0.5 text-xs font-medium text-stone-700">
              <XCircle className="h-3 w-3" />
              Fermée
            </span>
          )}
          <span className="rounded-full bg-paper-soft px-2 py-0.5 text-xs font-medium text-ink-500">
            {row.profil_cible}
          </span>
        </div>
        <div className="flex flex-wrap items-center gap-4 text-xs text-ink-500">
          <span className="inline-flex items-center gap-1">
            <CalendarRange className="h-3.5 w-3.5" />
            {formatDate(row.date_debut)} → {formatDate(row.date_fin)}
          </span>
          <span>
            Plafond :{" "}
            <strong className="text-ink-900">{formatXaf(row.montant_max)}</strong>
          </span>
          <span>
            Taux :{" "}
            <strong className="text-ink-900">
              {(parseFloat(row.taux_interet) * 100).toFixed(0)} %
            </strong>
          </span>
          <span className="inline-flex items-center gap-1">
            <Users className="h-3.5 w-3.5" />
            {row.beneficiaires_count}
            {row.plafond_beneficiaires !== null
              ? ` / ${row.plafond_beneficiaires}`
              : ""}{" "}
            bénéficiaires
          </span>
          <span className="inline-flex items-center gap-1">
            <Users className="h-3.5 w-3.5" />
            <strong className="text-ink-900">{row.targeted_count}</strong>{" "}
            ciblés
          </span>
          {!row.actif && row.close_reason ? (
            <span className="text-stone-500">closed_reason : {row.close_reason}</span>
          ) : null}
        </div>
      </div>
      <div className="flex shrink-0 items-center gap-2">
        <button
          onClick={onOpenDetail}
          className={buttonClasses({ variant: "ghost", size: "sm" })}
        >
          Détail
        </button>
        {row.actif && (
          <button
            onClick={onClose}
            className={buttonClasses({ variant: "secondary", size: "sm" })}
          >
            <Power className="mr-1 h-3.5 w-3.5" />
            Clôturer
          </button>
        )}
      </div>
    </li>
  );
}


// ---------------------------------------------------------------------------
// Création
// ---------------------------------------------------------------------------


function CreateModal({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: () => void;
}) {
  const today = new Date().toISOString().slice(0, 10);
  const [form, setForm] = useState<MicrocampaignCreateInput>({
    nom: "",
    profil_cible: "",
    date_debut: today,
    date_fin: today,
    montant_min: 5000,
    montant_max: 50000,
    taux_interet: 0.1,
    nb_jours_recouvrement: 60,
    plafond_beneficiaires: null,
  });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [flyer, setFlyer] = useState<File | null>(null);
  const [flyerPreviewUrl, setFlyerPreviewUrl] = useState<string | null>(null);

  function set<K extends keyof MicrocampaignCreateInput>(
    key: K,
    value: MicrocampaignCreateInput[K],
  ) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  function onPickFlyer(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0] ?? null;
    if (flyerPreviewUrl) URL.revokeObjectURL(flyerPreviewUrl);
    setFlyer(file);
    setFlyerPreviewUrl(file ? URL.createObjectURL(file) : null);
  }

  useEffect(() => {
    return () => {
      if (flyerPreviewUrl) URL.revokeObjectURL(flyerPreviewUrl);
    };
  }, [flyerPreviewUrl]);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await adminApi.campaigns.create(
        {
          ...form,
          montant_min: String(form.montant_min),
          montant_max: String(form.montant_max),
          taux_interet: String(form.taux_interet),
        },
        flyer,
      );
      onCreated();
    } catch (err) {
      const apiErr = err as ApiError;
      const detail =
        apiErr.detail ??
        (typeof apiErr.body === "object"
          ? JSON.stringify(apiErr.body)
          : "Création impossible.");
      setError(detail);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Modal open onClose={onClose} title="Nouvelle campagne micro-crédit">
      <form onSubmit={onSubmit} className="space-y-4">
        <Field label="Nom de la campagne">
          <input
            value={form.nom}
            onChange={(e) => set("nom", e.target.value)}
            required
            className={inputCls}
          />
        </Field>
        <Field
          label="Profil cible"
          hint="Mot-clé libre (ex: commercants, agriculteurs, parents)."
        >
          <input
            value={form.profil_cible}
            onChange={(e) => set("profil_cible", e.target.value)}
            required
            className={inputCls}
          />
        </Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Date début">
            <input
              type="date"
              value={form.date_debut}
              onChange={(e) => set("date_debut", e.target.value)}
              required
              className={inputCls}
            />
          </Field>
          <Field label="Date fin">
            <input
              type="date"
              value={form.date_fin}
              onChange={(e) => set("date_fin", e.target.value)}
              required
              className={inputCls}
            />
          </Field>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Montant min (FCFA)">
            <input
              type="number"
              min={0}
              value={form.montant_min as number}
              onChange={(e) => set("montant_min", Number(e.target.value))}
              required
              className={inputCls}
            />
          </Field>
          <Field label="Montant max (FCFA)">
            <input
              type="number"
              min={100}
              value={form.montant_max as number}
              onChange={(e) => set("montant_max", Number(e.target.value))}
              required
              className={inputCls}
            />
          </Field>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Taux d'intérêt" hint="0.10 = 10 %">
            <input
              type="number"
              step="0.01"
              min={0}
              max={1}
              value={form.taux_interet as number}
              onChange={(e) => set("taux_interet", Number(e.target.value))}
              required
              className={inputCls}
            />
          </Field>
          <Field label="Durée recouvrement (jours)">
            <input
              type="number"
              min={1}
              max={365}
              value={form.nb_jours_recouvrement}
              onChange={(e) =>
                set("nb_jours_recouvrement", Number(e.target.value))
              }
              required
              className={inputCls}
            />
          </Field>
        </div>
        <Field
          label="Plafond bénéficiaires"
          hint="Vide = pas de quota. Bloque les nouvelles demandes une fois atteint."
        >
          <input
            type="number"
            min={1}
            max={10000}
            value={form.plafond_beneficiaires ?? ""}
            onChange={(e) =>
              set(
                "plafond_beneficiaires",
                e.target.value === "" ? null : Number(e.target.value),
              )
            }
            className={inputCls}
          />
        </Field>

        <Field
          label="Flyer (image PNG/JPG)"
          hint="Visuel affiché dans l'admin et envoyé aux membres ciblés."
        >
          <div className="flex items-center gap-3">
            {flyerPreviewUrl ? (
              /* eslint-disable-next-line @next/next/no-img-element */
              <img
                src={flyerPreviewUrl}
                alt="Aperçu flyer"
                className="h-24 w-16 rounded-md border border-line-200 object-cover"
              />
            ) : (
              <div className="flex h-24 w-16 items-center justify-center rounded-md border border-dashed border-line-200 bg-paper-soft text-ink-400">
                <ImageIcon className="h-5 w-5" />
              </div>
            )}
            <div className="flex-1">
              <input
                type="file"
                accept="image/png,image/jpeg,image/gif,image/webp"
                onChange={onPickFlyer}
                className="block w-full text-xs text-ink-700 file:mr-3 file:rounded-md file:border-0 file:bg-blue-50 file:px-3 file:py-1.5 file:text-xs file:font-medium file:text-blue-700 hover:file:bg-blue-100"
              />
              {flyer && (
                <p className="mt-1 text-[11px] text-ink-500">
                  {flyer.name} · {Math.round(flyer.size / 1024)} Ko
                </p>
              )}
            </div>
            {flyer && (
              <button
                type="button"
                onClick={() => {
                  if (flyerPreviewUrl) URL.revokeObjectURL(flyerPreviewUrl);
                  setFlyer(null);
                  setFlyerPreviewUrl(null);
                }}
                className="rounded-md p-2 text-ink-400 hover:bg-red-50 hover:text-red-600"
                title="Retirer le flyer"
              >
                <Trash2 className="h-4 w-4" />
              </button>
            )}
          </div>
        </Field>

        {error && (
          <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
            <AlertCircle className="mr-1 inline h-4 w-4" />
            {error}
          </div>
        )}

        <div className="flex justify-end gap-2 pt-2">
          <button
            type="button"
            onClick={onClose}
            className={buttonClasses({ variant: "ghost", size: "sm" })}
          >
            Annuler
          </button>
          <button
            type="submit"
            disabled={submitting}
            className={buttonClasses({ variant: "primary", size: "sm" })}
          >
            {submitting ? "Création…" : "Créer la campagne"}
          </button>
        </div>
      </form>
    </Modal>
  );
}


// ---------------------------------------------------------------------------
// Clôture
// ---------------------------------------------------------------------------


function CloseModal({
  target,
  onCancel,
  onConfirm,
}: {
  target: MicrocampaignRow;
  onCancel: () => void;
  onConfirm: (reason: string) => void;
}) {
  const [reason, setReason] = useState("manual");
  return (
    <Modal open onClose={onCancel} title={`Clôturer "${target.nom}"`}>
      <p className="text-sm text-ink-700">
        La campagne ne sera plus proposée aux nouvelles demandes. Les LoanRequest
        déjà en validation campagne restent traitables.
      </p>
      <Field label="Motif" hint='Ex: "manual", "quota_reached", "expired".'>
        <input
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          className={inputCls}
        />
      </Field>
      <div className="flex justify-end gap-2 pt-3">
        <button
          onClick={onCancel}
          className={buttonClasses({ variant: "ghost", size: "sm" })}
        >
          Annuler
        </button>
        <button
          onClick={() => onConfirm(reason)}
          className={buttonClasses({ variant: "primary", size: "sm" })}
        >
          Confirmer la clôture
        </button>
      </div>
    </Modal>
  );
}


// ---------------------------------------------------------------------------
// Détail + décisions LR
// ---------------------------------------------------------------------------


function DetailModal({
  campaignId,
  onClose,
  onDecided,
}: {
  campaignId: number;
  onClose: () => void;
  onDecided: () => void;
}) {
  const [detail, setDetail] = useState<MicrocampaignDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pendingLrId, setPendingLrId] = useState<number | null>(null);

  async function reload() {
    try {
      const d = await adminApi.campaigns.detail(campaignId);
      setDetail(d);
    } catch (err) {
      const apiErr = err as ApiError;
      setError(apiErr.detail ?? "Détail introuvable.");
    }
  }

  useEffect(() => {
    reload();
    /* eslint-disable-next-line react-hooks/exhaustive-deps */
  }, [campaignId]);

  async function decide(
    lr: MicrocampaignPendingRequest,
    payload:
      | { decision: "valide" }
      | { decision: "rejete"; motif_rejet: string },
  ) {
    setPendingLrId(lr.id);
    try {
      await adminApi.campaigns.decideRequest(lr.id, payload);
      onDecided();
      await reload();
    } catch (err) {
      const apiErr = err as ApiError;
      setError(apiErr.detail ?? "Décision impossible.");
    } finally {
      setPendingLrId(null);
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      title={detail ? detail.nom : "Détail campagne"}
    >
      {error && (
        <div className="mb-3 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </div>
      )}
      {!detail ? (
        <p className="text-sm text-ink-500">Chargement…</p>
      ) : (
        <div className="space-y-5">
          <div className="grid grid-cols-2 gap-3 rounded-lg border border-line-200 bg-paper-soft p-3 text-xs">
            <Info label="Profil cible" value={detail.profil_cible} />
            <Info
              label="Période"
              value={`${formatDate(detail.date_debut)} → ${formatDate(detail.date_fin)}`}
            />
            <Info
              label="Bornes"
              value={`${formatXaf(detail.montant_min)} – ${formatXaf(detail.montant_max)}`}
            />
            <Info
              label="Taux flat"
              value={`${(parseFloat(detail.taux_interet) * 100).toFixed(0)} %`}
            />
            <Info
              label="Recouvrement"
              value={`${detail.nb_jours_recouvrement} jours`}
            />
            <Info
              label="Bénéficiaires"
              value={`${detail.beneficiaires_count}${
                detail.plafond_beneficiaires
                  ? ` / ${detail.plafond_beneficiaires}`
                  : ""
              }`}
            />
          </div>

          <section>
            <h3 className="mb-2 font-display text-sm font-semibold text-ink-900">
              Demandes en attente de validation comité (
              {detail.pending_count})
            </h3>
            {detail.pending_requests.length === 0 ? (
              <p className="rounded-md border border-dashed border-line-200 px-4 py-6 text-center text-sm text-ink-500">
                Aucune demande en attente.
              </p>
            ) : (
              <ul className="divide-y divide-line-200 rounded-lg border border-line-200">
                {detail.pending_requests.map((lr) => (
                  <PendingRow
                    key={lr.id}
                    lr={lr}
                    submitting={pendingLrId === lr.id}
                    onValide={() => decide(lr, { decision: "valide" })}
                    onRejete={(motif) =>
                      decide(lr, { decision: "rejete", motif_rejet: motif })
                    }
                  />
                ))}
              </ul>
            )}
          </section>

          {/* Audience — membres ciblés (M2M) */}
          <AudienceSection
            campaignId={detail.id}
            members={detail.targeted_members}
            onChange={reload}
          />
        </div>
      )}
    </Modal>
  );
}


function AudienceSection({
  campaignId,
  members,
  onChange,
}: {
  campaignId: number;
  members: MicrocampaignTargetedMember[];
  onChange: () => void;
}) {
  const [input, setInput] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [notFound, setNotFound] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);

  async function onAdd() {
    setError(null);
    setNotFound([]);
    const numeros = input
      .split(/[,\s\n]+/)
      .map((s) => s.trim())
      .filter(Boolean);
    if (numeros.length === 0) return;
    setSubmitting(true);
    try {
      const r = await adminApi.campaigns.addTargeted(campaignId, {
        numeros_membre: numeros,
      });
      setNotFound(r.not_found.numeros_membre);
      setInput("");
      await onChange();
    } catch (err) {
      const apiErr = err as ApiError;
      setError(apiErr.detail ?? "Ajout impossible.");
    } finally {
      setSubmitting(false);
    }
  }

  async function onRemove(m: MicrocampaignTargetedMember) {
    try {
      await adminApi.campaigns.removeTargeted(campaignId, m.id);
      await onChange();
    } catch (err) {
      const apiErr = err as ApiError;
      setError(apiErr.detail ?? "Retrait impossible.");
    }
  }

  return (
    <section>
      <h3 className="mb-2 font-display text-sm font-semibold text-ink-900">
        Audience — membres ciblés ({members.length})
      </h3>
      <p className="mb-3 text-xs text-ink-500">
        Membres explicitement notifiés pour cette campagne (segmentation
        manuelle). Indépendant des bénéficiaires effectifs.
      </p>

      <div className="mb-3 flex gap-2 rounded-md border border-line-200 bg-cream/40 p-3">
        <Search className="mt-2 h-4 w-4 shrink-0 text-ink-400" />
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Numéros de membre — séparés par espace, virgule ou retour ligne (ex: GF-DEMO-0109 GF-DEMO-0404)"
          rows={2}
          className="flex-1 resize-y rounded-md border border-line-200 bg-paper px-2 py-1.5 text-xs text-ink-900 outline-none focus:border-blue-700 focus:ring-1 focus:ring-blue-700"
        />
        <button
          onClick={onAdd}
          disabled={submitting || !input.trim()}
          className={buttonClasses({ variant: "primary", size: "sm" })}
        >
          {submitting ? "…" : "Ajouter"}
        </button>
      </div>

      {error && (
        <p className="mb-2 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
          {error}
        </p>
      )}
      {notFound.length > 0 && (
        <p className="mb-2 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
          ⚠️ Numéros introuvables : {notFound.join(", ")}
        </p>
      )}

      {members.length === 0 ? (
        <p className="rounded-md border border-dashed border-line-200 px-4 py-6 text-center text-xs text-ink-500">
          Aucun membre ciblé pour le moment.
        </p>
      ) : (
        <ul className="divide-y divide-line-200 rounded-lg border border-line-200">
          {members.map((m) => (
            <li
              key={m.id}
              className="flex items-center justify-between px-3 py-2"
            >
              <div>
                <p className="text-sm font-medium text-ink-900">
                  {m.prenom} {m.nom}
                </p>
                <p className="text-xs text-ink-500">
                  {m.numero_membre} · {m.statut}
                </p>
              </div>
              <button
                onClick={() => onRemove(m)}
                className="rounded-md p-1.5 text-ink-400 hover:bg-red-50 hover:text-red-600"
                title="Retirer de l'audience"
              >
                <Trash2 className="h-4 w-4" />
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}


function PendingRow({
  lr,
  submitting,
  onValide,
  onRejete,
}: {
  lr: MicrocampaignPendingRequest;
  submitting: boolean;
  onValide: () => void;
  onRejete: (motif: string) => void;
}) {
  const [showReject, setShowReject] = useState(false);
  const [motif, setMotif] = useState("");

  return (
    <li className="px-4 py-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="text-sm font-semibold text-ink-900">
            {lr.member_nom}{" "}
            <span className="text-xs font-medium text-ink-500">
              {lr.member_numero}
            </span>
          </p>
          <p className="mt-0.5 text-xs text-ink-500">
            {formatXaf(lr.montant_demande)} sur {lr.duree_mois} mois ·{" "}
            {formatDate(lr.date_soumission)}
          </p>
          {lr.motif && (
            <p className="mt-1 text-xs italic text-ink-600">"{lr.motif}"</p>
          )}
        </div>
        {!showReject ? (
          <div className="flex shrink-0 gap-2">
            <button
              onClick={onValide}
              disabled={submitting}
              className={buttonClasses({ variant: "primary", size: "sm" })}
            >
              Valider
            </button>
            <button
              onClick={() => setShowReject(true)}
              disabled={submitting}
              className={buttonClasses({ variant: "secondary", size: "sm" })}
            >
              Rejeter…
            </button>
          </div>
        ) : null}
      </div>
      {showReject && (
        <div className="mt-3 space-y-2">
          <textarea
            value={motif}
            onChange={(e) => setMotif(e.target.value)}
            placeholder="Motif du rejet…"
            className={`${inputCls} min-h-[60px]`}
          />
          <div className="flex justify-end gap-2">
            <button
              onClick={() => setShowReject(false)}
              className={buttonClasses({ variant: "ghost", size: "sm" })}
            >
              Annuler
            </button>
            <button
              onClick={() => onRejete(motif.trim())}
              disabled={!motif.trim() || submitting}
              className={buttonClasses({ variant: "primary", size: "sm" })}
            >
              Confirmer le rejet
            </button>
          </div>
        </div>
      )}
    </li>
  );
}


function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block space-y-1">
      <span className="text-xs font-medium text-ink-700">{label}</span>
      {children}
      {hint && <span className="block text-[11px] text-ink-500">{hint}</span>}
    </label>
  );
}


function Info({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="font-medium text-ink-500">{label}</p>
      <p className="mt-0.5 text-ink-900">{value}</p>
    </div>
  );
}


const inputCls =
  "block w-full rounded-md border border-line-200 bg-paper px-3 py-2 text-sm text-ink-900 placeholder-ink-400 focus:border-blue-700 focus:outline-none focus:ring-1 focus:ring-blue-700";


function formatXaf(amount: string | number): string {
  const n = typeof amount === "number" ? amount : parseFloat(amount);
  if (Number.isNaN(n)) return String(amount);
  return Math.round(n).toLocaleString("fr-FR") + " XAF";
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString("fr-FR", {
      day: "2-digit",
      month: "short",
      year: "numeric",
    });
  } catch {
    return iso;
  }
}

