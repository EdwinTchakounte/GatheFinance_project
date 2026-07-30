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
        <span className={`label-num ${onDark ? "label-num--on-dark" : ""}`}>
          {number ? `${number} · ` : null}
          {eyebrow}
        </span>
      ) : null}
      <h2
        className={`mt-5 text-balance font-editorial text-section font-medium ${
          wideLead ? "max-w-4xl" : ""
        } ${onDark ? "text-white" : "text-ink-900"}`}
      >
        {title}
      </h2>
      {lead ? (
        <p
          className={`mt-5 text-lg leading-relaxed ${
            wideLead ? "max-w-none" : "max-w-2xl"
          } ${center ? "mx-auto" : ""} ${onDark ? "text-blue-100/85" : "text-ink-600"}`}
        >
          {lead}
        </p>
      ) : null}
    </Reveal>
  );
}
