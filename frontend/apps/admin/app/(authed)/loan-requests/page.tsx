"use client";

import { useEffect, useState } from "react";
import { Check, Coins, FileText, Scale, Send, X } from "lucide-react";

import { buttonClasses, SkeletonList } from "@gathe/ui";

import { CashInModal, type CashInPrefill } from "@/components/cash-in-modal";
import { DataTable, type DataColumn } from "@/components/data-table";
import { DocumentLink } from "@/components/document-preview";
import { Modal, ModalField, modalInputClass } from "@/components/modal";
import { adminApi, type ApiError, type LoanRequest } from "@/lib/api";
import { fullName } from "@/lib/name";
import { StatusPill } from "@/components/status-pill";


function formatXAF(amount: string): string {
  const n = Number(amount);
  if (Number.isNaN(n)) return amount;
  return n.toLocaleString("fr-FR", { maximumFractionDigits: 0 }) + " XAF";
}


function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("fr-FR", {
    day: "2-digit",
    month: "short",
    year: "2-digit",
  });
}


function defaultFirstDueDate(): string {
  const d = new Date();
  d.setMonth(d.getMonth() + 1);
  return d.toISOString().slice(0, 10);
}


export default function LoanRequestsPage() {
  return <Inner />;
}

type LoanRequestFilter =
  | "en_attente"
  | "en_attente_avaliste"
  | "en_validation_campagne"
  | "en_instruction"
  | "approuvee_provisoire"
  | "approuvee"
  | "rejetee"
  | "";

