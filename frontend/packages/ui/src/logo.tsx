import type { ImgHTMLAttributes } from "react";
import { cn } from "./cn";

/**
 * Gathe Finance wordmark — official downloaded JPG (`/images/logo.jpg`,
 * byte-identical to the upstream gathe-finance.com asset). Height is set by
 * the parent via className (e.g. `h-14 w-auto`).
 *
 * The variant prop is kept for API compatibility with the previous SVG
 * implementation; the rendered asset is always the same JPG.
 */
export type LogoVariant = "color" | "light" | "dark";

export interface LogoProps extends Omit<ImgHTMLAttributes<HTMLImageElement>, "src" | "alt"> {
  variant?: LogoVariant;
  title?: string;
}

const LOGO_SRC = "/images/logo.jpg";

export function Logo({
  variant: _variant,
  title = "Gathe Finance",
  className,
  ...rest
}: LogoProps) {
  void _variant;
  return (
    <img
      src={LOGO_SRC}
      alt={title}
      className={cn("block h-auto w-auto select-none", className)}
      loading="eager"
      decoding="async"
      draggable={false}
      {...rest}
    />
  );
}
