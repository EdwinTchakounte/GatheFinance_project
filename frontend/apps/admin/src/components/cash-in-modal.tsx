"use client";

import { useEffect, useState } from "react";

import { Modal, ModalField, modalInputClass, buttonClasses } from "./modal";
import {
  adminApi,
  type ApiError,
  type LoanRequest,
  type Member,
} from "@/lib/api";
import { fullName } from "@/lib/name";


type CashInType =
  | "frais_adhesion"
  | "frais_inscription"
  | "frais_carnet"
  | "frais_demande_credit"
  | "epargne"
  | "epargne_classique"
  | "frais_reconduction"
  | "remboursement";


const TYPE_OPTIONS: { value: CashInType; label: string }[] = [
  { value: "frais_adhesion", label: "Frais d'adhésion (10 000)" },
  { value: "frais_inscription", label: "Frais d'inscription (2 000)" },
  { value: "frais_carnet", label: "Frais de carnet (1 000)" },
  { value: "frais_demande_credit", label: "Frais demande de crédit (CH-7)" },
  { value: "epargne", label: "Collecte journalière" },
  { value: "epargne_classique", label: "Épargne classique (libre / placement)" },
  { value: "frais_reconduction", label: "Intérêts de reconduction" },
  { value: "remboursement", label: "Remboursement de crédit" },
];


// Frais FIXES : le montant est arrêté dans le catalogue (FeeType), l'admin ne
// doit PAS pouvoir valider un montant différent. On mappe le type de versement
// vers le code FeeType pour récupérer le tarif officiel et verrouiller le champ.
const FIXED_FEE_CODE: Partial<Record<CashInType, string>> = {
  frais_adhesion: "ADHESION",
  frais_inscription: "INSCRIPTION",
  frais_carnet: "CARNET",
  frais_demande_credit: "DEMANDE_CREDIT",
};


// Optionnel : pre-remplir membre + type + montant a l'ouverture, pour les
// flots ou le contexte est connu (ex: encaisser les frais d'etude d'une
// demande precise depuis la page /loan-requests).
//
// `member` accepte un sous-ensemble (id + nom/prenom + identifiants) car les
// objets renvoyes par les API connexes (LoanRequest, etc.) n'exposent pas
// tous les champs du Member admin (statut, email, ...). On reconstruit un
// Member minimal pour le typeahead UI.
export type CashInPrefillMember = Pick<
  Member,
  "id" | "numero_membre" | "nom" | "prenom"
> & Partial<Member>;

export type CashInPrefill = {
  member?: CashInPrefillMember | null;
  type?: CashInType;
  montant?: string;
  note?: string;
  // Pré-remplit le crédit ciblé (pour un `remboursement` depuis un crédit).
  loanId?: string;
};

