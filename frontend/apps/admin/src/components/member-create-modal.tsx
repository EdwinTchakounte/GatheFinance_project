"use client";

import { useState } from "react";
import { buttonClasses } from "@gathe/ui";

import { Modal } from "@/components/modal";
import { adminApi, type ApiError } from "@/lib/api";

const FIELD =
  "mt-1 w-full rounded-md border border-line-300 bg-white px-3 py-2 text-sm text-ink-900 " +
  "outline-none transition-colors focus:border-blue-400 focus:ring-1 focus:ring-blue-200";
const LABEL = "block text-[0.7rem] font-semibold uppercase tracking-wider text-ink-500";

/**
 * M1 — Ajouter un membre depuis le dashboard.
 * Crée le compte (statut suspendu) ; le membre reçoit un mail de définition de
 * mot de passe et chargera SES pièces (CNI, photo, plan) à ce moment-là.
 */
export function MemberCreateModal({
  open,
  onClose,
  onCreated,
}: {
  open: boolean;
  onClose: () => void;
  onCreated: () => void;
}) {
  const [nom, setNom] = useState("");
  const [prenom, setPrenom] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  function reset() {
    setNom("");
    setPrenom("");
    setEmail("");
    setPhone("");
    setError(null);
    setOk(null);
  }

  async function submit() {
    setError(null);
    if (!nom.trim() || !email.trim()) {
      setError("Le nom et l'e-mail sont requis.");
      return;
    }
    setSubmitting(true);
    try {
      const m = await adminApi.members.create({
        nom: nom.trim(),
        prenom: prenom.trim() || undefined,
        email: email.trim(),
        phone: phone.trim() || undefined,
      });
      setOk(
        `Membre ${m.numero_membre} créé. Un e-mail de définition de mot de passe ` +
          `lui a été envoyé — il chargera ses pièces (CNI, photo, plan) à ce moment.`,
      );
      onCreated();
    } catch (err) {
      const apiErr = err as ApiError;
      setError(apiErr.detail ?? "Création impossible.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Modal
      open={open}
      onClose={() => {
        reset();
        onClose();
      }}
      title="Ajouter un membre"
      description="Le membre reçoit un e-mail pour définir son mot de passe et charger ses pièces (CNI, photo, plan)."
      footer={
        ok ? (
          <button
            type="button"
            className={buttonClasses({ variant: "primary" })}
            onClick={() => {
              reset();
              onClose();
            }}
          >
            Fermer
          </button>
        ) : (
          <>
            <button
              type="button"
              className={buttonClasses({ variant: "ghost" })}
              onClick={() => {
                reset();
                onClose();
              }}
            >
              Annuler
            </button>
            <button
              type="button"
              className={buttonClasses({ variant: "primary" })}
              onClick={submit}
              disabled={submitting}
            >
              {submitting ? "Création…" : "Créer le membre"}
            </button>
          </>
        )
      }
    >
      {ok ? (
        <p className="rounded-md bg-emerald-50 px-3 py-2 text-sm text-emerald-800">{ok}</p>
      ) : (
        <div className="space-y-3">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div>
              <label className={LABEL} htmlFor="mc-nom">Nom *</label>
              <input id="mc-nom" className={FIELD} value={nom} onChange={(e) => setNom(e.target.value)} />
            </div>
            <div>
              <label className={LABEL} htmlFor="mc-prenom">Prénom</label>
              <input id="mc-prenom" className={FIELD} value={prenom} onChange={(e) => setPrenom(e.target.value)} />
            </div>
          </div>
          <div>
            <label className={LABEL} htmlFor="mc-email">E-mail *</label>
            <input id="mc-email" type="email" className={FIELD} value={email} onChange={(e) => setEmail(e.target.value)} />
          </div>
          <div>
            <label className={LABEL} htmlFor="mc-phone">Téléphone</label>
            <input id="mc-phone" className={FIELD} value={phone} onChange={(e) => setPhone(e.target.value)} />
          </div>
          {error ? (
            <p className="rounded-md bg-terra-50 px-3 py-2 text-sm text-terra-700">{error}</p>
          ) : null}
        </div>
      )}
    </Modal>
  );
}
