"use client";

import { useEffect, useRef } from "react";
import { X } from "lucide-react";

import { buttonClasses } from "@gathe/ui";


export type ModalTone = "info" | "success" | "danger";


export function Modal({
  open,
  onClose,
  title,
  description,
  tone = "info",
  children,
  footer,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  tone?: ModalTone;
  children?: React.ReactNode;
  footer?: React.ReactNode;
}) {
  const dialogRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function handleKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", handleKey);
    // Lock body scroll while the modal is open.
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    // Focus the dialog so screen readers and keyboard pick it up.
    dialogRef.current?.focus();
    return () => {
      document.removeEventListener("keydown", handleKey);
      document.body.style.overflow = prevOverflow;
    };
  }, [open, onClose]);

  if (!open) return null;

  const accent =
    tone === "danger"
      ? "border-l-4 border-l-[#ba2121]"
      : tone === "success"
        ? "border-l-4 border-l-emerald"
        : "border-l-4 border-l-blue-700";

  return (
    <div
      role="presentation"
      onClick={onClose}
      className="fixed inset-0 z-50 flex items-center justify-center bg-ink-900/50 px-4 py-8 backdrop-blur-sm"
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="modal-title"
        tabIndex={-1}
        onClick={(e) => e.stopPropagation()}
        className={
          "flex max-h-[90vh] w-full max-w-lg flex-col overflow-hidden rounded-md bg-paper shadow-xl outline-none " +
          accent
        }
      >
        <header className="flex shrink-0 items-start justify-between gap-4 px-6 pt-5 pb-3">
          <div>
            <h2
              id="modal-title"
              className="font-editorial text-xl font-medium text-ink-900"
            >
              {title}
            </h2>
            {description ? (
              <p className="mt-1 text-sm text-ink-600">{description}</p>
            ) : null}
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Fermer"
            className="rounded p-1 text-ink-500 hover:bg-line-100 hover:text-ink-900"
          >
            <X className="size-4" aria-hidden="true" />
          </button>
        </header>

        {children ? <div className="px-6 py-4">{children}</div> : null}

        {footer ? (
          <footer className="flex items-center justify-end gap-2 border-t border-line-200 bg-line-100/30 px-6 py-3">
            {footer}
          </footer>
        ) : null}
      </div>
    </div>
  );
}


export function ModalField({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className="block text-xs font-semibold uppercase tracking-wider text-ink-700">
        {label}
      </span>
      {hint ? <span className="mt-0.5 block text-xs text-ink-500">{hint}</span> : null}
      <div className="mt-1.5">{children}</div>
    </label>
  );
}


export const modalInputClass =
  "w-full rounded-md border border-line-200 bg-paper px-3 py-2 text-sm placeholder:text-ink-400 focus:border-blue-700 focus:outline-none focus:ring-1 focus:ring-blue-700";

export { buttonClasses };
