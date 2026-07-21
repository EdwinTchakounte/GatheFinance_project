"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { FileText, Paperclip, ZoomIn } from "lucide-react";

import {
  DocumentPreview,
  DocumentThumbnail,
} from "@/components/document-preview";
import { ExportMenu } from "@/components/export-menu";
import { adminApi, type BRCDocument } from "@/lib/api";
import type { ExportColumn } from "@/lib/export";
import { StatusPill } from "@/components/status-pill";


/**
 * Justificatifs BRC — VUE DE LECTURE.
 *
 * Le justificatif BRC est purement **documentaire** : il n'y a plus de statut
 * BRC à « valider » ici (les boutons approuver/rejeter ont été retirés). Le
 * comité consulte simplement la pièce (contrat CGA BRC, certificat CFP BRC…)
 * quand il instruit / décide la **demande de crédit** correspondante — c'est
 * là que se prend la décision, pas sur un statut BRC séparé.
 */
export default function BRCPage() {
  return <Inner />;
}

function Inner() {
  const [filter, setFilter] = useState<
    "en_attente" | "valide" | "rejete" | ""
  >("");
  const [items, setItems] = useState<BRCDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [previewTarget, setPreviewTarget] = useState<BRCDocument | null>(null);

  async function reload() {
    setLoading(true);
    try {
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

  const exportColumns: ExportColumn<BRCDocument>[] = [
    { key: "id", label: "ID", value: (d) => d.id },
    { key: "membre", label: "Membre", value: (d) => `${d.member_prenom} ${d.member_nom}` },
    { key: "numero", label: "N° membre", value: (d) => d.member_numero },
    { key: "fichier", label: "Fichier", value: (d) => d.nom_original || `Document #${d.id}` },
    { key: "taille_ko", label: "Taille (Ko)", value: (d) => Math.round(d.taille / 1024) },
    { key: "provenance", label: "Provenance", value: (d) => d.champ_source_display },
    {
      key: "demande_credit",
      label: "Demande de crédit",
      value: (d) => (d.loan_request_id ? `#${d.loan_request_id}` : ""),
    },
    { key: "statut", label: "Statut", value: (d) => d.statut_display },
    {
      key: "depose_le",
      label: "Déposé le",
      value: (d) => new Date(d.created_at).toLocaleDateString("fr-FR"),
    },
  ];

  return (
    <section className="space-y-6">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="space-y-1">
          <h1 className="font-display text-2xl text-ink-900">
            Justificatifs BRC
          </h1>
          <p className="max-w-2xl text-sm text-ink-500">
            Consultation des pièces BRC (contrat CGA BRC, certificat CFP BRC…)
            déposées par les membres ou jointes à leurs demandes de crédit. Vue
            documentaire : la décision se prend sur la demande de crédit
            correspondante, pas ici.
          </p>
        </div>
        <ExportMenu
          filenamePrefix="brc-justificatifs"
          title="Justificatifs BRC"
          subtitle={`Filtre : ${filter || "tous"}`}
          columns={exportColumns}
          rows={items}
        />
      </header>

      <div className="flex flex-wrap items-center gap-2">
        {(
          [
            ["", "Tous"],
            ["en_attente", "Sans décision"],
            ["valide", "Historique validés"],
            ["rejete", "Historique rejetés"],
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

      <section className="rounded-2xl border border-line-200 bg-paper">
        {loading && (
          <p className="px-6 py-12 text-center text-sm text-ink-500">
            Chargement…
          </p>
        )}
        {!loading && items.length === 0 && (
          <p className="px-6 py-12 text-center text-sm text-ink-500">
            Aucun justificatif à ce filtre.
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

                <div className="min-w-[260px] flex-1 space-y-1.5">
                  <div className="flex flex-wrap items-center gap-2 text-sm font-semibold text-ink-900">
                    {doc.member_prenom} {doc.member_nom}
                    <span className="rounded-full bg-paper-soft px-2 py-0.5 text-xs font-medium text-ink-500">
                      {doc.member_numero}
                    </span>
                    <StatusPill statut={doc.statut} label={doc.statut_display} />
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
                      <button
                        onClick={() => setPreviewTarget(doc)}
                        className="inline-flex items-center gap-1 text-blue-700 hover:text-blue-800"
                      >
                        <ZoomIn className="h-3 w-3" />
                        Aperçu plein écran
                      </button>
                    )}
                    <span className="inline-flex items-center gap-1">
                      <Paperclip className="h-3 w-3" />
                      {doc.champ_source_display}
                    </span>
                    {doc.loan_request_id ? (
                      <Link
                        href="/loan-requests"
                        className="inline-flex items-center gap-1 text-blue-700 hover:underline"
                      >
                        Demande de crédit #{doc.loan_request_id}
                      </Link>
                    ) : null}
                  </div>
                  {doc.statut === "rejete" && doc.motif_rejet && (
                    <p className="rounded-md bg-red-50 px-3 py-2 text-xs text-red-700">
                      <strong>Motif (historique) :</strong> {doc.motif_rejet}
                    </p>
                  )}
                  <p className="text-xs text-ink-400">
                    Déposé le{" "}
                    {new Date(doc.created_at).toLocaleDateString("fr-FR")}
                  </p>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

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
