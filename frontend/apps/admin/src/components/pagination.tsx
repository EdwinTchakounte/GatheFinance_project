"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";


type Props = {
  count: number;
  limit: number;
  offset: number;
  onChange: (offset: number) => void;
  pageSizeOptions?: number[];
  onLimitChange?: (limit: number) => void;
};


/**
 * Pagination offset/limit reutilisable pour les listes admin paginees.
 *
 * Affiche : "X-Y sur Z" + boutons Precedent/Suivant + selecteur de taille.
 * Boutons desactives quand on est en bord. Cache tout si count <= limit.
 */
export function Pagination({
  count,
  limit,
  offset,
  onChange,
  pageSizeOptions = [25, 50, 100],
  onLimitChange,
}: Props) {
  if (count === 0) return null;

  const start = count === 0 ? 0 : offset + 1;
  const end = Math.min(offset + limit, count);
  const canPrev = offset > 0;
  const canNext = end < count;

  return (
    <div className="mt-5 flex flex-wrap items-center justify-between gap-3 border-t border-line-200 pt-4 text-xs text-ink-600">
      <p>
        <span className="font-mono text-ink-900 font-medium">
          {start}–{end}
        </span>{" "}
        sur <span className="font-mono text-ink-900 font-medium">{count}</span>
      </p>

      <div className="flex items-center gap-2">
        {onLimitChange ? (
          <label className="flex items-center gap-1.5">
            <span className="text-ink-500">Par page</span>
            <select
              value={limit}
              onChange={(e) => onLimitChange(Number(e.target.value))}
              className="rounded-md border border-line-200 bg-paper px-2 py-1 font-mono text-xs text-ink-900 focus:border-blue-700 focus:outline-none focus:ring-1 focus:ring-blue-700"
            >
              {pageSizeOptions.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </label>
        ) : null}

        <button
          type="button"
          disabled={!canPrev}
          onClick={() => onChange(Math.max(0, offset - limit))}
          className="inline-flex items-center gap-1 rounded-md border border-line-200 bg-paper px-2.5 py-1.5 font-medium text-ink-700 transition-colors hover:border-blue-700 hover:text-blue-700 disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:border-line-200 disabled:hover:text-ink-700"
        >
          <ChevronLeft className="size-3.5" aria-hidden="true" />
          Précédent
        </button>
        <button
          type="button"
          disabled={!canNext}
          onClick={() => onChange(offset + limit)}
          className="inline-flex items-center gap-1 rounded-md border border-line-200 bg-paper px-2.5 py-1.5 font-medium text-ink-700 transition-colors hover:border-blue-700 hover:text-blue-700 disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:border-line-200 disabled:hover:text-ink-700"
        >
          Suivant
          <ChevronRight className="size-3.5" aria-hidden="true" />
        </button>
      </div>
    </div>
  );
}