function Inner() {
  // Defaut sur "en_attente" : les demandes fraichement soumises restent
  // bloquees en attente du paiement des frais d'etude (CH-7). C'est la
  // file la plus urgente cote admin (relance + cash-in agence).
  const [filter, setFilter] = useState<LoanRequestFilter>("en_attente");
  const [items, setItems] = useState<LoanRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [actingId, setActingId] = useState<number | null>(null);
  const [message, setMessage] = useState<{ tone: "ok" | "err"; text: string } | null>(null);

  const [approveTarget, setApproveTarget] = useState<LoanRequest | null>(null);
  const [rejectTarget, setRejectTarget] = useState<LoanRequest | null>(null);
  const [disburseTarget, setDisburseTarget] = useState<LoanRequest | null>(null);
  // CH-6 — Workflow double approbation : provisoire → visite terrain → définitive.
  const [provisionalTarget, setProvisionalTarget] = useState<LoanRequest | null>(null);
  const [fieldVisitTarget, setFieldVisitTarget] = useState<LoanRequest | null>(null);
  // Cash-in admin frais d'etude (CH-7) : encaisser les frais en agence quand
  // le membre paie en especes au lieu de Tara MoMo.
  const [cashInTarget, setCashInTarget] = useState<LoanRequest | null>(null);
  // L4 — Évaluation du bien mis en garantie matérielle (informel, non bloquant).
  const [guaranteeTarget, setGuaranteeTarget] = useState<LoanRequest | null>(null);

  async function reload() {
    setLoading(true);
    try {
      adminApi.primeCsrf().catch(() => undefined);
      const list = await adminApi.loanRequests.list(filter || undefined);
      setItems(list);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { reload(); /* eslint-disable-next-line */ }, [filter]);

  async function submitApprove(payload: { taux_annuel: number; date_premiere_echeance: string }) {
    if (!approveTarget) return;
    setActingId(approveTarget.id);
    try {
      await adminApi.loanRequests.decide(approveTarget.id, {
        decision: "approuvee",
        ...payload,
      });
      setMessage({ tone: "ok", text: `Demande #${approveTarget.id} approuvée — Loan créé.` });
      setApproveTarget(null);
      await reload();
    } catch (err) {
      const apiErr = err as ApiError;
      setMessage({ tone: "err", text: apiErr.detail ?? "Approbation impossible." });
    } finally {
      setActingId(null);
    }
  }

  async function submitReject(motif: string) {
    if (!rejectTarget) return;
    setActingId(rejectTarget.id);
    try {
      await adminApi.loanRequests.decide(rejectTarget.id, { decision: "rejetee", motif_rejet: motif });
      setMessage({ tone: "ok", text: `Demande #${rejectTarget.id} rejetée.` });
      setRejectTarget(null);
      await reload();
    } catch (err) {
      const apiErr = err as ApiError;
      setMessage({ tone: "err", text: apiErr.detail ?? "Rejet impossible." });
    } finally {
      setActingId(null);
    }
  }

  async function deleteRequest(r: LoanRequest) {
    const motif = window.prompt(
      `Supprimer définitivement la demande #${r.id} (et le crédit associé) ?\n` +
        "Cette action est tracée dans un fichier d'audit. Motif (optionnel) :",
      "",
    );
    if (motif === null) return; // annulé
    setActingId(r.id);
    try {
      await adminApi.loanRequests.remove(r.id, motif || undefined);
      setMessage({ tone: "ok", text: `Demande #${r.id} supprimée (tracée).` });
      await reload();
    } catch (err) {
      const apiErr = err as ApiError;
      setMessage({ tone: "err", text: apiErr.detail ?? "Suppression impossible." });
    } finally {
      setActingId(null);
    }
  }

  async function submitProvisional(avis: string) {
    if (!provisionalTarget) return;
    setActingId(provisionalTarget.id);
    try {
      await adminApi.loanRequests.decideProvisional(provisionalTarget.id, {
        avis_provisoire: avis,
      });
      setMessage({
        tone: "ok",
        text: `Demande #${provisionalTarget.id} approuvée provisoirement — à charge du staff de réaliser la visite terrain.`,
      });
      setProvisionalTarget(null);
      await reload();
    } catch (err) {
      const apiErr = err as ApiError;
      setMessage({ tone: "err", text: apiErr.detail ?? "Approbation provisoire impossible." });
    } finally {
      setActingId(null);
    }
  }

  async function submitFieldVisit(payload: {
    outcome: "favorable" | "defavorable" | "a_revoir";
    note: string;
  }) {
    if (!fieldVisitTarget) return;
    setActingId(fieldVisitTarget.id);
    try {
      await adminApi.loanRequests.fieldVisit(fieldVisitTarget.id, payload);
      setMessage({
        tone: "ok",
        text: `Visite terrain enregistrée pour la demande #${fieldVisitTarget.id} (${payload.outcome}).`,
      });
      setFieldVisitTarget(null);
      await reload();
    } catch (err) {
      const apiErr = err as ApiError;
      setMessage({ tone: "err", text: apiErr.detail ?? "Enregistrement visite impossible." });
    } finally {
      setActingId(null);
    }
  }

  async function submitGuaranteeEval(payload: { valeur_estimee: number; note: string }) {
    if (!guaranteeTarget) return;
    setActingId(guaranteeTarget.id);
    try {
      await adminApi.loanRequests.evaluateGuarantee(guaranteeTarget.id, {
        valeur_estimee: payload.valeur_estimee,
        note: payload.note || undefined,
      });
      setMessage({
        tone: "ok",
        text: `Évaluation du bien enregistrée pour la demande #${guaranteeTarget.id} (${formatXAF(String(payload.valeur_estimee))}).`,
      });
      setGuaranteeTarget(null);
      await reload();
    } catch (err) {
      const apiErr = err as ApiError;
      setMessage({ tone: "err", text: apiErr.detail ?? "Évaluation impossible." });
    } finally {
      setActingId(null);
    }
  }

  async function submitDisburse(payload: { recipient_phone: string; network: "MTN" | "ORANGE" | "WAVE" | "AIRTEL" }) {
    if (!disburseTarget?.loan) return;
    setActingId(disburseTarget.id);
    try {
      const res = await adminApi.loans.disburseTara(disburseTarget.loan.id, payload);
      setMessage({
        tone: "ok",
        text: `Payout Tara initié pour ${res.numero_dossier} (Payment #${res.payment_id}). En attente du webhook.`,
      });
      setDisburseTarget(null);
      await reload();
    } catch (err) {
      const apiErr = err as ApiError;
      setMessage({ tone: "err", text: apiErr.detail ?? "Décaissement impossible." });
    } finally {
      setActingId(null);
    }
  }

  const columns: DataColumn<LoanRequest>[] = [
    {
      key: "demande",
      label: "Demande",
      text: (r) => `#${r.id}`,
      render: (r) => <span className="font-mono text-xs text-ink-600">#{r.id}</span>,
    },
    {
      key: "membre",
      label: "Membre",
      locked: true,
      text: (r) =>
        r.member
          ? `${fullName(r.member.prenom, r.member.nom)} ${r.member.numero_membre} ${r.member.telephone ?? ""}`
          : "",
      render: (r) =>
        r.member ? (
          <div className="min-w-[10rem]">
            <p className="text-sm font-medium text-ink-900">
              {fullName(r.member.prenom, r.member.nom)}
            </p>
            <p className="font-mono text-[11px] text-ink-500">
              {r.member.numero_membre}
              {r.member.telephone ? ` · ${r.member.telephone}` : ""}
            </p>
          </div>
        ) : (
          <span className="text-xs text-ink-400"></span>
        ),
    },
    {
      // E-mail de l'adhérent — masqué par défaut, activable via le menu
      // « Colonnes » (utile pour contacter / vérifier l'identité au versement).
      key: "email",
      label: "E-mail",
      defaultVisible: false,
      text: (r) => r.member?.email ?? "",
      render: (r) =>
        r.member?.email ? (
          <a
            href={`mailto:${r.member.email}`}
            className="text-xs text-blue-700 hover:underline"
          >
            {r.member.email}
          </a>
        ) : (
          <span className="text-xs text-ink-400">—</span>
        ),
    },
    {
      // Prévisualisation du « mode employé » sur chaque crédit.
      key: "voie",
      label: "Voie",
      text: (r) => r.voie_display ?? "",
      render: (r) => <VoieBadge r={r} />,
    },
    {
      key: "montant",
      label: "Montant",
      numeric: true,
      align: "right",
      text: (r) => r.montant_demande,
      render: (r) => (
        <span className="font-mono font-medium tabular-nums">
          {formatXAF(r.montant_demande)}
        </span>
      ),
    },
    {
      key: "duree",
      label: "Durée",
      numeric: true,
      text: (r) => String(r.duree_mois),
      render: (r) => <span className="whitespace-nowrap">{r.duree_mois} mois</span>,
    },
    {
      key: "objet",
      label: "Objet",
      text: (r) => r.motif,
      render: (r) => (
        <div className="max-w-md">
          <p className="line-clamp-3 text-sm">{r.motif}</p>
          <ProfilEmprunteurBadges r={r} />
          <GarantieMaterielleSection r={r} />
        </div>
      ),
    },
    {
      key: "date",
      label: "Reçue le",
      defaultVisible: false,
      text: (r) => formatDate(r.date_soumission),
      render: (r) => (
        <div className="whitespace-nowrap">
          <span>{formatDate(r.date_soumission)}</span>
          {r.date_limite_etude ? (
            <p className="mt-0.5 text-[11px] text-ink-500">
              Étude avant le {formatDate(r.date_limite_etude)}
            </p>
          ) : null}
        </div>
      ),
    },
    {
      key: "statut",
      label: "Statut",
      text: (r) => r.statut_display,
      render: (r) => (
        <div>
          <StatusPill statut={r.statut} label={r.statut_display} />
          {r.field_visit_outcome ? (
            <p className="mt-1 text-[11px] font-medium">
              <span className="text-ink-500">Visite : </span>
              <span
                className={
                  r.field_visit_outcome === "favorable"
                    ? "text-emerald"
                    : r.field_visit_outcome === "defavorable"
                      ? "text-terra-700"
                      : "text-ink-700"
                }
              >
                {r.field_visit_outcome === "favorable"
                  ? "favorable"
                  : r.field_visit_outcome === "defavorable"
                    ? "défavorable"
                    : "à revoir"}
              </span>
            </p>
          ) : null}
          {r.motif_rejet ? (
            <p className="mt-1 max-w-[14rem] text-xs text-terra-700">{r.motif_rejet}</p>
          ) : null}
        </div>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      <header className="mb-8 flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="font-display text-[0.7rem] font-semibold uppercase tracking-[0.18em] text-terra-600">
            Crédits
          </p>
          <h1 className="mt-2 font-editorial text-3xl font-medium text-ink-900">
            Demandes de crédit
          </h1>
          <p className="mt-1 text-sm text-ink-600">
            Décide en tant que président du comité — approuver crée le crédit + l'échéancier.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-1 rounded-md border border-line-200 bg-paper p-1">
          {[
            { v: "en_attente", l: "Frais à percevoir" },
            { v: "en_attente_avaliste", l: "Attente avaliste" },
            { v: "en_validation_campagne", l: "Validation campagne" },
            { v: "en_instruction", l: "En instruction" },
            { v: "approuvee_provisoire", l: "Provisoires" },
            { v: "approuvee", l: "Approuvées" },
            { v: "rejetee", l: "Rejetées" },
            { v: "", l: "Toutes" },
          ].map((opt) => (
            <button
              key={opt.v}
              type="button"
              onClick={() => setFilter(opt.v as LoanRequestFilter)}
              className={[
                "rounded px-3 py-1.5 text-xs font-medium transition-colors",
                filter === opt.v ? "bg-blue-700 text-white" : "text-ink-700 hover:text-blue-700",
              ].join(" ")}
            >
              {opt.l}
            </button>
          ))}
        </div>
      </header>

      {message ? (
        <div className={
          "mb-5 rounded-md px-4 py-2.5 text-sm " +
          (message.tone === "ok"
            ? "bg-emerald/10 text-emerald border border-emerald/30"
            : "bg-terra-50/60 text-terra-700 border border-terra-400/40")
        }>
          {message.text}
        </div>
      ) : null}

      {loading ? (
        <SkeletonList count={6} cardClassName="h-14" />
      ) : (
        <DataTable
          columns={columns}
          rows={items}
          rowKey={(r) => r.id}
          emptyLabel="Aucune demande dans ce filtre."
          exportFilename="demandes-credit"
          exportTitle="Demandes de crédit — GATHE Finance"
          exportSubtitle={`Filtre : ${filter || "toutes"}`}
          actions={(r) =>
            r.statut === "en_attente" ? (
              <div className="flex flex-col items-end gap-1.5">
                <button
                  type="button"
                  onClick={() => setCashInTarget(r)}
                  disabled={actingId === r.id}
                  className={buttonClasses({ variant: "primary", size: "sm" })}
                  title="Encaisser les frais d'etude en agence (cash-in)"
                >
                  <Coins className="size-3.5" aria-hidden="true" />Encaisser frais
                </button>
                <p className="max-w-[14rem] text-right text-[11px] text-ink-500">
                  La demande passera en instruction des reception des frais (Tara ou cash-in agence).
                </p>
                <a
                  href={adminApi.loans.noteUrl(r.id)}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 text-[11px] font-medium text-blue-700 hover:underline"
                >
                  <FileText className="size-3" />Note PDF
                </a>
              </div>
            ) : r.statut === "en_instruction" ? (
              <div className="flex flex-col items-end gap-1.5">
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => setProvisionalTarget(r)}
                    disabled={actingId === r.id}
                    className={buttonClasses({ variant: "success", size: "sm" })}
                  >
                    <Check className="size-3.5" aria-hidden="true" />Approbation provisoire
                  </button>
                  <button
                    type="button"
                    onClick={() => setRejectTarget(r)}
                    disabled={actingId === r.id}
                    className={buttonClasses({ variant: "ghost", size: "sm" })}
                  >
                    <X className="size-3.5" aria-hidden="true" />Rejeter
                  </button>
                </div>
                {r.garantie_materielle ? (
                  <button
                    type="button"
                    onClick={() => setGuaranteeTarget(r)}
                    disabled={actingId === r.id}
                    className={buttonClasses({ variant: "ghost", size: "sm" })}
                    title="Enregistrer la valeur estimée du bien mis en garantie (informel, n'affecte pas la décision)"
                  >
                    <Scale className="size-3.5" aria-hidden="true" />Évaluer le bien
                  </button>
                ) : null}
                <a
                  href={adminApi.loans.noteUrl(r.id)}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 text-[11px] font-medium text-blue-700 hover:underline"
                >
                  <FileText className="size-3" />Note PDF
                </a>
              </div>
            ) : r.statut === "approuvee_provisoire" ? (
              <div className="flex flex-col items-end gap-1.5">
                {!r.field_visit_outcome ? (
                  <button
                    type="button"
                    onClick={() => setFieldVisitTarget(r)}
                    disabled={actingId === r.id}
                    className={buttonClasses({ variant: "primary", size: "sm" })}
                  >
                    Visite terrain à effectuer
                  </button>
                ) : (
                  <div className="flex gap-2">
                    {r.field_visit_outcome === "favorable" ? (
                      <button
                        type="button"
                        onClick={() => setApproveTarget(r)}
                        disabled={actingId === r.id}
                        className={buttonClasses({ variant: "success", size: "sm" })}
                      >
                        <Check className="size-3.5" aria-hidden="true" />Décision définitive
                      </button>
                    ) : null}
                    <button
                      type="button"
                      onClick={() => setRejectTarget(r)}
                      disabled={actingId === r.id}
                      className={buttonClasses({ variant: "ghost", size: "sm" })}
                    >
                      <X className="size-3.5" aria-hidden="true" />Rejeter
                    </button>
                  </div>
                )}
                <a
                  href={adminApi.loans.noteUrl(r.id)}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 text-[11px] font-medium text-blue-700 hover:underline"
                >
                  <FileText className="size-3" />Note PDF
                </a>
                <button
                  type="button"
                  onClick={() => deleteRequest(r)}
                  disabled={actingId === r.id}
                  className="inline-flex items-center gap-1 text-[11px] font-medium text-terra-700 hover:underline disabled:opacity-50"
                  title="Supprimer la demande (tracé dans l'audit)"
                >
                  <X className="size-3" />Supprimer
                </button>
              </div>
            ) : r.statut === "approuvee" && r.loan ? (
              <div className="flex flex-col items-end gap-1.5">
                <p className="font-mono text-xs text-ink-600">{r.loan.numero_dossier}</p>
                {r.loan.disbursed ? (
                  <span className="pill pill-success">Décaissé</span>
                ) : r.loan.disbursement_pending ? (
                  <span className="pill pill-warning">Payout en attente</span>
                ) : (
                  <button
                    type="button"
                    onClick={() => setDisburseTarget(r)}
                    disabled={actingId === r.id}
                    className={buttonClasses({ variant: "primary", size: "sm" })}
                  >
                    <Send className="size-3.5" aria-hidden="true" />Décaisser via Tara
                  </button>
                )}
                <a
                  href={adminApi.loans.noteUrl(r.id)}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 text-[11px] font-medium text-blue-700 hover:underline"
                >
                  <FileText className="size-3" />Note PDF
                </a>
                <button
                  type="button"
                  onClick={() => deleteRequest(r)}
                  disabled={actingId === r.id}
                  className="inline-flex items-center gap-1 text-[11px] font-medium text-terra-700 hover:underline disabled:opacity-50"
                  title="Supprimer la demande / le crédit (tracé dans l'audit)"
                >
                  <X className="size-3" />Supprimer
                </button>
              </div>
            ) : (
              <div className="flex flex-col items-end gap-1.5">
                <span className="text-xs text-ink-400"></span>
                <a
                  href={adminApi.loans.noteUrl(r.id)}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 text-[11px] font-medium text-blue-700 hover:underline"
                >
                  <FileText className="size-3" />Note PDF
                </a>
                <button
                  type="button"
                  onClick={() => deleteRequest(r)}
                  disabled={actingId === r.id}
                  className="inline-flex items-center gap-1 text-[11px] font-medium text-terra-700 hover:underline disabled:opacity-50"
                  title="Supprimer la demande (tracé dans l'audit)"
                >
                  <X className="size-3" />Supprimer
                </button>
              </div>
            )
          }
        />
      )}

      <ApproveLoanModal
        target={approveTarget}
        onClose={() => setApproveTarget(null)}
        onSubmit={submitApprove}
        submitting={actingId !== null}
      />
      <RejectLoanModal
        target={rejectTarget}
        onClose={() => setRejectTarget(null)}
        onSubmit={submitReject}
        submitting={actingId !== null}
      />
      <DisburseTaraModal
        target={disburseTarget}
        onClose={() => setDisburseTarget(null)}
        onSubmit={submitDisburse}
        submitting={actingId !== null}
      />
      <ProvisionalApproveModal
        target={provisionalTarget}
        onClose={() => setProvisionalTarget(null)}
        onSubmit={submitProvisional}
        submitting={actingId !== null}
      />
      <FieldVisitModal
        target={fieldVisitTarget}
        onClose={() => setFieldVisitTarget(null)}
        onSubmit={submitFieldVisit}
        submitting={actingId !== null}
      />
      <GuaranteeEvalModal
        target={guaranteeTarget}
        onClose={() => setGuaranteeTarget(null)}
        onSubmit={submitGuaranteeEval}
        submitting={actingId !== null}
      />

      {/* Cash-in frais d'etude (CH-7). Pre-remplit membre + type + montant
          a partir de la demande selectionnee. L'admin peut tout editer. */}
      <CashInModal
        open={cashInTarget !== null}
        onClose={() => setCashInTarget(null)}
        onSuccess={(text) => {
          setMessage({ tone: "ok", text });
          setCashInTarget(null);
          void reload();
        }}
        prefill={
          cashInTarget && cashInTarget.member
            ? ({
                // LoanRequest.member expose `telephone` (champ Django) alors
                // que le type Member admin utilise `phone` : on traduit ici.
                member: {
                  id: cashInTarget.member.id,
                  numero_membre: cashInTarget.member.numero_membre,
                  nom: cashInTarget.member.nom,
                  prenom: cashInTarget.member.prenom,
                  phone: cashInTarget.member.telephone,
                },
                type: "frais_demande_credit",
                // Montant prérempli depuis le tarif autoritaire (FeeType /
                // campagne) exposé sur la demande — l'admin n'a rien à saisir.
                montant: cashInTarget.frais_etude_montant ?? undefined,
                note: `Frais d'etude demande #${cashInTarget.id}`,
              } satisfies CashInPrefill)
            : undefined
        }
      />
    </div>
  );
}


// CH-6 — Modal Approbation provisoire (avis du comité avant visite terrain).
function ProvisionalApproveModal({
  target,
  onClose,
  onSubmit,
  submitting,
}: {
  target: LoanRequest | null;
  onClose: () => void;
  onSubmit: (avis: string) => void;
  submitting: boolean;
}) {
  const [avis, setAvis] = useState("");
  useEffect(() => {
    if (target) setAvis("");
  }, [target]);
  if (!target) return null;
  const trimmed = avis.trim();
  return (
    <Modal
      open
      onClose={onClose}
      title="Approbation provisoire — comité"
      description={`Demande #${target.id} · ${formatXAF(target.montant_demande)} · ${target.duree_mois} mois`}
      footer={
        <>
          <button
            type="button"
            onClick={onClose}
            disabled={submitting}
            className={buttonClasses({ variant: "ghost" })}
          >
            Annuler
          </button>
          <button
            type="button"
            disabled={submitting || trimmed.length < 5}
            onClick={() => onSubmit(trimmed)}
            className={buttonClasses({ variant: "success" })}
          >
            {submitting ? "Enregistrement…" : "Approuver provisoirement"}
          </button>
        </>
      }
    >
      <ModalField label="Avis du comité (motivation provisoire)">
        <textarea
          value={avis}
          onChange={(e) => setAvis(e.target.value)}
          placeholder="Dossier solide, sous réserve d'une visite favorable…"
          rows={4}
          className={modalInputClass}
        />
      </ModalField>
      <p className="mt-2 text-xs text-ink-500">
        La demande passe en <span className="font-medium">approuvée provisoirement</span>.
        Le staff devra ensuite enregistrer une visite terrain avant la décision définitive.
      </p>
    </Modal>
  );
}


// CH-6 — Modal Visite terrain (outcome favorable / défavorable / à revoir + note).
function FieldVisitModal({
  target,
  onClose,
  onSubmit,
  submitting,
}: {
  target: LoanRequest | null;
  onClose: () => void;
  onSubmit: (payload: {
    outcome: "favorable" | "defavorable" | "a_revoir";
    note: string;
  }) => void;
  submitting: boolean;
}) {
  const [outcome, setOutcome] = useState<"favorable" | "defavorable" | "a_revoir">("favorable");
  const [note, setNote] = useState("");
  useEffect(() => {
    if (target) {
      setOutcome("favorable");
      setNote("");
    }
  }, [target]);
  if (!target) return null;
  const trimmed = note.trim();
  return (
    <Modal
      open
      onClose={onClose}
      title="Visite terrain — compte-rendu"
      description={`Demande #${target.id} · ${formatXAF(target.montant_demande)}`}
      footer={
        <>
          <button
            type="button"
            onClick={onClose}
            disabled={submitting}
            className={buttonClasses({ variant: "ghost" })}
          >
            Annuler
          </button>
          <button
            type="button"
            disabled={submitting || trimmed.length < 5}
            onClick={() => onSubmit({ outcome, note: trimmed })}
            className={buttonClasses({ variant: "primary" })}
          >
            {submitting ? "Enregistrement…" : "Enregistrer la visite"}
          </button>
        </>
      }
    >
      <ModalField label="Verdict de la visite">
        <div className="flex flex-col gap-1.5">
          {[
            { v: "favorable", l: "Favorable — peut être approuvée définitivement" },
            { v: "defavorable", l: "Défavorable — propose le rejet" },
            { v: "a_revoir", l: "À revoir — informations à compléter" },
          ].map((opt) => (
            <label key={opt.v} className="flex items-center gap-2 text-sm">
              <input
                type="radio"
                name="outcome"
                value={opt.v}
                checked={outcome === opt.v}
                onChange={() =>
                  setOutcome(opt.v as "favorable" | "defavorable" | "a_revoir")
                }
              />
              {opt.l}
            </label>
          ))}
        </div>
      </ModalField>
      <ModalField label="Observations terrain">
        <textarea
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder="Activité réelle, local visité, ressenti général…"
          rows={4}
          className={modalInputClass}
        />
      </ModalField>
    </Modal>
  );
}


function DisburseTaraModal({
  target,
  onClose,
  onSubmit,
  submitting,
}: {
  target: LoanRequest | null;
  onClose: () => void;
  onSubmit: (payload: { recipient_phone: string; network: "MTN" | "ORANGE" | "WAVE" | "AIRTEL" }) => void;
  submitting: boolean;
}) {
  const [phone, setPhone] = useState("");
  const [network, setNetwork] = useState<"MTN" | "ORANGE" | "WAVE" | "AIRTEL">("MTN");

  useEffect(() => {
    if (target) {
      setPhone("");
      setNetwork("MTN");
    }
  }, [target]);

  const open = target !== null;
  const trimmedPhone = phone.replace(/\s+/g, "");
  const digitsOnly = trimmedPhone.replace(/\D+/g, "");
  const phoneValid = digitsOnly.length >= 9;
  const canSubmit = !submitting && phoneValid;

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Décaisser via Tara"
      description={
        target?.loan
          ? `Crédit ${target.loan.numero_dossier} — ${formatXAF(target.montant_demande)}`
          : undefined
      }
      tone="info"
      footer={
        <>
          <button
            type="button"
            onClick={onClose}
            className={buttonClasses({ variant: "ghost", size: "sm" })}
          >
            Annuler
          </button>
          <button
            type="button"
            onClick={() => canSubmit && onSubmit({ recipient_phone: trimmedPhone, network })}
            disabled={!canSubmit}
            className={buttonClasses({ variant: "primary", size: "sm" })}
          >
            Lancer le payout
          </button>
        </>
      }
    >
      <div className="space-y-4">
        <ModalField
          label="Numéro Mobile Money du membre"
          hint="Format Cameroun. Le provider Tara normalise automatiquement (237 préfixé)."
        >
          <input
            type="tel"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            placeholder="237 6 99 00 00 00"
            className={modalInputClass}
            autoFocus
          />
        </ModalField>
        <ModalField label="Opérateur" hint="Réseau Mobile Money correspondant au numéro saisi.">
          <select
            value={network}
            onChange={(e) =>
              setNetwork(e.target.value as "MTN" | "ORANGE" | "WAVE" | "AIRTEL")
            }
            className={modalInputClass}
          >
            <option value="MTN">MTN Mobile Money</option>
            <option value="ORANGE">Orange Money</option>
            <option value="WAVE">Wave</option>
            <option value="AIRTEL">Airtel Money</option>
          </select>
        </ModalField>
        <p className="rounded-md border border-blue-700/20 bg-blue-100/40 px-3 py-2 text-xs text-blue-900">
          Le Payment passera en <strong>en_attente</strong>. La bascule du crédit en <strong>actif</strong>{" "}
          + la date de décaissement seront posées par le webhook Tara (`_hook_decaissement`).
        </p>
      </div>
    </Modal>
  );
}


function ApproveLoanModal({
  target,
  onClose,
  onSubmit,
  submitting,
}: {
  target: LoanRequest | null;
  onClose: () => void;
  onSubmit: (payload: { taux_annuel: number; date_premiere_echeance: string }) => void;
  submitting: boolean;
}) {
  // Taux par défaut = le taux d'intérêt crédit CONFIGURÉ par l'admin (Paramètres
  // → Frais & taux, RateParam LOAN_INTEREST). On ne code plus 0.12 en dur : le
  // taux est piloté depuis une source unique. Fallback réglementaire : 0.10.
  const [tauxStr, setTauxStr] = useState("0.10");
  const [dateStr, setDateStr] = useState(defaultFirstDueDate());
  const [localError, setLocalError] = useState<string | null>(null);

  useEffect(() => {
    if (!target) return;
    setDateStr(defaultFirstDueDate());
    setLocalError(null);
    let cancelled = false;
    // Pré-remplit avec le taux configuré (une seule source de vérité).
    adminApi.costs
      .config()
      .then((cfg) => {
        if (cancelled) return;
        const rate = cfg.rates.find((r) => r.code === "LOAN_INTEREST");
        if (rate?.valeur != null) setTauxStr(String(Number(rate.valeur)));
      })
      .catch(() => {
        /* garde le fallback réglementaire 0.10 */
      });
    return () => {
      cancelled = true;
    };
  }, [target]);

  const open = target !== null;
  const taux = Number(tauxStr);
  const tauxValid = Number.isFinite(taux) && taux >= 0 && taux <= 1;
  const dateValid = /^\d{4}-\d{2}-\d{2}$/.test(dateStr);
  const canSubmit = !submitting && tauxValid && dateValid;

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Approuver la demande de crédit"
      description={
        target
          ? `Montant : ${formatXAF(target.montant_demande)} · Durée : ${target.duree_mois} mois`
          : undefined
      }
      tone="success"
      footer={
        <>
          <button
            type="button"
            onClick={onClose}
            className={buttonClasses({ variant: "ghost", size: "sm" })}
          >
            Annuler
          </button>
          <button
            type="button"
            onClick={() => {
              if (!tauxValid) {
                setLocalError("Taux invalide (attendu entre 0 et 1 — ex. 0.10 pour 10%).");
                return;
              }
              if (!dateValid) {
                setLocalError("Date invalide (format attendu AAAA-MM-JJ).");
                return;
              }
              onSubmit({ taux_annuel: taux, date_premiere_echeance: dateStr });
            }}
            disabled={!canSubmit}
            className={buttonClasses({ variant: "success", size: "sm" })}
          >
            <Check className="size-3.5" aria-hidden="true" />
            Approuver et générer l'échéancier
          </button>
        </>
      }
    >
      <div className="space-y-4">
        <ModalField
          label="Taux d'intérêt annuel"
          hint="Pré-rempli avec le taux configuré (Paramètres → Frais & taux). Décimal entre 0 et 1 (ex. 0.10 = 10% par an)."
        >
          <input
            type="number"
            inputMode="decimal"
            step="0.0001"
            min="0"
            max="1"
            value={tauxStr}
            onChange={(e) => setTauxStr(e.target.value)}
            className={modalInputClass}
            autoFocus
          />
        </ModalField>
        <ModalField
          label="1re échéance"
          hint="Date à laquelle le 1er remboursement est exigible."
        >
          <input
            type="date"
            value={dateStr}
            onChange={(e) => setDateStr(e.target.value)}
            className={modalInputClass}
          />
        </ModalField>
        {localError ? (
          <p className="rounded-md border border-terra-400/40 bg-terra-50/60 px-3 py-2 text-xs text-terra-700">
            {localError}
          </p>
        ) : null}
      </div>
    </Modal>
  );
}


