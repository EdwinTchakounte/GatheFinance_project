"use client";

import { useEffect, useState } from "react";

import { Modal, ModalField, buttonClasses, modalInputClass } from "@/components/modal";
import { adminApi, type ApiError, type Member } from "@/lib/api";
import { fullName } from "@/lib/name";

const MODALITES: Array<{ value: string; label: string }> = [
  { value: "mensuel", label: "Mensuel" },
  { value: "hebdomadaire", label: "Hebdomadaire" },
  { value: "journalier", label: "Journalier" },
];

/**
 * Crédit décidé en séance à l'agence : le comité statue devant le membre,
 * dossier papier en main, sans demande en ligne à instruire.
 *
 * La DURÉE n'est volontairement pas saisissable — elle découle du montant via
 * le barème du règlement (Art. 7). La laisser libre produirait un échéancier
 * incohérent avec le barème appliqué à tous les autres crédits.
 */
export function AgencyLoanModal({
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

  const [montant, setMontant] = useState("");
  const [motif, setMotif] = useState("");
  const [datePremiere, setDatePremiere] = useState("");
  const [modalite, setModalite] = useState("mensuel");
  const [taux, setTaux] = useState("");
  const [gele, setGele] = useState("");
  const [garantie, setGarantie] = useState(false);
  const [garantieDesc, setGarantieDesc] = useState("");
  const [note, setNote] = useState("");

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function reset() {
    setMemberQuery("");
    setMembers([]);
    setSelected(null);
    setMontant("");
    setMotif("");
    setDatePremiere("");
    setModalite("mensuel");
    setTaux("");
    setGele("");
    setGarantie(false);
    setGarantieDesc("");
    setNote("");
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
    if (!selected) return setError("Sélectionne un membre.");
    if (!montant || Number(montant) <= 0) return setError("Montant invalide.");
    if (!motif.trim()) return setError("Le motif est obligatoire (trace de la décision).");
    if (!datePremiere) return setError("Renseigne la date de la première échéance.");

    setSubmitting(true);
    try {
      const loan = await adminApi.loans.createAgencyLoan({
        member_id: selected.id,
        montant: Number(montant),
        motif: motif.trim(),
        date_premiere_echeance: datePremiere,
        modalite_paiement: modalite,
        taux_annuel: taux ? Number(taux) : undefined,
        montant_gele_demandeur: gele ? Number(gele) : undefined,
        garantie_materielle: garantie,
        garantie_description: garantie ? garantieDesc.trim() || undefined : undefined,
        note: note.trim() || undefined,
      });
      onSuccess(
        `Crédit ${loan.numero_dossier} accordé (${Number(loan.montant).toLocaleString("fr-FR")} XAF, ` +
          `${loan.duree_mois} mois). L'argent n'est pas encore versé : procède au décaissement.`,
      );
      onClose();
    } catch (e) {
      setError((e as ApiError).detail ?? "Octroi impossible.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Crédit accordé à l'agence"
      description="Décision de séance, sans demande en ligne. La durée est déduite du montant par le barème du règlement."
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
            onClick={submit}
            disabled={submitting || !selected}
            className={buttonClasses({ variant: "primary", size: "sm" })}
          >
            {submitting ? "Octroi…" : "Accorder le crédit"}
          </button>
        </>
      }
    >
      <div className="space-y-4">
      <ModalField label="Membre">
        {selected ? (
          <div className="flex items-center justify-between rounded-md border border-line-200 bg-line-50/50 px-3 py-2">
            <span className="text-sm text-ink-900">
              {fullName(selected.prenom, selected.nom)}{" "}
              <span className="font-mono text-xs text-ink-500">{selected.numero_membre}</span>
            </span>
            <button
              type="button"
              onClick={() => setSelected(null)}
              className="text-xs font-semibold text-blue-700 hover:underline"
            >
              Changer
            </button>
          </div>
        ) : (
          <>
            <input
              value={memberQuery}
              onChange={(e) => setMemberQuery(e.target.value)}
              placeholder="Nom ou numéro de membre…"
              className={modalInputClass}
            />
            {members.length > 0 ? (
              <ul className="mt-1 max-h-40 overflow-y-auto rounded-md border border-line-200">
                {members.map((m) => (
                  <li key={m.id}>
                    <button
                      type="button"
                      onClick={() => setSelected(m)}
                      className="flex w-full items-center justify-between px-3 py-2 text-left text-sm hover:bg-blue-50"
                    >
                      <span>{fullName(m.prenom, m.nom)}</span>
                      <span className="font-mono text-xs text-ink-500">{m.numero_membre}</span>
                    </button>
                  </li>
                ))}
              </ul>
            ) : null}
          </>
        )}
      </ModalField>

      <ModalField label="Montant (XAF)" hint="La durée de remboursement en découle automatiquement.">
        <input
          type="number"
          min="1"
          value={montant}
          onChange={(e) => setMontant(e.target.value)}
          placeholder="0"
          className={modalInputClass}
        />
      </ModalField>

      <ModalField label="Motif" hint="Objet du crédit — c'est la trace écrite de ce qui a été décidé en séance.">
        <input
          value={motif}
          onChange={(e) => setMotif(e.target.value)}
          placeholder="ex. fonds de roulement boutique"
          className={modalInputClass}
        />
      </ModalField>

      <ModalField label="Première échéance">
        <input
          type="date"
          value={datePremiere}
          onChange={(e) => setDatePremiere(e.target.value)}
          className={modalInputClass}
        />
      </ModalField>

      <ModalField label="Cadence de remboursement">
        <select
          value={modalite}
          onChange={(e) => setModalite(e.target.value)}
          className={modalInputClass}
        >
          {MODALITES.map((m) => (
            <option key={m.value} value={m.value}>
              {m.label}
            </option>
          ))}
        </select>
      </ModalField>

      <ModalField label="Taux (optionnel)" hint="Vide = taux courant du barème. Ex. 0.10 pour 10 %.">
        <input
          type="number"
          step="0.0001"
          min="0"
          max="1"
          value={taux}
          onChange={(e) => setTaux(e.target.value)}
          placeholder="barème"
          className={modalInputClass}
        />
      </ModalField>

      <ModalField
        label="Épargne gelée en garantie (optionnel)"
        hint="Part de l'épargne classique du membre bloquée au retrait jusqu'à clôture du crédit."
      >
        <input
          type="number"
          min="0"
          value={gele}
          onChange={(e) => setGele(e.target.value)}
          placeholder="0"
          className={modalInputClass}
        />
      </ModalField>

      <ModalField label="Garantie matérielle ?">
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={garantie}
            onChange={(e) => setGarantie(e.target.checked)}
            className="size-4"
          />
          Un bien a été présenté en garantie
        </label>
        {garantie ? (
          <input
            value={garantieDesc}
            onChange={(e) => setGarantieDesc(e.target.value)}
            placeholder="Description du bien"
            className={`${modalInputClass} mt-2`}
          />
        ) : null}
      </ModalField>

      <ModalField label="Note interne (optionnel)" hint="ex. numéro du dossier papier, nom du président de séance.">
        <input
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder="ex. dossier papier n°12"
          className={modalInputClass}
        />
      </ModalField>

      <p className="rounded-md border border-amber-200 bg-amber-50/60 px-3 py-2 text-xs text-amber-800">
        Le crédit sera créé <strong>actif mais non décaissé</strong> : l'argent ne
        sort qu'au décaissement, depuis la fiche du crédit.
      </p>

      {error ? (
        <p className="rounded-md border border-rose-200 bg-rose-50/60 p-2.5 text-xs text-rose-700" role="alert">
          {error}
        </p>
      ) : null}
      </div>
    </Modal>
  );
}
