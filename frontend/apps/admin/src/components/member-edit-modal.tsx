"use client";

import { useEffect, useState } from "react";
import { buttonClasses } from "@gathe/ui";

import { Modal } from "@/components/modal";
import { adminApi, type ApiError, type Member } from "@/lib/api";

const FIELD =
  "mt-1 w-full rounded-md border border-line-300 bg-white px-3 py-2 text-sm text-ink-900 " +
  "outline-none transition-colors focus:border-blue-400 focus:ring-1 focus:ring-blue-200";
const LABEL = "block text-[0.7rem] font-semibold uppercase tracking-wider text-ink-500";

const PIECES: Array<{ key: string; label: string }> = [
  { key: "cni_recto", label: "CNI — recto" },
  { key: "cni_verso", label: "CNI — verso" },
  { key: "photo", label: "Photo d'identité" },
  { key: "plan", label: "Plan de localisation" },
];

/**
 * Édition d'un membre actif : identité + contact + pièces (remplacement).
 * Seuls les champs modifiés (et les pièces chargées) sont envoyés.
 */
export function MemberEditModal({
  member,
  open,
  onClose,
  onSaved,
}: {
  member: Member | null;
  open: boolean;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [nom, setNom] = useState("");
  const [prenom, setPrenom] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [files, setFiles] = useState<Record<string, File | null>>({});
  const [error, setError] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (open && member) {
      setNom(member.nom ?? "");
      setPrenom(member.prenom ?? "");
      setEmail(member.email ?? "");
      setPhone(member.phone ?? "");
      setFiles({});
      setError(null);
      setOk(null);
    }
  }, [open, member]);

  async function submit() {
    if (!member) return;
    setError(null);
    if (!nom.trim()) {
      setError("Le nom est requis.");
      return;
    }
    setSubmitting(true);
    try {
      const form = new FormData();
      form.append("nom", nom.trim());
      form.append("prenom", prenom.trim());
      form.append("phone", phone.trim());
      form.append("email", email.trim());
      for (const { key } of PIECES) {
        const f = files[key];
        if (f) form.append(key, f);
      }
      await adminApi.members.update(member.id, form);
      setOk("Membre mis à jour.");
      onSaved();
    } catch (err) {
      setError((err as ApiError).detail ?? "Enregistrement impossible.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Éditer le membre"
      description="Corrige l'identité, le contact ou remplace les pièces. Seuls les champs modifiés sont enregistrés."
      footer={
        ok ? (
          <button type="button" className={buttonClasses({ variant: "primary" })} onClick={onClose}>
            Fermer
          </button>
        ) : (
          <>
            <button type="button" className={buttonClasses({ variant: "ghost" })} onClick={onClose}>
              Annuler
            </button>
            <button
              type="button"
              className={buttonClasses({ variant: "primary" })}
              onClick={submit}
              disabled={submitting}
            >
              {submitting ? "Enregistrement…" : "Enregistrer"}
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
              <label className={LABEL} htmlFor="me-nom">Nom *</label>
              <input id="me-nom" className={FIELD} value={nom} onChange={(e) => setNom(e.target.value)} />
            </div>
            <div>
              <label className={LABEL} htmlFor="me-prenom">Prénom</label>
              <input id="me-prenom" className={FIELD} value={prenom} onChange={(e) => setPrenom(e.target.value)} />
            </div>
          </div>
          <div>
            <label className={LABEL} htmlFor="me-email">E-mail</label>
            <input id="me-email" type="email" className={FIELD} value={email} onChange={(e) => setEmail(e.target.value)} />
          </div>
          <div>
            <label className={LABEL} htmlFor="me-phone">Téléphone</label>
            <input id="me-phone" className={FIELD} value={phone} onChange={(e) => setPhone(e.target.value)} />
          </div>

          <div className="pt-1">
            <p className={LABEL}>Pièces (remplacer — facultatif)</p>
            <div className="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-2">
              {PIECES.map(({ key, label }) => (
                <label key={key} className="text-xs text-ink-600">
                  <span className="mb-1 block">{label}</span>
                  <input
                    type="file"
                    accept="image/*,application/pdf"
                    onChange={(e) =>
                      setFiles((prev) => ({ ...prev, [key]: e.target.files?.[0] ?? null }))
                    }
                    className="block w-full text-xs file:mr-2 file:rounded file:border-0 file:bg-line-100 file:px-2 file:py-1"
                  />
                </label>
              ))}
            </div>
          </div>

          {error ? (
            <p className="rounded-md bg-terra-50 px-3 py-2 text-sm text-terra-700">{error}</p>
          ) : null}
        </div>
      )}
    </Modal>
  );
}
