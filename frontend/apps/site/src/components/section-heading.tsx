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
  className,
}: {
  number?: string;
  eyebrow?: ReactNode;
  title: ReactNode;
  lead?: ReactNode;
  align?: "left" | "center";
  onDark?: boolean;
  className?: string;
}) {
  const center = align === "center";
  return (
    <Reveal className={`${center ? "mx-auto max-w-4xl text-center" : "max-w-5xl"} ${className ?? ""}`}>
      {eyebrow ? (
        <span className={`label-num ${onDark ? "label-num--on-dark" : ""}`}>
          {number ? `${number} · ` : null}
          {eyebrow}
        </span>
      ) : null}
      <h2
        className={`mt-5 text-balance font-editorial text-section font-medium ${
          onDark ? "text-white" : "text-ink-900"
        }`}
      >
        {title}
      </h2>
      {lead ? (
        <p
          className={`mt-5 max-w-2xl text-lg leading-relaxed ${center ? "mx-auto" : ""} ${
            onDark ? "text-blue-100/85" : "text-ink-600"
          }`}
        >
          {lead}
        </p>
      ) : null}
    </Reveal>
  );
}
