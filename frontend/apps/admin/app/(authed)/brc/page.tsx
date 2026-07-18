"use client";

import { useEffect, useState } from "react";
import {
  Check,
  X,
  FileText,
  ExternalLink,
  ZoomIn,
} from "lucide-react";

import { buttonClasses } from "@gathe/ui";

import {
  DocumentPreview,
  DocumentThumbnail,
} from "@/components/document-preview";
import { ExportMenu } from "@/components/export-menu";
import { Modal, ModalField, modalInputClass } from "@/components/modal";
import { adminApi, type ApiError, type BRCDocument } from "@/lib/api";
import type { ExportColumn } from "@/lib/export";


/**
 * Refonte 2026 — LOT 1 — Justificatifs BRC.
 *
 * Queue des ``BRCDocument`` en attente de validation par un admin.
 * Décision = valider (pose Member.is_brc_member=True) ou rejeter avec motif
 * (le membre peut alors re-uploader).
 */
export default function BRCPage() {
  return <Inner />;
}

function Inner() {
  const [filter, setFilter] = useState<
    "en_attente" | "valide" | "rejete" | ""
  >("en_attente");
  const [items, setItems] = useState<BRCDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [actingId, setActingId] = useState<number | null>(null);
  const [message, setMessage] = useState<{
    tone: "ok" | "err";
    text: string;
  } | null>(null);
  const [rejectTarget, setRejectTarget] = useState<BRCDocument | null>(null);
  const [previewTarget, setPreviewTarget] = useState<BRCDocument | null>(null);

  async function reload() {
    setLoading(true);
    try {
      adminApi.primeCsrf().catch(() => undefined);
      const list = await adminApi.brc.list(filter || undefined);
      setItems(list);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    reload();
    /* eslint-disable-next-line react-hooks/exhaustive-deps */
  }, [filter]);

  async function onValidate(doc: BRCDocument) {
    setActingId(doc.id);
    try {
      await adminApi.brc.validate(doc.id);
      setMessage({
        tone: "ok",
        text: `Justificatif #${doc.id} validé — ${doc.member_prenom} ${doc.member_nom} est désormais BRC.`,
      });
      await reload();
    } catch (err) {
      const apiErr = err as ApiError;
      setMessage({
        tone: "err",
        text: apiErr.detail ?? "Validation impossible.",
      });
    } finally {
      setActingId(null);
    }
  }

  async function submitReject(motif: string) {
    if (!rejectTarget) return;
    setActingId(rejectTarget.id);
    try {
      await adminApi.brc.reject(rejectTarget.id, motif);
      setMessage({
        tone: "ok",
        text: `Justificatif #${rejectTarget.id} rejeté.`,
      });
      setRejectTarget(null);
      await reload();
    } catch (err) {
      const apiErr = err as ApiError;
      setMessage({
        tone: "err",
        text: apiErr.detail ?? "Rejet impossible.",
      });
    } finally {
      setActingId(null);
    }
  }

  const exportColumns: ExportColumn<BRCDocument>[] = [
    { key: "id", label: "ID", value: (d) => d.id },
    { key: "membre", label: "Membre", value: (d) => `${d.member_prenom} ${d.member_nom}` },
    { key: "numero", label: "N° membre", value: (d) => d.member_numero },
    { key: "fichier", label: "Fichier", value: (d) => d.nom_original || `Document #${d.id}` },
    { key: "taille_ko", label: "Taille (Ko)", value: (d) => Math.round(d.taille / 1024) },
    { key: "statut", label: "Statut", value: (d) => d.statut_display },
    { key: "motif_rejet", label: "Motif rejet", value: (d) => d.motif_rejet },
    {
      key: "depose_le",
      label: "Déposé le",
      value: (d) => new Date(d.created_at).toLocaleDateString("fr-FR"),
    },
    {
      key: "valide_le",
      label: "Validé le",
      value: (d) => (d.validated_at ? new Date(d.validated_at).toLocaleDateString("fr-FR") : ""),
    },
  ];

  return (
    <section className="space-y-6">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="space-y-1">
          <h1 className="font-display text-2xl text-ink-900">
            Justificatifs BRC
          </h1>
          <p className="text-sm text-ink-500">
            Validation du statut de client Broad Range Consulting — prérequis
            pour les voies crédit Senior+BRC (refonte 2026).
          </p>
        </div>
        <ExportMenu
          filenamePrefix="brc-justificatifs"
          title="Justificatifs BRC"
          subtitle={`Filtre : ${filter || "tous statuts"}`}
          columns={exportColumns}
          rows={items}
        />
      </header>

      <div className="flex flex-wrap items-center gap-2">
        {(
          [
            ["en_attente", "En attente"],
            ["valide", "Validés"],
            ["rejete", "Rejetés"],
            ["", "Tous"],
          ] as const
        ).map(([key, label]) => (
          <button
            key={key}
            onClick={() => setFilter(key as typeof filter)}
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
            Aucun justificatif{" "}
            {filter === "en_attente" ? "en attente" : "à ce filtre"}.
          </p>
        )}
        {!loading && items.length > 0 && (
          <ul className="divide-y divide-line-200">
            {items.map((doc) => (
              <li
                key={doc.id}
                className="flex flex-wrap items-start gap-4 px-6 py-5"
              >
                {/* Thumbnail cliquable — preview du fichier */}
                <DocumentThumbnail
                  url={doc.fichier_url}
                  label={`Justificatif ${doc.member_prenom} ${doc.member_nom}`}
                  onOpen={() => setPreviewTarget(doc)}
                />

                <div className="flex-1 min-w-[260px] space-y-1.5">
                  <div className="flex flex-wrap items-center gap-2 text-sm font-semibold text-ink-900">
                    {doc.member_prenom} {doc.member_nom}
                    <span className="rounded-full bg-paper-soft px-2 py-0.5 text-xs font-medium text-ink-500">
                      {doc.member_numero}
                    </span>
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                        doc.statut === "en_attente"
                          ? "bg-amber-100 text-amber-700"
                          : doc.statut === "valide"
                          ? "bg-emerald-100 text-emerald-700"
                          : "bg-red-100 text-red-700"
                      }`}
                    >
                      {doc.statut_display}
                    </span>
                  </div>
                  <div className="flex flex-wrap items-center gap-3 text-xs text-ink-500">
                    <span className="inline-flex items-center gap-1">
                      <FileText className="h-3.5 w-3.5" />
                      {doc.nom_original || `Document #${doc.id}`}
                      {doc.taille
                        ? ` · ${Math.round(doc.taille / 1024)} Ko`
                        : ""}
                    </span>
                    {doc.fichier_url && (
                      <>
                        <button
                          onClick={() => setPreviewTarget(doc)}
                          className="inline-flex items-center gap-1 text-blue-700 hover:text-blue-800"
                        >
                          <ZoomIn className="h-3 w-3" />
                          Aperçu plein écran
                        </button>
                        <a
                          href={doc.fichier_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1 text-ink-500 hover:text-ink-700"
                        >
                          <ExternalLink className="h-3 w-3" />
                          Nouvel onglet
                        </a>
                      </>
                    )}
                  </div>
                  {doc.statut === "rejete" && doc.motif_rejet && (
                    <p className="rounded-md bg-red-50 px-3 py-2 text-xs text-red-700">
                      <strong>Motif rejet :</strong> {doc.motif_rejet}
                    </p>
                  )}
                  <p className="text-xs text-ink-400">
                    Déposé le{" "}
                    {new Date(doc.created_at).toLocaleDateString("fr-FR")}
                  </p>
                </div>

                {doc.statut === "en_attente" && (
                  <div className="flex shrink-0 gap-2">
                    <button
                      onClick={() => onValidate(doc)}
                      disabled={actingId === doc.id}
                      className={buttonClasses({
                        variant: "primary",
                        size: "sm",
                      })}
                    >
                      <Check className="mr-1 h-4 w-4" />
                      Valider
                    </button>
                    <button
                      onClick={() => setRejectTarget(doc)}
                      disabled={actingId === doc.id}
                      className={buttonClasses({
                        variant: "ghost",
                        size: "sm",
                      })}
                    >
                      <X className="mr-1 h-4 w-4" />
                      Rejeter
                    </button>
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>

      {rejectTarget && (
        <RejectModal
          target={rejectTarget}
          onClose={() => setRejectTarget(null)}
          onSubmit={submitReject}
          submitting={actingId === rejectTarget.id}
        />
      )}

      {previewTarget && previewTarget.fichier_url && (
        <DocumentPreview
          url={previewTarget.fichier_url}
          name={previewTarget.nom_original || `Document #${previewTarget.id}`}
          subtitle={`${previewTarget.member_prenom} ${previewTarget.member_nom} · ${previewTarget.member_numero}`}
          onClose={() => setPreviewTarget(null)}
        />
      )}
    </section>
  );
}


function RejectModal({
  target,
  onClose,
  onSubmit,
  submitting,
}: {
  target: BRCDocument;
  onClose: () => void;
  onSubmit: (motif: string) => void;
  submitting: boolean;
}) {
  const [motif, setMotif] = useState("");
  return (
    <Modal
      open
      onClose={onClose}
      title={`Rejeter le justificatif BRC #${target.id}`}
    >
      <p className="text-sm text-ink-500">
        Le motif sera transmis au membre. Il pourra re-uploader un nouveau
        document.
      </p>
      <ModalField label="Motif de rejet *">
        <textarea
          value={motif}
          onChange={(e) => setMotif(e.target.value)}
          rows={4}
          placeholder="Document illisible / non-conforme / expiré…"
          className={modalInputClass + " min-h-[100px]"}
        />
      </ModalField>
      <div className="flex justify-end gap-2 pt-3">
        <button
          onClick={onClose}
          className={buttonClasses({ variant: "ghost", size: "sm" })}
        >
          Annuler
        </button>
        <button
          onClick={() => onSubmit(motif.trim())}
          disabled={!motif.trim() || submitting}
          className={buttonClasses({ variant: "primary", size: "sm" })}
        >
          {submitting ? "En cours…" : "Confirmer le rejet"}
        </button>
      </div>
    </Modal>
  );
}
