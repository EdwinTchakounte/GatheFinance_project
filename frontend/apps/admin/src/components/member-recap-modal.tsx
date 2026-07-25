"use client";

import { useState } from "react";
import { ChevronDown, FileDown } from "lucide-react";

import {
  DocumentPreview,
  DocumentThumbnail,
} from "@/components/document-preview";
import { Modal } from "@/components/modal";
import {
  adminApi,
  type ApiError,
  type Member,
  type MemberAdhesion,
} from "@/lib/api";


// ── Carte recap financier d'un membre ──────────────────────────────────────
// Consolide, en un coup d'œil : épargne (collecte + libre + placement),
// crédit en cours, et le solde net (épargne totale − crédit).
export function MemberRecapModal({
  member,
  onClose,
}: {
  member: Member | null;
  onClose: () => void;
}) {
  const [showAdh, setShowAdh] = useState(false);
  const [adh, setAdh] = useState<MemberAdhesion | null>(null);
  const [adhLoading, setAdhLoading] = useState(false);
  const [adhErr, setAdhErr] = useState<string | null>(null);

  async function toggleAdhesion() {
    if (showAdh) {
      setShowAdh(false);
      return;
    }
    setShowAdh(true);
    if (adh || !member) return;
    setAdhLoading(true);
    setAdhErr(null);
    try {
      setAdh(await adminApi.members.adhesion(member.id));
    } catch (e) {
      const err = e as ApiError;
      setAdhErr(
        err.status === 404
          ? "Aucune fiche d'adhésion liée à ce membre (adhésion legacy)."
          : err.detail ?? "Chargement impossible.",
      );
    } finally {
      setAdhLoading(false);
    }
  }

  if (!member) return null;
  const collecte = Number(member.epargne_collecte ?? 0);
  const libre = Number(member.epargne_classique_libre ?? 0);
  const placement = Number(member.epargne_placement ?? 0);
  const epargneTotal = Number(member.epargne_total ?? 0);
  const credit = Number(member.credit_encours ?? 0);
  const net = epargneTotal - credit;

  return (
    <Modal
      open
      onClose={onClose}
      title={`${member.prenom} ${member.nom}`}
      description={`N° ${member.numero_membre} · ${member.statut_display}`}
    >
      <div className="space-y-4">
        {/* Épargne détaillée */}
        <div>
          <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-ink-500">
            Épargne
          </p>
          <div className="space-y-1.5 rounded-md border border-line-200 bg-paper-soft/40 px-4 py-3">
            <RecapLine label="Collecte (journalière)" value={collecte} />
            <RecapLine label="Classique libre" value={libre} />
            <RecapLine label="Placement" value={placement} />
            <div className="mt-1.5">
              <RecapLine label="Épargne totale" value={epargneTotal} strong />
            </div>
          </div>
        </div>

        {/* Crédit */}
        <div>
          <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-ink-500">
            Crédit
          </p>
          <div className="rounded-md border border-line-200 bg-paper-soft/40 px-4 py-3">
            <RecapLine
              label="Crédit en cours"
              value={credit}
              tone={credit > 0 ? "terra" : undefined}
            />
          </div>
        </div>

        {/* Solde net */}
        <div
          className={
            "flex items-center justify-between rounded-md px-4 py-3 " +
            (net >= 0 ? "bg-emerald/10" : "bg-terra-50")
          }
        >
          <div>
            <p className="text-sm font-semibold text-ink-900">Solde net</p>
            <p className="text-xs text-ink-500">Épargne totale − crédit en cours</p>
          </div>
          <span
            className={
              "text-lg font-bold tabular-nums " +
              (net >= 0 ? "text-emerald" : "text-terra-700")
            }
          >
            {net.toLocaleString("fr-FR")} FCFA
          </span>
        </div>

        {credit > 0 ? (
          <p className="text-xs text-ink-500">
            Note : une partie de l'épargne classique peut être gelée en garantie
            tant qu'un crédit est actif (bloquée au retrait).
          </p>
        ) : null}

        <a
          href={adminApi.members.statementUrl(member.id)}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex w-full items-center justify-center gap-2 rounded-md border border-line-300 bg-white px-3.5 py-2.5 text-sm font-medium text-ink-800 transition-colors hover:border-blue-400 hover:text-blue-700"
        >
          <FileDown className="size-4" aria-hidden="true" />
          Télécharger le relevé PDF
        </a>

        {/* Voir plus — fiche d'adhésion (infos renseignées à la soumission) */}
        <button
          type="button"
          onClick={toggleAdhesion}
          className="flex w-full items-center justify-between rounded-md border border-line-200 px-3.5 py-2.5 text-sm font-medium text-ink-800 transition-colors hover:border-blue-400 hover:text-blue-700"
        >
          <span>Voir plus — fiche d&apos;adhésion</span>
          <ChevronDown
            className={"size-4 transition-transform " + (showAdh ? "rotate-180" : "")}
            aria-hidden="true"
          />
        </button>

        {showAdh ? (
          adhLoading ? (
            <p className="text-center text-sm text-ink-500">Chargement…</p>
          ) : adhErr ? (
            <p className="rounded-md bg-terra-50 px-3 py-2 text-sm text-terra-700">
              {adhErr}
            </p>
          ) : adh ? (
            <AdhesionDetails adh={adh} />
          ) : null
        ) : null}
      </div>
    </Modal>
  );
}


