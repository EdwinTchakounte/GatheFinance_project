import type { ImgHTMLAttributes } from "react";
import { cn } from "./cn";

/**
 * GATHE Finance wordmark — transparent PNG (`/images/logo.png`, derived from
 * the official JPG with the white background made transparent so the mark
 * blends with any surface). Height is set by the parent via className.
 *
 * The variant prop is kept for API compatibility with the previous SVG
 * implementation; the rendered asset is always the same PNG.
 */
export type LogoVariant = "color" | "light" | "dark";

export interface LogoProps extends Omit<ImgHTMLAttributes<HTMLImageElement>, "src" | "alt"> {
  variant?: LogoVariant;
  title?: string;
}

const LOGO_SRC = "/images/logo.png";

export function Logo({
  variant: _variant,
  title = "GATHE Finance",
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
