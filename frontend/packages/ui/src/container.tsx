import type { ElementType, HTMLAttributes } from "react";
import { cn } from "./cn";

type ContainerProps = HTMLAttributes<HTMLElement> & {
  as?: ElementType;
  /**
   * "content"  — wide page container (~1920px) — the default, fills the screen.
   * "narrow"   — readable text column (~768px), for article bodies / long copy.
   * "wide" / "full" — no max-width, just the gutters (full-bleed bands).
   * "flush"    — no max-width and no gutters (edge-to-edge media).
   */
  width?: "content" | "narrow" | "wide" | "full" | "flush";
};

const widths = {
  content: "max-w-[var(--container-content)] px-5 sm:px-7 lg:px-9 xl:px-12",
  narrow: "max-w-[var(--container-text)] px-5 sm:px-7 lg:px-9 xl:px-12",
  wide: "max-w-none px-5 sm:px-7 lg:px-9 xl:px-12",
  full: "max-w-none px-5 sm:px-7 lg:px-9 xl:px-12",
  flush: "max-w-none",
} as const;

export function Container({ as: Tag = "div", width = "content", className, ...props }: ContainerProps) {
  return <Tag className={cn("mx-auto w-full", widths[width], className)} {...props} />;
}
