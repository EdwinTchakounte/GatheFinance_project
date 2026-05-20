import { cn } from "@gathe/ui";

/**
 * Curve divider — a full-bleed band that creates a soft curved transition
 * between two adjacent sections.
 *
 * Inspired by modern corporate banking sites (cca-bank.com, etc.): instead
 * of a sharp horizontal line between two background colours, the boundary
 * is a single smooth curve. The lower surface (`to`) "rises" gently into
 * the upper surface (`from`) at the centre, creating a calm,
 * organic flow.
 *
 *  - `from` is the colour of the section ABOVE the divider.
 *  - `to` is the colour of the section BELOW the divider.
 *  - `height` (default 80 px on desktop) — the divider's total height.
 *
 * Render directly between two `<section>` elements:
 * ```tsx
 * <section className="bg-blue-950">…</section>
 * <CurveDivider from="navy" to="paper" />
 * <section className="bg-paper">…</section>
 * ```
 */
type Surface = "paper" | "cream" | "white" | "navy";

const COLOR: Record<Surface, string> = {
  paper: "var(--color-paper)",
  cream: "var(--color-cream)",
  white: "#ffffff",
  navy: "var(--color-blue-950)",
};

export function CurveDivider({
  from,
  to,
  height = 70,
  className,
}: {
  from: Surface;
  to: Surface;
  height?: number;
  className?: string;
}) {
  const fromColor = COLOR[from];
  const toColor = COLOR[to];

  // The band is filled with `from` colour; an inner curve filled with the
  // `to` colour rises into the centre, creating a soft mound that lets the
  // next surface peek through.
  return (
    <div
      aria-hidden="true"
      className={cn("relative block w-full", className)}
      style={{ height, background: fromColor }}
    >
      <svg
        viewBox="0 0 1440 100"
        preserveAspectRatio="none"
        className="absolute inset-0 size-full"
      >
        <path
          d="M 0 100 L 1440 100 L 1440 35 C 1080 -5, 360 -5, 0 35 Z"
          fill={toColor}
        />
      </svg>
    </div>
  );
}
