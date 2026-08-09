"use client";

import { useState } from "react";
import { ChevronDown } from "lucide-react";

/**
 * Liste des objectifs de la coopérative (section « Notre raison d'être »).
 * Repliée aux 3 premiers items par défaut, avec un « Voir plus » qui déplie le
 * reste — pour garder la colonne de texte à une hauteur proche de la photo.
 * Client component (état d'ouverture) isolé du reste de la section (serveur).
 */
export function AboutObjectives({
  items,
  moreLabel,
  lessLabel,
  collapsedCount = 3,
}: {
  items: string[];
  moreLabel: string;
  lessLabel: string;
  collapsedCount?: number;
}) {
  const [open, setOpen] = useState(false);
  const needsToggle = items.length > collapsedCount;
  const shown = open || !needsToggle ? items : items.slice(0, collapsedCount);

  return (
    <div className="mt-8">
      <ul className="space-y-4 border-l border-line-200 pl-7">
        {shown.map((item, i) => (
          <li key={i} className="relative">
            <span
              aria-hidden="true"
              className="absolute -left-[31px] top-2 size-1.5 rounded-full bg-emerald"
            />
            <p className="text-[0.98rem] leading-relaxed text-ink-700">{item}</p>
          </li>
        ))}
      </ul>

      {needsToggle ? (
        <button
          type="button"
          onClick={() => setOpen((o) => !o)}
          aria-expanded={open}
          className="mt-6 inline-flex items-center gap-1.5 text-sm font-semibold text-blue-700 transition-colors hover:text-blue-800"
        >
          {open ? lessLabel : moreLabel}
          <ChevronDown
            aria-hidden="true"
            className={`size-4 transition-transform duration-300 ${open ? "rotate-180" : ""}`}
          />
        </button>
      ) : null}
    </div>
  );
}
