import { cn } from "./cn";

/**
 * Bloc squelette (shimmer/pulse) — remplace les loaders texte « Chargement… »
 * pour un rendu premium cohérent sur portail + admin.
 */
export function Skeleton({ className }: { className?: string }) {
  return (
    <div
      aria-hidden
      className={cn("animate-pulse rounded-md bg-line-100", className)}
    />
  );
}

/** Carte squelette (silhouette d'une ligne/carte de liste). */
export function SkeletonCard({ className }: { className?: string }) {
  return (
    <div
      aria-hidden
      className={cn(
        "animate-pulse rounded-2xl border border-line-200 bg-line-100/60",
        className,
      )}
    />
  );
}

/**
 * Liste de cartes squelette prête à l'emploi — à afficher pendant le chargement
 * initial d'une liste (membres, crédits, paiements…).
 */
export function SkeletonList({
  count = 3,
  cardClassName = "h-20",
  className,
}: {
  count?: number;
  cardClassName?: string;
  className?: string;
}) {
  return (
    <div className={cn("space-y-3", className)} aria-busy="true">
      {Array.from({ length: count }).map((_, i) => (
        <SkeletonCard key={i} className={cardClassName} />
      ))}
    </div>
  );
}
