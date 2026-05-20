import type { ReactNode } from "react";

/** Editorial anchor line — small caps prefix with a hairline tail, used to
 *  date or attribute a block of data. Eg.: `<SinceLine>Depuis 2020</SinceLine>`.
 *  Pass `onDark` on navy bands. */
export function SinceLine({ children, onDark = false }: { children: ReactNode; onDark?: boolean }) {
  return (
    <span
      className={`inline-flex items-center gap-3 font-display text-[0.7rem] font-medium uppercase tracking-[0.16em] ${
        onDark ? "text-blue-100/80" : "text-ink-500"
      }`}
    >
      <span
        aria-hidden="true"
        className={`h-px w-9 ${onDark ? "bg-emerald" : "bg-terra-500"}`}
      />
      {children}
    </span>
  );
}
