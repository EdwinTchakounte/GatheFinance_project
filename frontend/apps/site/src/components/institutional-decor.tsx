/**
 * Modern institutional decoration layer for calm bands.
 *
 *  Registre: Afro-futurisme institutionnel + fintech premium
 *  Inspirations: Stripe / Linear / Bloomberg / Flutterwave dot-grids,
 *  network constellations, financial flow lines, modernised African
 *  textile chevrons.
 *
 *  Four variants alternate across sections to avoid repetition:
 *   - `grid`   dot-grid + slim cobalt→copper flow curve
 *   - `nodes`  data-network constellation anchored top-right
 *   - `weave`  African chevron tile + single copper hairline
 *   - `flow`   three parallel financial flow curves (cobalt / copper / emerald)
 *
 *  All elements:
 *   - pointer-events-none, sit on -z-10 behind content
 *   - hairlines 0.5–1.2px, opacity 0.06–0.18 max
 *   - no gradient blobs, no blur — geometry only
 *
 *  The parent section must be `relative isolate overflow-hidden`.
 */
type Variant = "grid" | "nodes" | "weave" | "flow";

export function InstitutionalDecor({ variant = "grid" }: { variant?: Variant }) {
  return (
    <div aria-hidden="true" className="pointer-events-none absolute inset-0 -z-10 overflow-hidden">
      {variant === "grid" ? <GridDecor /> : null}
      {variant === "nodes" ? <NodesDecor /> : null}
      {variant === "weave" ? <WeaveDecor /> : null}
      {variant === "flow" ? <FlowDecor /> : null}
    </div>
  );
}

/* — Stripe-style dot grid + slim financial-flow curve ——————————————— */
function GridDecor() {
  return (
    <>
      <div
        className="absolute inset-0"
        style={{
          backgroundImage:
            "radial-gradient(circle, rgba(14,77,146,0.10) 1px, transparent 1px)",
          backgroundSize: "32px 32px",
          maskImage:
            "linear-gradient(180deg, rgba(0,0,0,0.85), rgba(0,0,0,0.4) 70%, rgba(0,0,0,0))",
          WebkitMaskImage:
            "linear-gradient(180deg, rgba(0,0,0,0.85), rgba(0,0,0,0.4) 70%, rgba(0,0,0,0))",
        }}
      />
      <svg
        viewBox="0 0 1200 800"
        preserveAspectRatio="none"
        className="absolute inset-0 size-full"
      >
        <defs>
          <linearGradient id="gathe-flow-grid" x1="0" x2="1" y1="0" y2="0">
            <stop offset="0" stopColor="rgba(14,77,146,0)" />
            <stop offset="0.5" stopColor="rgba(194,116,42,0.45)" />
            <stop offset="1" stopColor="rgba(14,77,146,0)" />
          </linearGradient>
        </defs>
        <path
          d="M -40 640 C 320 280, 880 760, 1240 200"
          stroke="url(#gathe-flow-grid)"
          strokeWidth="1.4"
          fill="none"
        />
      </svg>
    </>
  );
}

/* — Data network constellation, corner-anchored top-right ——————————————— */
function NodesDecor() {
  return (
    <svg
      viewBox="0 0 600 400"
      className="absolute -right-12 -top-8 h-[24rem] w-[36rem] max-w-[70%] opacity-90 md:h-[28rem] md:w-[44rem]"
      aria-hidden="true"
    >
      <g stroke="rgba(14,77,146,0.18)" strokeWidth="0.6" fill="none">
        <line x1="60" y1="80" x2="180" y2="140" />
        <line x1="180" y1="140" x2="300" y2="60" />
        <line x1="300" y1="60" x2="430" y2="150" />
        <line x1="430" y1="150" x2="540" y2="80" />
        <line x1="180" y1="140" x2="320" y2="260" />
        <line x1="320" y1="260" x2="430" y2="150" />
        <line x1="320" y1="260" x2="200" y2="340" />
        <line x1="430" y1="150" x2="510" y2="320" />
        <line x1="60" y1="80" x2="180" y2="260" />
      </g>
      <g fill="rgba(14,77,146,0.32)">
        <circle cx="60" cy="80" r="2.6" />
        <circle cx="180" cy="140" r="2.6" />
        <circle cx="430" cy="150" r="2.6" />
        <circle cx="540" cy="80" r="2.6" />
        <circle cx="320" cy="260" r="2.6" />
        <circle cx="200" cy="340" r="2.6" />
        <circle cx="510" cy="320" r="2.6" />
        <circle cx="180" cy="260" r="2.6" />
      </g>
      {/* Copper accent nodes — sparingly placed for emphasis */}
      <g fill="rgba(194,116,42,0.55)">
        <circle cx="300" cy="60" r="3" />
        <circle cx="320" cy="260" r="2" />
      </g>
      {/* Outer ring on hub node */}
      <circle
        cx="300"
        cy="60"
        r="8"
        stroke="rgba(194,116,42,0.30)"
        strokeWidth="0.6"
        fill="none"
      />
    </svg>
  );
}

