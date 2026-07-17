"use client";

import { useEffect, useRef, useState } from "react";
import {
  FileText,
  Upload,
  CheckCircle2,
  AlertCircle,
  ZoomIn,
} from "lucide-react";

import { buttonClasses } from "@gathe/ui";

import { DocumentPreview } from "@/components/document-preview";
import { adminApi, type ApiError } from "@/lib/api";


type AssetState = {
  reglement_interieur: {
    uploaded: boolean;
    url: string | null;
    name: string | null;
    size: number;
    uploaded_at: string | null;
    uploaded_by: string | null;
  };
};


/**
 * Documents officiels de la coopérative — singleton.
 *
 * Pour l'instant : règlement intérieur (PDF) joint au mail de bienvenue UC1.
 */
export default function CooperativeAssetPage() {
  const [state, setState] = useState<AssetState | null>(null);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [message, setMessage] = useState<{
    tone: "ok" | "err";
    text: string;
  } | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const [previewOpen, setPreviewOpen] = useState(false);

  async function reload() {
    setLoading(true);
    try {
      setState(await adminApi.cooperativeAsset.get());
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

  async function onUpload(file: File) {
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      setMessage({ tone: "err", text: "Le fichier doit être un PDF." });
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      setMessage({ tone: "err", text: "PDF trop volumineux (max 10 Mo)." });
      return;
    }
    setUploading(true);
    setMessage(null);
    try {
      await adminApi.cooperativeAsset.uploadReglement(file);
      setMessage({
        tone: "ok",
        text: "Règlement intérieur mis à jour. Il sera joint à tous les prochains mails de bienvenue.",
      });
      await reload();
    } catch (err) {
      const apiErr = err as ApiError;
      setMessage({
        tone: "err",
        text: apiErr.detail ?? "Échec de l'upload.",
      });
    } finally {
      setUploading(false);
      if (fileInput.current) fileInput.current.value = "";
    }
  }

  const r = state?.reglement_interieur;

  return (
    <main className="space-y-6 p-8">
      <header className="space-y-1">
        <h1 className="font-display text-2xl text-ink-900">
          Documents officiels
        </h1>
        <p className="max-w-2xl text-sm text-ink-500">
          PDF officiels de la coopérative — joints automatiquement aux mails
          de bienvenue lors de l&apos;approbation d&apos;une adhésion.
        </p>
      </header>

      {message && (
        <div
          className={`rounded-md border p-3 text-sm ${
            message.tone === "ok"
              ? "border-emerald/30 bg-emerald/10 text-emerald-900"
              : "border-red-300 bg-red-50 text-red-900"
          }`}
        >
          {message.text}
        </div>
      )}

      <section className="rounded-lg border border-line-200 bg-paper p-6">
        <div className="flex items-start gap-4">
          <div className="rounded-lg bg-blue-700/10 p-3">
            <FileText className="h-6 w-6 text-blue-700" />
          </div>
          <div className="flex-1">
            <h2 className="font-display text-lg text-ink-900">
              Règlement intérieur
            </h2>
            <p className="text-sm text-ink-600">
              PDF joint à chaque mail de bienvenue (avec l&apos;attestation
              d&apos;adhésion), et consultable par les membres dans
              l&apos;application mobile et le portail (rubrique Carnet →
              « Règlement intérieur »).
            </p>

            {loading ? (
              <p className="mt-3 text-sm text-ink-500">Chargement…</p>
            ) : r?.uploaded ? (
              <div className="mt-3 space-y-2">
                <div className="flex items-center gap-2 text-sm">
                  <CheckCircle2 className="h-4 w-4 text-emerald" />
                  <span className="font-mono text-ink-900">{r.name}</span>
                  <span className="text-ink-500">
                    ({(r.size / 1024).toFixed(0)} Ko)
                  </span>
                </div>
                <p className="text-[12px] text-ink-500">
                  Uploadé{" "}
                  {r.uploaded_at
                    ? new Date(r.uploaded_at).toLocaleString("fr-FR", {
                        dateStyle: "short",
                        timeStyle: "short",
                      })
                    : ""}{" "}
                  {r.uploaded_by ? `par ${r.uploaded_by}` : ""}
                </p>
                {r.url && (
                  <div className="flex flex-wrap items-center gap-3">
                    <button
                      type="button"
                      onClick={() => setPreviewOpen(true)}
                      className="inline-flex items-center gap-1.5 text-sm font-medium text-blue-700 hover:text-blue-800"
                    >
                      <ZoomIn className="h-3.5 w-3.5" />
                      Aperçu du PDF
                    </button>
                    <a
                      href={r.url}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center gap-1.5 text-sm font-medium text-ink-500 hover:text-ink-700"
                    >
                      Télécharger →
                    </a>
                  </div>
                )}
              </div>
            ) : (
              <div className="mt-3 flex items-center gap-2 text-sm">
                <AlertCircle className="h-4 w-4 text-orange-700" />
                <span className="text-orange-900">
                  Pas encore uploadé — les mails de bienvenue partiront avec
                  seulement l&apos;attestation.
                </span>
              </div>
            )}

            <div className="mt-4 flex items-center gap-3">
              <input
                ref={fileInput}
                type="file"
                accept="application/pdf,.pdf"
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) onUpload(f);
                }}
                disabled={uploading}
                className="block w-full text-sm text-ink-600 file:mr-3 file:cursor-pointer file:rounded-md file:border-0 file:bg-blue-700 file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-white hover:file:bg-blue-800 disabled:opacity-50"
              />
              {uploading && (
                <span className="text-sm text-ink-500">Envoi…</span>
              )}
            </div>
            <p className="mt-1 text-[11px] text-ink-500">
              PDF uniquement · Max 10 Mo · Remplace le précédent
            </p>
          </div>
        </div>
      </section>

      {previewOpen && r?.url && (
        <DocumentPreview
          url={r.url}
          name={r.name || "Règlement intérieur"}
          subtitle="Règlement intérieur de la coopérative"
          onClose={() => setPreviewOpen(false)}
        />
      )}
    </main>
  );
}
