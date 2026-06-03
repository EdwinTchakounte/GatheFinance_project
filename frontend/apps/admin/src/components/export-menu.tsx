"use client";

import { useEffect, useRef, useState } from "react";
import { Download, FileSpreadsheet, Printer, ChevronDown } from "lucide-react";

import {
  exportCSV,
  printPDF,
  type ExportColumn,
} from "@/lib/export";


/**
 * Bouton "Exporter" déroulant — CSV + PDF (via print).
 *
 * Réutilisable sur n'importe quelle liste : on passe la liste, les colonnes
 * (label + value selector) et un préfixe de nom de fichier. Le composant
 * gère son propre dropdown.
 */
export function ExportMenu<T>({
  filenamePrefix,
  title,
  subtitle,
  columns,
  rows,
  disabled,
}: {
  filenamePrefix: string;
  title: string;
  subtitle?: string;
  columns: ExportColumn<T>[];
  rows: T[];
  disabled?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const wrapperRef = useRef<HTMLDivElement>(null);

  // Fermer au clic extérieur
  useEffect(() => {
    if (!open) return;
    function onClick(e: MouseEvent) {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, [open]);

  const dateSuffix = new Date().toISOString().slice(0, 10);

  return (
    <div ref={wrapperRef} className="relative inline-block">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        disabled={disabled || rows.length === 0}
        className="inline-flex items-center gap-1.5 rounded-md border border-line-200 bg-paper px-3 py-1.5 text-sm font-medium text-ink-700 transition hover:bg-cream disabled:cursor-not-allowed disabled:opacity-50"
      >
        <Download className="h-4 w-4" />
        Exporter {rows.length > 0 ? `(${rows.length})` : ""}
        <ChevronDown
          className={`h-3.5 w-3.5 transition-transform ${open ? "rotate-180" : ""}`}
        />
      </button>
      {open && (
        <div className="absolute right-0 z-40 mt-1.5 min-w-[200px] overflow-hidden rounded-md border border-line-200 bg-paper shadow-lg">
          <button
            type="button"
            onClick={() => {
              exportCSV({
                filename: `${filenamePrefix}-${dateSuffix}`,
                columns,
                rows,
              });
              setOpen(false);
            }}
            className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-ink-700 transition hover:bg-cream"
          >
            <FileSpreadsheet className="h-4 w-4 text-emerald" />
            <div>
              <p className="font-medium">CSV (Excel)</p>
              <p className="text-[10px] text-ink-500">Séparateur « ; », UTF-8 BOM</p>
            </div>
          </button>
          <button
            type="button"
            onClick={() => {
              printPDF({ title, subtitle, columns, rows });
              setOpen(false);
            }}
            className="flex w-full items-center gap-2 border-t border-line-200 px-3 py-2 text-left text-sm text-ink-700 transition hover:bg-cream"
          >
            <Printer className="h-4 w-4 text-blue-700" />
            <div>
              <p className="font-medium">PDF (imprimer)</p>
              <p className="text-[10px] text-ink-500">
                Dialogue d&apos;impression → enregistrer en PDF
              </p>
            </div>
          </button>
        </div>
      )}
    </div>
  );
}
