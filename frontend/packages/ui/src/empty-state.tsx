import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

import { cn } from "./cn";

export type EmptyStateTone = "blue" | "green" | "neutral";

/**
 * État vide premium unifié GATHE : icône dans un cercle teinté + titre + texte
 * (+ action optionnelle). Remplace les « Aucun… » texte-brut disséminés pour un
 * rendu cohérent sur portail + admin.
 *
 *   <EmptyState icon={Inbox} title="Aucune notification" message="…" />
 */
export function EmptyState({
  icon: Icon,
  title,
  message,
  tone = "blue",
  action,
  className,
}: {
  icon: LucideIcon;
  title: string;
  message?: ReactNode;
  tone?: EmptyStateTone;
  action?: ReactNode;
  className?: string;
}) {
  const tint: Record<EmptyStateTone, string> = {
    blue: "bg-blue-50 text-blue-700",
    green: "bg-green-50 text-green-600",
    neutral: "bg-line-100 text-ink-500",
  };
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center rounded-2xl border border-dashed border-line-200 bg-paper/60 px-6 py-12 text-center",
        className,
      )}
    >
      <span
        className={cn(
          "flex h-16 w-16 items-center justify-center rounded-full",
          tint[tone],
        )}
      >
        <Icon className="h-7 w-7" strokeWidth={1.75} />
      </span>
      <p className="mt-4 font-display text-lg text-ink-900">{title}</p>
      {message ? (
        <p className="mt-1.5 max-w-sm text-sm text-ink-600">{message}</p>
      ) : null}
      {action ? <div className="mt-5">{action}</div> : null}
    </div>
  );
}