export function CashInModal({
  open,
  onClose,
  onSuccess,
  prefill,
}: {
  open: boolean;
  onClose: () => void;
  onSuccess: (msg: string) => void;
  prefill?: CashInPrefill;
}) {
  const [memberQuery, setMemberQuery] = useState("");
  const [members, setMembers] = useState<Member[]>([]);
  const [memberLoading, setMemberLoading] = useState(false);
  const [selectedMember, setSelectedMember] = useState<Member | null>(null);

  const [paymentType, setPaymentType] = useState<CashInType>("frais_adhesion");
  const [montant, setMontant] = useState("");
  const [reference, setReference] = useState("");
  const [note, setNote] = useState("");

  // Champs specifiques.
  const [loanId, setLoanId] = useState("");
  const [nbJours, setNbJours] = useState("1");
  const [isPlacement, setIsPlacement] = useState(false);
  // D6 . Flag renouvellement annuel pour frais_carnet.
  const [isRenewal, setIsRenewal] = useState(false);

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Sélection du « crédit demandé » : UNIQUEMENT pour les frais d'étude de
  // dossier (le remboursement, lui, cible le crédit via son propre champ
  // `loanId`). Le carnet est un frais FIXE indépendant de tout crédit — il ne
  // doit ni chercher une demande en attente ni afficher « pas de demande de
  // crédit » (bug signalé sur l'achat de carnet).
  const [pendingRequests, setPendingRequests] = useState<LoanRequest[]>([]);
  const [pendingLoading, setPendingLoading] = useState(false);
  const isCreditFee = paymentType === "frais_demande_credit";
  // Anti double-facturation : si on est sur « frais de demande de crédit » et
  // que la demande en attente a déjà ses frais d'étude réglés (cas campagne :
  // seul le carnet reste dû), on bloque la saisie — sinon on re-facturerait.
  const studyFeeAlreadyPaid =
    paymentType === "frais_demande_credit" &&
    pendingRequests.length > 0 &&
    pendingRequests.every((r) => r.frais_demande_credit_paye);

  // Tarifs officiels des frais fixes (FeeType) → verrouillage du montant.
  const [feeAmounts, setFeeAmounts] = useState<Record<string, number>>({});
  const fixedFeeCode = FIXED_FEE_CODE[paymentType];
  const officialAmount =
    fixedFeeCode != null ? feeAmounts[fixedFeeCode] : undefined;
  const montantLocked = officialAmount != null && officialAmount > 0;

  function reset() {
    setMemberQuery("");
    setMembers([]);
    setSelectedMember(null);
    setPaymentType("frais_adhesion");
    setMontant("");
    setReference("");
    setNote("");
    setLoanId("");
    setNbJours("1");
    setIsPlacement(false);
    setIsRenewal(false);
    setPendingRequests([]);
    setError(null);
  }

  // Charge les tarifs officiels des frais fixes à l'ouverture.
  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    (async () => {
      try {
        const cfg = await adminApi.costs.config();
        if (cancelled) return;
        const map: Record<string, number> = {};
        for (const fee of cfg.fees) {
          if (fee.actif) map[fee.code] = Number(fee.montant);
        }
        setFeeAmounts(map);
      } catch {
        // Pas bloquant : sans tarif, le champ reste éditable (fallback backend).
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [open]);

  // Verrouille le montant au tarif officiel dès qu'un frais fixe est
  // sélectionné (et que son tarif est connu). Empêche toute validation avec un
  // montant différent — barrière serveur en plus dans admin_cash_in_payment.
  useEffect(() => {
    if (montantLocked && officialAmount != null) {
      setMontant(String(officialAmount));
    }
  }, [montantLocked, officialAmount, paymentType]);

  useEffect(() => {
    if (!open) {
      reset();
      return;
    }
    // Applique le prefill quand le modal s'ouvre. Le membre selectionne court-
    // circuite la recherche typeahead. L'admin peut toujours editer.
    if (prefill?.member) {
      // Le typeahead `selectedMember` exige un Member complet : on comble
      // les champs absents avec des defauts safe. L'admin peut quand meme
      // dechecker pour resaisir si besoin.
      const m: Member = {
        id: prefill.member.id,
        numero_membre: prefill.member.numero_membre,
        nom: prefill.member.nom,
        prenom: prefill.member.prenom,
        email: prefill.member.email ?? "",
        phone: prefill.member.phone ?? "",
        statut: prefill.member.statut ?? "actif",
        statut_display: prefill.member.statut_display ?? "",
        date_adhesion: prefill.member.date_adhesion ?? "",
      };
      setSelectedMember(m);
    }
    if (prefill?.type) setPaymentType(prefill.type);
    if (prefill?.montant) setMontant(prefill.montant);
    if (prefill?.note) setNote(prefill.note);
    if (prefill?.loanId) setLoanId(prefill.loanId);
  }, [open, prefill]);

  // Recherche membre . debounce simple 250ms.
  useEffect(() => {
    if (!open || selectedMember) return;
    const q = memberQuery.trim();
    if (q.length < 2) {
      setMembers([]);
      return;
    }
    const handle = setTimeout(async () => {
      setMemberLoading(true);
      try {
        const res = await adminApi.members.list({ q, limit: 10 });
        setMembers(res.results);
      } catch {
        setMembers([]);
      } finally {
        setMemberLoading(false);
      }
    }, 250);
    return () => clearTimeout(handle);
  }, [memberQuery, open, selectedMember]);

  // Frais de crédit : charge la (les) demande(s) en attente du membre pour
  // afficher/confirmer le « crédit demandé » à la sélection.
  useEffect(() => {
    if (!open || !selectedMember || !isCreditFee) {
      setPendingRequests([]);
      return;
    }
    let cancelled = false;
    setPendingLoading(true);
    adminApi.loanRequests
      .list("en_attente", { member: selectedMember.id })
      .then((rows) => {
        if (cancelled) return;
        setPendingRequests(rows);
        // Montant autoritaire : frais d'étude propres à la demande (campagne
        // incluse) ; carnet = tarif fixe déjà géré par montantLocked.
        if (
          paymentType === "frais_demande_credit" &&
          rows[0]?.frais_etude_montant
        ) {
          setMontant(String(rows[0].frais_etude_montant));
        }
      })
      .catch(() => {
        if (!cancelled) setPendingRequests([]);
      })
      .finally(() => {
        if (!cancelled) setPendingLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [open, selectedMember, isCreditFee, paymentType]);

  async function handleSubmit() {
    setError(null);
    if (!selectedMember) {
      setError("Sélectionne un membre.");
      return;
    }
    if (isCreditFee && pendingRequests.length === 0) {
      setError(
        "Ce membre n'a pas de demande de crédit en attente de paiement.",
      );
      return;
    }
    const montantNum = Number(montant);
    if (!Number.isFinite(montantNum) || montantNum <= 0) {
      setError("Montant invalide.");
      return;
    }
    if (paymentType === "remboursement" && !loanId.trim()) {
      setError("Numéro de crédit requis pour un remboursement.");
      return;
    }

    const payload: Parameters<typeof adminApi.payments.cashIn>[0] = {
      member_id: selectedMember.id,
      type: paymentType,
      montant: montantNum,
      reference_externe: reference.trim() || undefined,
      note: note.trim() || undefined,
    };
    if (paymentType === "remboursement") {
      payload.loan_id = Number(loanId);
    }
    if (paymentType === "epargne") {
      payload.nb_jours_couverts = Number(nbJours) || 1;
    }
    if (paymentType === "epargne_classique") {
      payload.is_placement = isPlacement;
    }
    if (paymentType === "frais_carnet" && isRenewal) {
      payload.is_renewal = true;
    }

    setSubmitting(true);
    try {
      const res = await adminApi.payments.cashIn(payload);
      onSuccess(
        `Versement #${res.id} enregistré (${Number(res.montant).toLocaleString("fr-FR")} XAF).`,
      );
      onClose();
    } catch (e) {
      const apiErr = e as ApiError;
      setError(apiErr.detail ?? "Saisie impossible.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Saisir un versement agence"
      description="Crée un paiement source=MANUEL, statut=VALIDÉ immédiatement et déclenche le hook business correspondant. Action tracée dans l'audit."
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
            onClick={handleSubmit}
            disabled={
              submitting || !selectedMember || !montant || studyFeeAlreadyPaid
            }
            className={buttonClasses({ variant: "primary", size: "sm" })}
          >
            {submitting ? "Enregistrement…" : "Enregistrer le versement"}
          </button>
        </>
      }
    >
      <div className="space-y-4">
        {error ? (
          <p className="rounded-md border border-rose-200 bg-rose-50/60 p-2.5 text-xs text-rose-700">
            {error}
          </p>
        ) : null}

        {/* Membre */}
        <ModalField
          label="Membre"
          hint="Recherche par numéro, nom ou prénom (≥ 2 caractères)."
        >
          {selectedMember ? (
            <div className="flex items-center justify-between rounded-md border border-emerald-200 bg-emerald-50/60 px-3 py-2 text-sm">
              <div>
                <p className="font-medium text-ink-900">
                  {fullName(selectedMember.prenom, selectedMember.nom)}
                </p>
                <p className="font-mono text-[10px] text-ink-500">
                  {selectedMember.numero_membre} · {selectedMember.statut}
                </p>
              </div>
              <button
                type="button"
                onClick={() => setSelectedMember(null)}
                className="text-xs font-medium text-emerald-700 hover:underline"
              >
                Changer
              </button>
            </div>
          ) : (
            <>
              <input
                type="search"
                value={memberQuery}
                onChange={(e) => setMemberQuery(e.target.value)}
                placeholder="Tape numéro, nom…"
                className={modalInputClass}
              />
              {memberLoading ? (
                <p className="mt-1 text-[11px] text-ink-500">Recherche…</p>
              ) : null}
              {members.length > 0 ? (
                <ul className="mt-2 max-h-48 overflow-y-auto rounded-md border border-line-200">
                  {members.map((m) => (
                    <li key={m.id}>
                      <button
                        type="button"
                        onClick={() => {
                          setSelectedMember(m);
                          setMembers([]);
                          setMemberQuery("");
                        }}
                        className="block w-full px-3 py-2 text-left text-xs hover:bg-line-100"
                      >
                        <span className="font-medium text-ink-900">
                          {fullName(m.prenom, m.nom)}
                        </span>
                        <span className="ml-2 font-mono text-[10px] text-ink-500">
                          {m.numero_membre} · {m.statut}
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
              ) : null}
            </>
          )}
        </ModalField>

        {/* Type */}
        <ModalField label="Type de versement">
          <select
            value={paymentType}
            onChange={(e) => setPaymentType(e.target.value as CashInType)}
            className={modalInputClass}
          >
            {TYPE_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </ModalField>

        {/* Crédit demandé (frais de crédit) — sélection/confirmation. */}
        {isCreditFee && selectedMember ? (
          <ModalField
            label="Crédit demandé"
            hint="Frais rattachés à la demande de crédit en attente de ce membre."
          >
            {pendingLoading ? (
              <p className="text-[11px] text-ink-500">Recherche du crédit…</p>
            ) : pendingRequests.length === 0 ? (
              <p className="rounded-md border border-amber-200 bg-amber-50/60 px-3 py-2 text-xs text-amber-700">
                Aucune demande de crédit en attente pour ce membre.
              </p>
            ) : (
              <ul className="space-y-2">
                {pendingRequests.map((r) => (
                  <li
                    key={r.id}
                    className="rounded-md border border-blue-200 bg-blue-50/40 px-3 py-2 text-xs"
                  >
                    <p className="font-medium text-ink-900">
                      Demande #{r.id} ·{" "}
                      {Number(r.montant_demande).toLocaleString("fr-FR")} XAF
                    </p>
                    <p className="mt-0.5 text-ink-600">
                      Frais d'étude :{" "}
                      <span
                        className={
                          r.frais_demande_credit_paye
                            ? "text-emerald-700"
                            : "font-medium text-ink-900"
                        }
                      >
                        {r.frais_demande_credit_paye
                          ? "réglés"
                          : `${Number(r.frais_etude_montant ?? 0).toLocaleString("fr-FR")} XAF dus`}
                      </span>
                      {Number(r.carnet_fee_due ?? 0) > 0 ? (
                        <>
                          {" · "}Carnet :{" "}
                          <span className="font-medium text-amber-700">
                            {Number(r.carnet_fee_due).toLocaleString("fr-FR")} XAF dus
                          </span>
                        </>
                      ) : null}
                    </p>
                  </li>
                ))}
                {Number(pendingRequests[0]?.carnet_fee_due ?? 0) > 0 ? (
                  <p className="text-[11px] text-ink-500">
                    Bénéficiaire campagne : encaisse l'étude ET le carnet (2
                    versements distincts) pour ouvrir l'instruction.
                  </p>
                ) : null}
                {studyFeeAlreadyPaid ? (
                  <p className="rounded-md border border-emerald-200 bg-emerald-50/60 px-3 py-2 text-[11px] text-emerald-700">
                    Frais d'étude déjà réglés pour cette demande.
                    {Number(pendingRequests[0]?.carnet_fee_due ?? 0) > 0
                      ? " Il reste le carnet à encaisser → choisis le type « frais de carnet »."
                      : " Aucun frais d'étude supplémentaire n'est dû."}
                  </p>
                ) : !studyFeeAlreadyPaid && pendingRequests[0] ? (
                  <p className="rounded-md border border-blue-200 bg-blue-50/60 px-3 py-2 text-[11px] text-blue-800">
                    Ce versement sera{" "}
                    <strong>rattaché à la demande de crédit #
                    {pendingRequests[0].id}</strong>{" "}
                    de {fullName(selectedMember.prenom, selectedMember.nom)} et fera
                    avancer son instruction. Il n'impacte aucun autre compte.
                  </p>
                ) : null}
              </ul>
            )}
          </ModalField>
        ) : null}

        {/* Montant */}
        <ModalField
          label="Montant (XAF)"
          hint={
            montantLocked
              ? "Montant fixe pour ce type de frais — non modifiable."
              : undefined
          }
        >
          <input
            type="number"
            min="1"
            step="100"
            value={montant}
            onChange={(e) => setMontant(e.target.value)}
            placeholder="0"
            readOnly={montantLocked}
            aria-readonly={montantLocked}
            className={
              montantLocked
                ? `${modalInputClass} cursor-not-allowed bg-line-100 text-ink-500`
                : modalInputClass
            }
          />
        </ModalField>

        {/* Specifiques par type */}
        {paymentType === "remboursement" ? (
          <ModalField
            label="ID du crédit"
            hint="Numéro interne (visible dans la liste des crédits)."
          >
            <input
              type="number"
              value={loanId}
              onChange={(e) => setLoanId(e.target.value)}
              placeholder="ex. 42"
              className={modalInputClass}
            />
          </ModalField>
        ) : null}

        {paymentType === "epargne" ? (
          <ModalField
            label="Nombre de jours couverts"
            hint="1 = paiement standard. > 1 = multi-jours pré-payé."
          >
            <input
              type="number"
              min="1"
              value={nbJours}
              onChange={(e) => setNbJours(e.target.value)}
              className={modalInputClass}
            />
          </ModalField>
        ) : null}

        {paymentType === "epargne_classique" ? (
          <ModalField
            label="Sous-canal"
            hint="Placement = pool prêteur (intérêts uniquement si engagé)."
          >
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={isPlacement}
                onChange={(e) => setIsPlacement(e.target.checked)}
                className="size-4"
              />
              Placement (sinon : épargne classique libre)
            </label>
          </ModalField>
        ) : null}

        {paymentType === "frais_carnet" ? (
          <ModalField
            label="Renouvellement annuel ?"
            hint="Coche si c'est le carnet annuel de re-souscription (n'imprime pas de nouveau carnet, met juste à jour la date d'anniversaire)."
          >
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={isRenewal}
                onChange={(e) => setIsRenewal(e.target.checked)}
                className="size-4"
              />
              Renouvellement annuel d'adhésion
            </label>
          </ModalField>
        ) : null}

        {/* Reference + note */}
        <ModalField
          label="Référence (n° bordereau)"
          hint="Recommandé pour la traçabilité comptable."
        >
          <input
            type="text"
            value={reference}
            onChange={(e) => setReference(e.target.value)}
            placeholder="ex. BRD-2026-00123"
            className={modalInputClass}
          />
        </ModalField>

        <ModalField label="Note (interne)">
          <textarea
            value={note}
            onChange={(e) => setNote(e.target.value)}
            rows={2}
            placeholder="Contexte, remarques…"
            className={modalInputClass}
          />
        </ModalField>
      </div>
    </Modal>
  );
}