function AdhLine({ label, value }: { label: string; value?: string | null }) {
  if (!value) return null;
  return (
    <div className="flex justify-between gap-4 py-1 text-sm">
      <span className="text-ink-500">{label}</span>
      <span className="text-right font-medium text-ink-900">{value}</span>
    </div>
  );
}


function AdhesionDetails({ adh }: { adh: MemberAdhesion }) {
  const [preview, setPreview] = useState<{ url: string; label: string } | null>(
    null,
  );
  const pieces = Object.entries(adh.pieces).filter(([, url]) => Boolean(url)) as [
    string,
    string,
  ][];
  const pieceLabel: Record<string, string> = {
    cni_recto: "CNI recto",
    cni_verso: "CNI verso",
    plan_localisation: "Plan de localisation",
    photo_identite: "Photo d'identité",
  };
  const extraEntries = Object.entries(adh.extra_payload ?? {});

  return (
    <div className="space-y-4 rounded-md border border-line-200 bg-paper-soft/40 px-4 py-3">
      <p className="text-xs text-ink-500">
        Soumise le{" "}
        {new Date(adh.soumis_le).toLocaleDateString("fr-FR", {
          day: "2-digit",
          month: "short",
          year: "numeric",
        })}
        {adh.form_schema_version != null
          ? ` · formulaire v${adh.form_schema_version}`
          : ""}
      </p>

      <div>
        <p className="mb-1 text-xs font-semibold uppercase tracking-wider text-ink-500">
          Identité
        </p>
        <AdhLine label="Nom" value={adh.identity.nom} />
        <AdhLine label="Prénom" value={adh.identity.prenom} />
        <AdhLine label="Email" value={adh.identity.email} />
        <AdhLine label="Téléphone" value={adh.identity.phone} />
        <AdhLine label="WhatsApp" value={adh.identity.whatsapp} />
        <AdhLine label="Ville" value={adh.identity.city} />
        <AdhLine label="Quartier / localité" value={adh.identity.quartier_localite} />
        <AdhLine label="Statut pro." value={adh.identity.statut_pro} />
      </div>

      {adh.urgence.nom || adh.urgence.phone ? (
        <div>
          <p className="mb-1 text-xs font-semibold uppercase tracking-wider text-ink-500">
            Contact d&apos;urgence
          </p>
          <AdhLine label="Nom" value={adh.urgence.nom} />
          <AdhLine label="Lien" value={adh.urgence.lien} />
          <AdhLine label="Téléphone" value={adh.urgence.phone} />
        </div>
      ) : null}

      {adh.motivation ? (
        <div>
          <p className="mb-1 text-xs font-semibold uppercase tracking-wider text-ink-500">
            Motivation
          </p>
          <p className="whitespace-pre-wrap text-sm text-ink-800">{adh.motivation}</p>
        </div>
      ) : null}

      {extraEntries.length > 0 ? (
        <div>
          <p className="mb-1 text-xs font-semibold uppercase tracking-wider text-ink-500">
            Champs additionnels (formulaire)
          </p>
          {extraEntries.map(([k, v]) => (
            <AdhLine key={k} label={k} value={String(v)} />
          ))}
        </div>
      ) : null}

      {pieces.length > 0 ? (
        <div>
          <p className="mb-1 text-xs font-semibold uppercase tracking-wider text-ink-500">
            Pièces jointes
          </p>
          <div className="flex flex-wrap gap-3">
            {pieces.map(([k, url]) => {
              const label = pieceLabel[k] ?? k;
              return (
                <div key={k} className="flex w-24 flex-col items-center gap-1.5">
                  <DocumentThumbnail
                    url={url}
                    label={label}
                    size="sm"
                    onOpen={() => setPreview({ url, label })}
                  />
                  <span className="w-full truncate text-center text-[0.65rem] text-ink-600">
                    {label}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      ) : null}

      {preview && (
        <DocumentPreview
          url={preview.url}
          name={preview.label}
          subtitle={`Fiche d'adhésion · ${adh.identity.prenom} ${adh.identity.nom}`}
          onClose={() => setPreview(null)}
        />
      )}
    </div>
  );
}


function RecapLine({
  label,
  value,
  strong,
  tone,
}: {
  label: string;
  value: number;
  strong?: boolean;
  tone?: "terra";
}) {
  return (
    <div className="flex items-center justify-between">
      <span className={"text-sm " + (strong ? "font-semibold text-ink-900" : "text-ink-700")}>
        {label}
      </span>
      <span
        className={
          "tabular-nums " +
          (strong ? "font-semibold text-ink-900" : "text-ink-800") +
          (tone === "terra" ? " text-terra-700" : "")
        }
      >
        {value.toLocaleString("fr-FR")} FCFA
      </span>
    </div>
  );
}
