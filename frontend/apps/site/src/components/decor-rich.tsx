/**
 * Décor "riche" partagé entre les pages éditoriales :
 *   - MeshAccent : 4 variantes de gradient radial multi-couches (cobalt /
 *     terra / emerald), couches très subtiles, en `-z-10` derrière le
 *     contenu. À placer dans une section `relative isolate overflow-hidden`.
 *   - HeroNumeral : gros chiffre serif positionné en watermark.
 *   - SideRail : barre verticale + label mono rotated, dans la marge.
 *
 * Ces blocs sont sans copy — toutes les chaînes passent en props.
 */
import type { ReactNode } from "react";

type MeshVariant = "blue" | "warm" | "split" | "dense";

const MESH_STYLES: Record<MeshVariant, React.CSSProperties> = {
  blue: {
    backgroundImage: [
      "radial-gradient(60% 50% at 20% 10%, rgba(14,77,146,0.10), transparent 70%)",
      "radial-gradient(50% 50% at 85% 30%, rgba(58,170,53,0.07), transparent 70%)",
      "radial-gradient(45% 45% at 60% 95%, rgba(194,116,42,0.08), transparent 70%)",
    ].join(", "),
  },
  warm: {
    backgroundImage: [
      "radial-gradient(55% 50% at 10% 100%, rgba(194,116,42,0.12), transparent 70%)",
      "radial-gradient(50% 40% at 85% 0%, rgba(14,77,146,0.09), transparent 70%)",
    ].join(", "),
  },
  split: {
    backgroundImage: [
      "radial-gradient(60% 55% at 0% 50%, rgba(14,77,146,0.10), transparent 70%)",
      "radial-gradient(55% 50% at 100% 50%, rgba(194,116,42,0.10), transparent 70%)",
      "radial-gradient(40% 40% at 50% 100%, rgba(58,170,53,0.06), transparent 70%)",
    ].join(", "),
  },
  dense: {
    backgroundImage: [
      "radial-gradient(50% 45% at 15% 15%, rgba(14,77,146,0.14), transparent 65%)",
      "radial-gradient(45% 40% at 85% 20%, rgba(194,116,42,0.12), transparent 65%)",
      "radial-gradient(45% 40% at 50% 95%, rgba(58,170,53,0.10), transparent 65%)",
      "radial-gradient(35% 35% at 90% 85%, rgba(14,77,146,0.10), transparent 65%)",
    ].join(", "),
  },
};

export function MeshAccent({ variant = "blue" }: { variant?: MeshVariant }) {
  return (
    <div
      aria-hidden="true"
      className="pointer-events-none absolute inset-0 -z-10"
      style={MESH_STYLES[variant]}
    />
  );
}


export function HeroNumeral({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <span
      aria-hidden="true"
      className={`pointer-events-none select-none font-editorial text-[10rem] font-medium leading-none text-blue-950/[0.06] sm:text-[14rem] lg:text-[18rem] ${className ?? ""}`}
    >
      {children}
    </span>
  );
}


export function SideRail({
  label,
  position = "left",
}: {
  label: string;
  position?: "left" | "right";
}) {
  return (
    <div
      aria-hidden="true"
      className={`pointer-events-none absolute top-32 hidden ${
        position === "left" ? "left-6" : "right-6"
      } z-0 flex-col items-center gap-3 lg:flex`}
    >
      <span className="h-12 w-px bg-gradient-to-b from-transparent via-line-200 to-line-200" />
      <span className="rotate-[-90deg] whitespace-nowrap font-mono text-[0.65rem] font-medium uppercase tracking-[0.24em] text-ink-400">
        {label}
      </span>
      <span className="h-12 w-px bg-gradient-to-t from-transparent via-line-200 to-line-200" />
    </div>
  );
}
