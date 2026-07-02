"use client";

import { useEffect, useRef, useState } from "react";
import { SlidersHorizontal, Check } from "lucide-react";

/**
 * Menu déroulant réutilisable de choix des colonnes visibles d'un tableau.
 * Générique : passe la liste `{ key, label }` + l'ensemble visible + un setter.
 * Réutilisable sur n'importe quel tableau admin (membres d'abord, puis crédits,
 * paiements…).
 */
export type ColumnOption = { key: string; label: string };

export function ColumnsMenu({
  columns,
  visible,
  onToggle,
  lockedKeys = [],
}: {
  columns: ColumnOption[];
  visible: Set<string>;
  onToggle: (key: string) => void;
  /** Colonnes non désactivables (toujours affichées). */
  lockedKeys?: string[];
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function onClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, [open]);

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="inline-flex items-center gap-1.5 rounded-md border border-line-200 bg-paper px-3 py-2 text-xs font-medium text-ink-700 hover:border-blue-700 hover:text-blue-700"
      >
        <SlidersHorizontal className="size-3.5" aria-hidden="true" />
        Colonnes
      </button>
      {open ? (
        <div className="absolute right-0 z-30 mt-1 w-56 rounded-md border border-line-200 bg-paper p-1.5 shadow-lg">
          <p className="px-2 py-1 text-[0.65rem] font-semibold uppercase tracking-wider text-ink-500">
            Colonnes affichées
          </p>
          {columns.map((c) => {
            const locked = lockedKeys.includes(c.key);
            const on = visible.has(c.key);
            return (
              <button
                key={c.key}
                type="button"
                disabled={locked}
                onClick={() => !locked && onToggle(c.key)}
                className={
                  "flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-sm " +
                  (locked
                    ? "cursor-not-allowed text-ink-400"
                    : "text-ink-800 hover:bg-line-100")
                }
              >
                <span
                  className={
                    "flex size-4 items-center justify-center rounded border " +
                    (on ? "border-blue-700 bg-blue-700 text-white" : "border-line-300")
                  }
                >
                  {on ? <Check className="size-3" aria-hidden="true" /> : null}
                </span>
                {c.label}
              </button>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}
