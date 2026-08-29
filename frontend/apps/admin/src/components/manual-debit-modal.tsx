"use client";

import { useEffect, useState } from "react";

import { Modal, ModalField, modalInputClass, buttonClasses } from "./modal";
import { adminApi, type ApiError, type Member } from "@/lib/api";
import { fullName } from "@/lib/name";

const FEES: Array<{ code: string; label: string }> = [
  { code: "CARNET", label: "Carnet (renouvellement)" },
  { code: "RECONDUCTION", label: "Reconduction" },
  { code: "INSCRIPTION", label: "Inscription" },
  { code: "ADHESION", label: "Adhésion" },
];

/**
 * Débit manuel agence : retrait direct sur un compte membre, OU prélèvement
 * d'un frais du barème réglé depuis l'épargne classique. Symétrique du cash-in.
 */
export function ManualDebitModal({
  open,
  onClose,
  onSuccess,
}: {
  open: boolean;
  onClose: () => void;
  onSuccess: (msg: string) => void;
}) {
  const [memberQuery, setMemberQuery] = useState("");
  const [members, setMembers] = useState<Member[]>([]);
  const [selected, setSelected] = useState<Member | null>(null);

  const [mode, setMode] = useState<"retrait" | "frais">("retrait");
  const [compte, setCompte] = useState<"collecte" | "classique">("classique");
  const [montant, setMontant] = useState("");
  const [motif, setMotif] = useState("");
  const [feeCode, setFeeCode] = useState("CARNET");
  const [isRenewal, setIsRenewal] = useState(true);

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function reset() {
    setMemberQuery("");
    setMembers([]);
    setSelected(null);
    setMode("retrait");
    setCompte("classique");
    setMontant("");
    setMotif("");
    setFeeCode("CARNET");
    setIsRenewal(true);
    setError(null);
  }

  useEffect(() => {
    if (!open) reset();
  }, [open]);

  useEffect(() => {
    if (!open || selected) return;
    const q = memberQuery.trim();
    if (q.length < 2) {
      setMembers([]);
      return;
    }
    const h = setTimeout(async () => {
      try {
        setMembers((await adminApi.members.list({ q, limit: 8 })).results);
      } catch {
        setMembers([]);
      }
    }, 250);
    return () => clearTimeout(h);
  }, [memberQuery, open, selected]);

  async function submit() {
    setError(null);
    if (!selected) {
      setError("Sélectionne un membre.");
      return;
    }
    if (mode === "retrait" && (!montant || Number(montant) <= 0)) {
      setError("Montant invalide.");
      return;
    }
    setSubmitting(true);
    try {
      const res = await adminApi.payments.manualDebit(
        mode === "frais"
          ? {
              member_id: selected.id,
              fee_code: feeCode,
              is_renewal: feeCode === "CARNET" ? isRenewal : false,
            }
          : {
              member_id: selected.id,
              compte,
              montant: Number(montant),
              motif: motif.trim() || undefined,
            },
      );
      onSuccess(
        `Débit effectué — ${Number(res.montant).toLocaleString("fr-FR")} XAF ` +
          `(solde restant ${Number(res.solde_apres).toLocaleString("fr-FR")} XAF).`,
      );
      onClose();
    } catch (e) {
      setError((e as ApiError).detail ?? "Débit impossible.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Débit / prélèvement agence"
      description="Débit direct immédiat sur un compte membre (symétrique du cash-in), ou prélèvement d'un frais depuis l'épargne classique."
      footer={
        <>
          <button type="button" onClick={onClose} className={buttonClasses({ variant: "ghost", size: "sm" })}>
            Annuler
          </button>
          <button
            type="button"
            onClick={submit}
            disabled={submitting || !selected}
            className={buttonClasses({ variant: "primary", size: "sm" })}
          >
            {submitting ? "Débit…" : "Effectuer le débit"}
          </button>
        </>
      }
    >
      <div className="space-y-4">
        {error ? (
          <p className="rounded-md border border-rose-200 bg-rose-50/60 p-2.5 text-xs text-rose-700">{error}</p>
        ) : null}

        <ModalField label="Membre" hint="Recherche par numéro, nom ou prénom.">
          {selected ? (
            <div className="flex items-center justify-between rounded-md border border-emerald-200 bg-emerald-50/60 px-3 py-2 text-sm">
              <span className="font-medium text-ink-900">{fullName(selected.prenom, selected.nom)}</span>
              <button type="button" onClick={() => setSelected(null)} className="text-xs font-medium text-emerald-700 hover:underline">
                Changer
              </button>
            </div>
          ) : (
            <>
              <input value={memberQuery} onChange={(e) => setMemberQuery(e.target.value)} placeholder="Tape numéro, nom…" className={modalInputClass} />
              {members.length > 0 ? (
                <ul className="mt-2 max-h-44 overflow-y-auto rounded-md border border-line-200">
                  {members.map((m) => (
                    <li key={m.id}>
                      <button type="button" onClick={() => { setSelected(m); setMembers([]); setMemberQuery(""); }} className="block w-full px-3 py-2 text-left text-xs hover:bg-line-100">
                        <span className="font-medium text-ink-900">{fullName(m.prenom, m.nom)}</span>
                        <span className="ml-2 font-mono text-[10px] text-ink-500">{m.numero_membre}</span>
                      </button>
                    </li>
                  ))}
                </ul>
              ) : null}
            </>
          )}
        </ModalField>

        <ModalField label="Opération">
          <div className="flex gap-2">
            {(["retrait", "frais"] as const).map((mo) => (
              <button
                key={mo}
                type="button"
                onClick={() => setMode(mo)}
                className={
                  "flex-1 rounded-md px-3 py-1.5 text-sm font-medium " +
                  (mode === mo ? "bg-blue-700 text-white" : "border border-line-300 text-ink-700")
                }
              >
                {mo === "retrait" ? "Retrait simple" : "Prélever un frais"}
              </button>
            ))}
          </div>
        </ModalField>

        {mode === "retrait" ? (
          <>
            <ModalField label="Compte à débiter">
              <select value={compte} onChange={(e) => setCompte(e.target.value as "collecte" | "classique")} className={modalInputClass}>
                <option value="classique">Épargne classique (part libre)</option>
                <option value="collecte">Collecte journalière</option>
              </select>
            </ModalField>
            <ModalField label="Montant (XAF)">
              <input type="number" min="1" value={montant} onChange={(e) => setMontant(e.target.value)} placeholder="0" className={modalInputClass} />
            </ModalField>
            <ModalField label="Motif">
              <input value={motif} onChange={(e) => setMotif(e.target.value)} placeholder="ex. frais fin d'année, retrait espèces…" className={modalInputClass} />
            </ModalField>
          </>
        ) : (
          <>
            <ModalField label="Frais à prélever" hint="Le montant officiel du barème est prélevé sur l'épargne classique et le frais est réglé (sa logique s'exécute).">
              <select value={feeCode} onChange={(e) => setFeeCode(e.target.value)} className={modalInputClass}>
                {FEES.map((f) => (
                  <option key={f.code} value={f.code}>{f.label}</option>
                ))}
              </select>
            </ModalField>
            {feeCode === "CARNET" ? (
              <ModalField label="Renouvellement annuel ?">
                <label className="flex items-center gap-2 text-sm">
                  <input type="checkbox" checked={isRenewal} onChange={(e) => setIsRenewal(e.target.checked)} className="size-4" />
                  Réinscription annuelle (décale l'anniversaire)
                </label>
              </ModalField>
            ) : null}
          </>
        )}
      </div>
    </Modal>
  );
}
