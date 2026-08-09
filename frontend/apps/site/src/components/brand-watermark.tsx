import { cn } from "@gathe/ui";

/**
 * Filigrane de marque — le monogramme « G » du logo (lettre cobalt + swoosh
 * vert) décliné en très grand format, posé en fond de section pour signer la
 * page discrètement, sans bruit. Purement décoratif : `pointer-events-none`,
 * `aria-hidden`, `-z-10` (le parent doit être `relative isolate overflow-hidden`).
 *
 * `tone` adapte la teinte au fond (clair vs sombre) ; la taille et la position
 * se règlent via `className` sur l'élément (ex. `right-[-4%] top-1/2 h-[26rem] w-[26rem]`).
 * Modéré par défaut (opacité ~5 %) — jamais tape-à-l'œil.
 */
export function BrandWatermark({
  tone = "light",
  className,
}: {
  tone?: "light" | "dark";
  className?: string;
}) {
  const gColor = tone === "dark" ? "#ffffff" : "#0E4D92";
  const opacity = tone === "dark" ? 0.05 : 0.045;

  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 64 64"
      fill="none"
      style={{ opacity }}
      className={cn("pointer-events-none absolute -z-10 select-none", className)}
    >
      {/* G bleu du logo (lettres GAT) */}
      <text
        x="32"
        y="43"
        textAnchor="middle"
        fontFamily="var(--font-syne), ui-sans-serif, system-ui, sans-serif"
        fontSize="40"
        fontWeight={800}
        letterSpacing="-1"
        fill={gColor}
      >
        G
      </text>
      {/* Swoosh vert — signature du logo (lettres HE) */}
      <path
        d="M10 50 C 22 44, 42 44, 54 50"
        stroke="#3AAA35"
        strokeWidth="3.2"
        strokeLinecap="round"
        fill="none"
        opacity={tone === "dark" ? 0.9 : 0.85}
      />
      <circle cx="52" cy="18" r="2.6" fill="#3AAA35" opacity={tone === "dark" ? 0.9 : 0.85} />
    </svg>
  );
}