/* — Modernised African chevron weave + single copper hairline ——————— */
function WeaveDecor() {
  return (
    <>
      <div
        className="absolute inset-0"
        style={{
          backgroundImage: `url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='80' height='40' viewBox='0 0 80 40'><path d='M 0 40 L 20 0 L 40 40 L 60 0 L 80 40' stroke='rgba(14,77,146,0.09)' stroke-width='0.9' fill='none'/></svg>")`,
          backgroundSize: "80px 40px",
          maskImage:
            "linear-gradient(180deg, rgba(0,0,0,0), rgba(0,0,0,0.7) 30%, rgba(0,0,0,0.7) 70%, rgba(0,0,0,0))",
          WebkitMaskImage:
            "linear-gradient(180deg, rgba(0,0,0,0), rgba(0,0,0,0.7) 30%, rgba(0,0,0,0.7) 70%, rgba(0,0,0,0))",
        }}
      />
      <svg
        viewBox="0 0 1200 800"
        preserveAspectRatio="none"
        className="absolute inset-0 size-full"
      >
        <defs>
          <linearGradient id="gathe-weave-rule" x1="0" x2="1" y1="0" y2="0">
            <stop offset="0" stopColor="rgba(194,116,42,0)" />
            <stop offset="0.5" stopColor="rgba(194,116,42,0.4)" />
            <stop offset="1" stopColor="rgba(194,116,42,0)" />
          </linearGradient>
        </defs>
        <line
          x1="0"
          y1="400"
          x2="1200"
          y2="400"
          stroke="url(#gathe-weave-rule)"
          strokeWidth="0.8"
        />
      </svg>
    </>
  );
}

/* — Three parallel financial-flow curves (cobalt / copper / emerald) ——— */
function FlowDecor() {
  return (
    <svg
      viewBox="0 0 1200 800"
      preserveAspectRatio="none"
      className="absolute inset-0 size-full"
    >
      <defs>
        <linearGradient id="gathe-flow-a" x1="0" x2="1" y1="0" y2="0">
          <stop offset="0" stopColor="rgba(14,77,146,0)" />
          <stop offset="0.5" stopColor="rgba(14,77,146,0.34)" />
          <stop offset="1" stopColor="rgba(14,77,146,0)" />
        </linearGradient>
        <linearGradient id="gathe-flow-b" x1="0" x2="1" y1="0" y2="0">
          <stop offset="0" stopColor="rgba(194,116,42,0)" />
          <stop offset="0.5" stopColor="rgba(194,116,42,0.40)" />
          <stop offset="1" stopColor="rgba(194,116,42,0)" />
        </linearGradient>
        <linearGradient id="gathe-flow-c" x1="0" x2="1" y1="0" y2="0">
          <stop offset="0" stopColor="rgba(58,170,53,0)" />
          <stop offset="0.5" stopColor="rgba(58,170,53,0.28)" />
          <stop offset="1" stopColor="rgba(58,170,53,0)" />
        </linearGradient>
      </defs>
      <g fill="none" strokeWidth="1.2">
        <path
          d="M -50 200 C 280 60, 880 360, 1250 120"
          stroke="url(#gathe-flow-a)"
        />
        <path
          d="M -50 400 C 280 240, 880 560, 1250 360"
          stroke="url(#gathe-flow-b)"
        />
        <path
          d="M -50 600 C 280 440, 880 760, 1250 580"
          stroke="url(#gathe-flow-c)"
        />
      </g>
    </svg>
  );
}
