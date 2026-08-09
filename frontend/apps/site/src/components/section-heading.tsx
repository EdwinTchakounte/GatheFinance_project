import type { ReactNode } from "react";
import { Reveal } from "@/components/reveal";

/** Institutional section heading.
 *  Small numbered label with a hairline tail (terra on light, emerald on dark),
 *  serif H2 in Lora, optional lead. Used everywhere on the site. */
export function SectionHeading({
  number,
  eyebrow,
  title,
  lead,
  align = "left",
  onDark = false,
  wideLead = false,
  className,
}: {
  number?: string;
  eyebrow?: ReactNode;
  title: ReactNode;
  lead?: ReactNode;
  align?: "left" | "center";
  onDark?: boolean;
  /** Lead qui occupe toute la largeur (2-3 lignes au lieu d'une colonne étroite). */
  wideLead?: boolean;
  className?: string;
}) {
  const center = align === "center";
  const wrapMax = center ? "mx-auto max-w-4xl text-center" : wideLead ? "max-w-none" : "max-w-5xl";
  return (
    <Reveal className={`${wrapMax} ${className ?? ""}`}>
      {eyebrow ? (
        // Eyebrow éditorial : numéro (aligné au bord gauche du titre) + filet
        // court + label tracké. Terra sur clair, vert lumineux sur sombre.
        // Plus de point en tête → le texte reste aligné sur le titre.
        <span
          className={`flex items-center gap-3 font-display text-[0.72rem] font-semibold uppercase tracking-[0.2em] ${
            center ? "justify-center" : ""
          } ${onDark ? "text-green-300" : "text-terra-600"}`}
        >
          {number ? <span className="tabular-nums">{number}</span> : null}
          <span
            aria-hidden="true"
            className={`h-px w-8 ${onDark ? "bg-green-300/50" : "bg-terra-500/50"}`}
          />
          <span>{eyebrow}</span>
        </span>
      ) : null}
      <h2
        className={`mt-6 text-balance font-display text-section font-bold ${
          wideLead ? "max-w-none" : ""
        } ${center ? "mx-auto" : ""} ${onDark ? "text-white" : "text-ink-900"}`}
      >
        {title}
      </h2>
      {lead ? (
        // wideLead : description large (~2 lignes) sous un titre pleine largeur.
        <p
          className={`mt-6 text-lead leading-relaxed text-pretty ${
            wideLead ? "max-w-4xl" : "max-w-2xl"
          } ${center ? "mx-auto" : ""} ${onDark ? "text-white/80" : "text-ink-600"}`}
        >
          {lead}
        </p>
      ) : null}
    </Reveal>
  );
}