function RejectLoanModal({
  target,
  onClose,
  onSubmit,
  submitting,
}: {
  target: LoanRequest | null;
  onClose: () => void;
  onSubmit: (motif: string) => void;
  submitting: boolean;
}) {
  const [motif, setMotif] = useState("");

  useEffect(() => {
    if (target) setMotif("");
  }, [target]);

  const open = target !== null;
  const trimmed = motif.trim();
  const canSubmit = !submitting && trimmed.length > 0;

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Rejeter la demande de crédit"
      description={
        target
          ? `Le demandeur recevra le motif par notification.`
          : undefined
      }
      tone="danger"
      footer={
        <>
          <button
            type="button"
            onClick={onClose}
            className={buttonClasses({ variant: "ghost", size: "sm" })}
          >
            Annuler
          </button>
          <button
            type="button"
            onClick={() => canSubmit && onSubmit(trimmed)}
            disabled={!canSubmit}
            className={buttonClasses({ variant: "danger", size: "sm" })}
          >
            <X className="size-3.5" aria-hidden="true" />
            Confirmer le rejet
          </button>
        </>
      }
    >
      <ModalField
        label="Motif du rejet"
        hint="Concis et factuel — sera communiqué au demandeur."
      >
        <textarea
          value={motif}
          onChange={(e) => setMotif(e.target.value)}
          rows={4}
          className={modalInputClass + " resize-y"}
          placeholder="Ex. : taux d'endettement trop élevé compte tenu de l'épargne courante."
          autoFocus
        />
      </ModalField>
    </Modal>
  );
}


