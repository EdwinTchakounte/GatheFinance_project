"use client";

import { useEffect, useState } from "react";

import { Modal, ModalField, ModalTone, buttonClasses, modalInputClass } from "./modal";

type ConfirmInput = {
  label: string;
  hint?: string;
  placeholder?: string;
  /** Le bouton de confirmation reste désactivé tant que le champ est vide. */
  required?: boolean;
  multiline?: boolean;
  defaultValue?: string;
};

/**
 * Modale de confirmation générique, bien designée — remplace les
 * `window.confirm` / `window.prompt` natifs.
 *
 * - `message` : corps explicatif (texte ou JSX).
 * - `input`   : champ optionnel (motif, référence de reçu…). Sa valeur est
 *               passée à `onConfirm`.
 * - `tone`    : `danger` (rouge) pour les actions destructives/irréversibles.
 *
 * `onConfirm` peut être async : le bouton affiche un état « en cours » et la
 * modale ne se referme qu'une fois l'action résolue (l'appelant ferme via
 * `onClose` dans son `.then`/`finally`, ou on referme automatiquement au succès).
 */
export function ConfirmModal({
  open,
  onClose,
  onConfirm,
  title,
  message,
  confirmLabel = "Confirmer",
  cancelLabel = "Annuler",
  tone = "info",
  input,
}: {
  open: boolean;
  onClose: () => void;
  onConfirm: (value: string) => void | Promise<void>;
  title: string;
  message?: React.ReactNode;
  confirmLabel?: string;
  cancelLabel?: string;
  tone?: ModalTone;
  input?: ConfirmInput;
}) {
  const [value, setValue] = useState(input?.defaultValue ?? "");
  const [submitting, setSubmitting] = useState(false);

  // Réinitialise le champ à chaque ouverture.
  useEffect(() => {
    if (open) setValue(input?.defaultValue ?? "");
  }, [open, input?.defaultValue]);

  const missingInput = Boolean(input?.required) && value.trim().length === 0;
  const disabled = submitting || missingInput;

  const confirmVariant =
    tone === "danger" ? "danger" : tone === "success" ? "success" : "primary";

  async function handleConfirm() {
    if (disabled) return;
    setSubmitting(true);
    try {
      await onConfirm(value.trim());
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Modal
      open={open}
      onClose={submitting ? () => {} : onClose}
      title={title}
      tone={tone}
      footer={
        <>
          <button
            type="button"
            className={buttonClasses({ variant: "ghost", size: "sm" })}
            onClick={onClose}
            disabled={submitting}
          >
            {cancelLabel}
          </button>
          <button
            type="button"
            className={buttonClasses({ variant: confirmVariant, size: "sm" })}
            onClick={handleConfirm}
            disabled={disabled}
          >
            {submitting ? "En cours…" : confirmLabel}
          </button>
        </>
      }
    >
      {message ? (
        <div className="text-sm leading-relaxed text-ink-700">{message}</div>
      ) : null}
      {input ? (
        <div className={message ? "mt-4" : undefined}>
          <ModalField label={input.label} hint={input.hint}>
            {input.multiline ? (
              <textarea
                className={modalInputClass}
                rows={3}
                placeholder={input.placeholder}
                value={value}
                onChange={(e) => setValue(e.target.value)}
              />
            ) : (
              <input
                className={modalInputClass}
                placeholder={input.placeholder}
                value={value}
                onChange={(e) => setValue(e.target.value)}
              />
            )}
          </ModalField>
        </div>
      ) : null}
    </Modal>
  );
}
