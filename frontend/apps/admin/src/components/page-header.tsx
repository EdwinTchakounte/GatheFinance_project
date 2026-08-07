import type { ReactNode } from "react";

/**
 * En-tête standard des pages du back-office.
 *
 * - eyebrow : sur-titre en petites capitales (section)
 * - title   : titre éditorial
 * - description : accroche courte, occupe TOUTE la largeur et tient sur 1–2
 *   lignes au plus (line-clamp-2) — plus de description bridée qui déborde.
 * - actions : boutons alignés à droite du titre (optionnel)
 */
export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
  className = "",
}: {
  eyebrow?: ReactNode;
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  className?: string;
}) {
  return (
    <header className={`mb-6 ${className}`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          {eyebrow ? (
            <p className="font-display text-[0.7rem] font-semibold uppercase tracking-[0.18em] text-terra-600">
              {eyebrow}
            </p>
          ) : null}
          <h1 className="mt-2 font-editorial text-3xl font-medium tracking-tight text-ink-900">
            {title}
          </h1>
        </div>
        {actions ? (
          <div className="flex shrink-0 items-center gap-2">{actions}</div>
        ) : null}
      </div>
      {description ? (
        <p className="mt-1.5 line-clamp-2 text-sm leading-relaxed text-ink-600">
          {description}
        </p>
      ) : null}
    </header>
  );
}
