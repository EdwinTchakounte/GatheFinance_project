"use client";

import { useEffect, useState } from "react";
import { Check, FileText, Send, X } from "lucide-react";

import { buttonClasses } from "@gathe/ui";

import { Modal, ModalField, modalInputClass } from "@/components/modal";
import { adminApi, type ApiError, type LoanRequest } from "@/lib/api";


function formatXAF(amount: string): string {
  const n = Number(amount);
  if (Number.isNaN(n)) return amount;
  return n.toLocaleString("fr-FR", { maximumFractionDigits: 0 }) + " XAF";
}


function defaultFirstDueDate(): string {
  const d = new Date();
  d.setMonth(d.getMonth() + 1);
  return d.toISOString().slice(0, 10);
}


export default function LoanRequestsPage() {
  return (
    
      <Inner />
    
  );
}

function Inner() {
  const [filter, setFilter] = useState<
    "en_instruction" | "approuvee_provisoire" | "approuvee" | "rejetee" | ""
  >("en_instruction");
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

  return (
    <div className="px-8 py-8 lg:px-12 lg:py-10">
      <header className="mb-8 flex items-end justify-between gap-4">
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

        <div className="flex items-center gap-1 rounded-md border border-line-200 bg-paper p-1">
          {[
            { v: "en_instruction", l: "En instruction" },
            { v: "approuvee_provisoire", l: "Provisoires" },
            { v: "approuvee", l: "Approuvées" },
            { v: "rejetee", l: "Rejetées" },
            { v: "", l: "Toutes" },
          ].map((opt) => (
            <button
              key={opt.v}
              type="button"
              onClick={() =>
                setFilter(
                  opt.v as
                    | "en_instruction"
                    | "approuvee_provisoire"
                    | "approuvee"
                    | "rejetee"
                    | "",
                )
              }
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
        <p className="text-ink-600">Chargement…</p>
      ) : items.length === 0 ? (
        <p className="rounded-md border border-dashed border-line-200 bg-paper/70 p-12 text-center text-sm text-ink-600">
          Aucune demande dans ce filtre.
        </p>
      ) : (
        <div className="overflow-hidden rounded-md border border-line-200 bg-paper">
          <table className="table-admin">
            <thead>
              <tr>
                <th>Demande</th>
                <th className="text-right">Montant</th>
                <th>Durée</th>
                <th>Objet</th>
                <th>Reçue le</th>
                <th>Statut</th>
                <th className="text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {items.map((r) => (
                <tr key={r.id}>
                  <td className="font-mono text-xs text-ink-600">#{r.id}</td>
                  <td className="text-right font-mono font-medium">{formatXAF(r.montant_demande)}</td>
                  <td className="whitespace-nowrap">{r.duree_mois} mois</td>
                  <td className="max-w-md"><p className="line-clamp-3 text-sm">{r.motif}</p></td>
                  <td className="text-sm text-ink-600 whitespace-nowrap">
                    {new Date(r.date_soumission).toLocaleDateString("fr-FR", { day: "2-digit", month: "short", year: "2-digit" })}
                  </td>
                  <td>
                    <span className={
                      "pill " +
                      (r.statut === "en_instruction" ? "pill-info"
                        : r.statut === "approuvee_provisoire" ? "pill-warning"
                        : r.statut === "approuvee" ? "pill-success"
                        : r.statut === "rejetee" ? "pill-danger" : "pill-muted")
                    }>{r.statut_display}</span>
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
                    {r.motif_rejet ? <p className="mt-1 text-xs text-terra-700 max-w-[14rem]">{r.motif_rejet}</p> : null}
                  </td>
                  <td className="text-right">
                    {r.statut === "en_instruction" ? (
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
                      </div>
                    ) : (
                      <div className="flex flex-col items-end gap-1.5">
                        <span className="text-xs text-ink-400">—</span>
                        <a
                          href={adminApi.loans.noteUrl(r.id)}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1 text-[11px] font-medium text-blue-700 hover:underline"
                        >
                          <FileText className="size-3" />Note PDF
                        </a>
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
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
  const [tauxStr, setTauxStr] = useState("0.12");
  const [dateStr, setDateStr] = useState(defaultFirstDueDate());
  const [localError, setLocalError] = useState<string | null>(null);

  useEffect(() => {
    if (target) {
      setTauxStr("0.12");
      setDateStr(defaultFirstDueDate());
      setLocalError(null);
    }
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
                setLocalError("Taux invalide (attendu entre 0 et 1 — ex. 0.12 pour 12%).");
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
          hint="Décimal entre 0 et 1 (ex. 0.12 = 12% par an)."
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