/**
 * L4 — Section « Garantie matérielle » affichée sous le motif quand la
 * demande emprunte la voie garantie_materielle. Présente la description du
 * bien, un lien vers le titre de propriété uploadé (attachment
 * `titre_propriete`) et la valeur estimée courante (dès qu'elle est > 0).
 * Purement informatif : la commission approuve toujours via le flux decide.
 */
function GarantieMaterielleSection({ r }: { r: LoanRequest }) {
  if (!r.garantie_materielle) return null;
  const titre = (r.attachments ?? []).find(
    (a) => a.schema_field_id === "titre_propriete",
  );
  const valeur = Number(r.garantie_valeur_estimee ?? "0");
  const valeurEstimee = Number.isFinite(valeur) && valeur > 0;
  const gele = Number(r.montant_gele_demandeur ?? "0");
  return (
    <div className="mt-2 rounded-md border border-blue-700/20 bg-blue-100/30 px-3 py-2">
      <p className="flex items-center gap-1 text-[11px] font-semibold uppercase tracking-wider text-blue-900">
        <Scale className="size-3" aria-hidden="true" />
        Garantie matérielle
      </p>
      {r.garantie_description ? (
        <p className="mt-1 text-xs text-ink-700">{r.garantie_description}</p>
      ) : null}
      <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px]">
        {gele > 0 ? (
          <span className="text-ink-600">
            Montant gelé : <span className="font-medium tabular-nums">{formatXAF(r.montant_gele_demandeur!)}</span>
          </span>
        ) : null}
        {valeurEstimee ? (
          <span className="text-emerald">
            Valeur estimée : <span className="font-medium tabular-nums">{formatXAF(r.garantie_valeur_estimee!)}</span>
          </span>
        ) : (
          <span className="text-ink-500">Bien non encore évalué.</span>
        )}
        {titre?.url ? (
          <DocumentLink
            url={titre.url}
            name={titre.nom_original || "Titre de propriété"}
            subtitle={`Demande #${r.id} · garantie matérielle`}
            label="Titre de propriété"
          />
        ) : (
          <span className="text-amber-700">Titre non uploadé — à demander.</span>
        )}
      </div>
    </div>
  );
}


