import { cn } from "@gathe/ui";

/**
 * Decorative blurred circles — modern landing-page accents that sit behind
 * the section content, using the brand palette (blue + emerald + terra) at
 * low opacity. Three preset variants tuned for the three surface registres:
 *  - "dark"  → blobs visible on the navy band
 *  - "light" → soft blobs for cream/white surfaces
 *  - "warm"  → ocre + emerald, for editorial light bands
 *
 * The wrapper is `pointer-events-none` and absolutely positioned at -z-10
 * relative to a `relative isolate overflow-hidden` parent section.
 */
export function DecorBlobs({
  variant = "light",
  className,
}: {
  variant?: "dark" | "light" | "warm";
  className?: string;
}) {
  if (variant === "dark") {
    return (
      <div aria-hidden="true" className={cn("pointer-events-none absolute inset-0 -z-10 overflow-hidden", className)}>
        <span className="absolute -left-32 -top-40 size-[28rem] rounded-full bg-blue-500/22 blur-[120px]" />
        <span className="absolute -right-40 top-32 size-[32rem] rounded-full bg-emerald/15 blur-[140px]" />
        <span className="absolute -bottom-40 left-1/3 size-[24rem] rounded-full bg-terra-500/12 blur-[120px]" />
      </div>
    );
  }

  if (variant === "warm") {
    return (
      <div aria-hidden="true" className={cn("pointer-events-none absolute inset-0 -z-10 overflow-hidden", className)}>
        <span className="absolute -right-32 -top-32 size-[26rem] rounded-full bg-terra-300/30 blur-[110px]" />
        <span className="absolute -bottom-40 -left-32 size-[30rem] rounded-full bg-emerald/22 blur-[110px]" />
        <span className="absolute top-1/3 right-1/4 size-[22rem] rounded-full bg-emerald/14 blur-[120px]" />
      </div>
    );
  }

  // light — default
  return (
    <div aria-hidden="true" className={cn("pointer-events-none absolute inset-0 -z-10 overflow-hidden", className)}>
      <span className="absolute -left-32 -top-32 size-[26rem] rounded-full bg-blue-400/14 blur-[110px]" />
      <span className="absolute -right-40 top-24 size-[26rem] rounded-full bg-emerald/18 blur-[110px]" />
      <span className="absolute -bottom-40 left-1/4 size-[28rem] rounded-full bg-terra-300/18 blur-[120px]" />
    </div>
  );
}