/**
 * L4 — Modal « Évaluer le bien ». Saisie de la valeur estimée (XAF) + note
 * facultative. POST vers evaluate-guarantee/. Non bloquant : la décision
 * d'octroi reste au flux decide (approbation provisoire / définitive).
 */
function GuaranteeEvalModal({
  target,
  onClose,
  onSubmit,
  submitting,
}: {
  target: LoanRequest | null;
  onClose: () => void;
  onSubmit: (payload: { valeur_estimee: number; note: string }) => void;
  submitting: boolean;
}) {
  const [valeurStr, setValeurStr] = useState("");
  const [note, setNote] = useState("");

  useEffect(() => {
    if (target) {
      // Pré-remplit avec l'évaluation courante si déjà saisie une 1re fois.
      const current = Number(target.garantie_valeur_estimee ?? "0");
      setValeurStr(Number.isFinite(current) && current > 0 ? String(current) : "");
      setNote("");
    }
  }, [target]);

  if (!target) return null;
  const valeur = Number(valeurStr);
  const valeurValid = Number.isFinite(valeur) && valeur > 0;
  const canSubmit = !submitting && valeurValid;

  return (
    <Modal
      open
      onClose={onClose}
      title="Évaluer le bien mis en garantie"
      description={`Demande #${target.id} · ${formatXAF(target.montant_demande)} demandés`}
      tone="info"
      footer={
        <>
          <button
            type="button"
            onClick={onClose}
            disabled={submitting}
            className={buttonClasses({ variant: "ghost", size: "sm" })}
          >
            Annuler
          </button>
          <button
            type="button"
            onClick={() => canSubmit && onSubmit({ valeur_estimee: valeur, note: note.trim() })}
            disabled={!canSubmit}
            className={buttonClasses({ variant: "primary", size: "sm" })}
          >
            <Scale className="size-3.5" aria-hidden="true" />Enregistrer l'évaluation
          </button>
        </>
      }
    >
      <div className="space-y-4">
        {target.garantie_description ? (
          <div className="rounded-md border border-line-200 bg-line-100/40 px-3 py-2 text-xs text-ink-700">
            <span className="font-semibold text-ink-900">Bien décrit : </span>
            {target.garantie_description}
          </div>
        ) : null}
        <ModalField
          label="Valeur estimée du bien"
          hint="Montant en XAF retenu par la commission après examen du titre."
        >
          <input
            type="number"
            inputMode="numeric"
            min="0"
            step="1000"
            value={valeurStr}
            onChange={(e) => setValeurStr(e.target.value)}
            placeholder="Ex. : 2 500 000"
            className={modalInputClass}
            autoFocus
          />
        </ModalField>
        <ModalField label="Note (facultatif)">
          <textarea
            value={note}
            onChange={(e) => setNote(e.target.value)}
            rows={3}
            className={modalInputClass + " resize-y"}
            placeholder="Base de l'estimation, réserves éventuelles…"
          />
        </ModalField>
        <p className="rounded-md border border-blue-700/20 bg-blue-100/40 px-3 py-2 text-xs text-blue-900">
          Cette évaluation est <strong>informative</strong> : elle n'octroie pas le
          crédit. La commission décide via l'approbation (provisoire puis définitive).
        </p>
      </div>
    </Modal>
  );
}


/**
 * Carte compacte « Profil emprunteur » affichée sous le motif de chaque
 * demande de crédit. Présente deux badges (CFP Broad Range + CGA) et,
 * pour chaque réponse positive, une vignette cliquable qui ouvre la
 * pièce uploadée dans un nouvel onglet (image ou PDF).
 *
 * Les libellés "" sont utilisés quand la donnée est absente (cas où le
 * mobile envoyé un build antérieur ou où le seed FormSchema n'a pas été
 * poussé : le compat layer backend met "oui/non" mais le membre peut
 * aussi n'avoir rien rempli).
 */
/** Badge de la voie empruntée + montant que l'avaliste couvre (le cas échéant). */
function VoieBadge({ r }: { r: LoanRequest }) {
  const voie = r.voie ?? "senior_brc";
  const label = r.voie_display ?? "—";
  const tone: Record<string, string> = {
    avaliste: "bg-terra-500/15 text-terra-700",
    campagne: "bg-blue-100 text-blue-800",
    garantie_materielle: "bg-amber-100 text-amber-800",
    senior_brc: "bg-emerald-100 text-emerald-800",
  };
  const couvre = Number(r.avaliste_montant_a_couvrir ?? 0);
  return (
    <div className="min-w-[7rem]">
      <span
        className={`inline-block rounded-full px-2 py-0.5 text-[11px] font-medium ${tone[voie] ?? "bg-ink-100 text-ink-700"}`}
      >
        {label}
      </span>
      {voie === "avaliste" && couvre > 0 ? (
        <p className="mt-1 text-[11px] text-ink-500">
          Avaliste couvre{" "}
          <span className="font-mono font-medium text-ink-700">
            {couvre.toLocaleString("fr-FR")} XAF
          </span>
        </p>
      ) : null}
    </div>
  );
}


/**
 * Badges de profil emprunteur — déclarations du formulaire + pièce jointe
 * correspondante, ouvrable en aperçu (jamais en nouvel onglet).
 *
 * Les deux lignes « Broad Range Consulting » (CGA BRC / CFP BRC) sont
 * DOCUMENTAIRES : la pièce déposée est dupliquée côté backend en `BRCDocument`
 * (consultable ici et dans `/brc`, en lecture). Plus de validation — le comité
 * juge la demande de crédit en s'appuyant dessus.
 */
const PROFIL_ROWS: {
  label: string;
  flagField: string;
  proofField: string;
  brc?: boolean;
}[] = [
  {
    label: "CFP Broad Range",
    flagField: "ancien_apprenant",
    proofField: "ancien_apprenant_preuve",
  },
  { label: "CGA", flagField: "cga_adherent", proofField: "cga_preuve" },
  {
    label: "CGA · BRC",
    flagField: "cga_brc_member",
    proofField: "cga_brc_preuve",
    brc: true,
  },
  {
    label: "CFP · BRC",
    flagField: "cfp_brc_apprenant",
    proofField: "cfp_brc_preuve",
    brc: true,
  },
];

function ProfilEmprunteurBadges({ r }: { r: LoanRequest }) {
  const ep = r.extra_payload ?? {};
  const findAttachment = (fieldId: string) =>
    (r.attachments ?? []).find((a) => a.schema_field_id === fieldId) ?? null;

  const rows = PROFIL_ROWS.map((row) => ({
    ...row,
    value: String(ep[row.flagField] ?? "").toLowerCase(),
    proof: findAttachment(row.proofField),
  })).filter((row) => row.value || row.proof);

  if (rows.length === 0) return null;

  const hasBrc = rows.some((row) => row.brc && (row.value === "oui" || row.proof));

  return (
    <div className="mt-2 space-y-1">
      <div className="flex flex-wrap items-center gap-1.5">
        {rows.map((row) => (
          <ProfilBadge
            key={row.flagField}
            label={row.label}
            value={row.value}
            proof={row.proof}
            isYes={row.value === "oui"}
            subtitle={`Demande #${r.id}${r.member ? ` · ${fullName(r.member.prenom, r.member.nom)}` : ""}`}
          />
        ))}
      </div>
      {hasBrc ? (
        <p className="text-[11px] text-ink-500">
          Pièce BRC à consulter ci-dessus — le comité juge la demande.
        </p>
      ) : null}
    </div>
  );
}

function ProfilBadge({
  label,
  value,
  proof,
  isYes,
  subtitle,
}: {
  label: string;
  value: string;
  proof: { url: string | null; nom_original: string } | null;
  isYes: boolean;
  subtitle?: string;
}) {
  const tone = !value
    ? "border-line-200 bg-paper text-ink-500"
    : isYes
      ? "border-emerald/30 bg-emerald/10 text-emerald"
      : "border-line-200 bg-line-100 text-ink-600";
  const symbol = !value ? "" : isYes ? "✓" : "✗";
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-semibold ${tone}`}
    >
      <span aria-hidden="true">{symbol}</span>
      <span>{label}</span>
      {proof?.url ? (
        <DocumentLink
          url={proof.url}
          name={proof.nom_original || label}
          subtitle={subtitle}
          label="Voir"
          className="ml-1 inline-flex items-center gap-0.5 rounded bg-paper px-1.5 py-px text-[10px] font-medium text-blue-700 hover:underline"
        />
      ) : null}
      {isYes && !proof?.url ? (
        <span
          className="ml-1 rounded bg-amber-100 px-1.5 py-px text-[10px] font-medium text-amber-700"
          title="Pièce non uploadée — à demander au membre"
        >
          pièce ?
        </span>
      ) : null}
    </span>
  );
}
