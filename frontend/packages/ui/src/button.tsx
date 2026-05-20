import type { AnchorHTMLAttributes, ButtonHTMLAttributes, ReactNode } from "react";
import { cn } from "./cn";

export type ButtonVariant = "primary" | "secondary" | "ghost" | "success" | "danger" | "onDark";
export type ButtonSize = "sm" | "md" | "lg";

const base =
  "group/btn inline-flex items-center justify-center gap-2 rounded-full font-medium " +
  "transition-[background-color,border-color,color,box-shadow,transform] duration-[var(--duration-base)] ease-[var(--ease-out-soft)] " +
  "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-500 " +
  "disabled:cursor-not-allowed disabled:opacity-55 select-none";

const variants: Record<ButtonVariant, string> = {
  primary:
    "bg-blue-700 text-white shadow-[var(--shadow-sm)] hover:bg-blue-800 hover:-translate-y-0.5 hover:shadow-[var(--shadow-md)] active:translate-y-0",
  secondary:
    "border border-blue-700/25 bg-white text-blue-700 hover:border-blue-700/45 hover:bg-blue-50 hover:-translate-y-0.5 hover:shadow-[var(--shadow-sm)]",
  ghost: "text-blue-700 hover:bg-blue-50",
  success:
    "bg-green-600 text-white shadow-[var(--shadow-sm)] hover:bg-green-700 hover:-translate-y-0.5 hover:shadow-[var(--shadow-md)] active:translate-y-0",
  danger:
    "bg-[#ba2121] text-white shadow-[var(--shadow-sm)] hover:bg-[#9a1818] hover:-translate-y-0.5 hover:shadow-[var(--shadow-md)] active:translate-y-0",
  onDark:
    "bg-white/12 text-white ring-1 ring-inset ring-white/25 backdrop-blur-md hover:bg-white/20 hover:ring-white/45 hover:-translate-y-0.5",
};

const sizes: Record<ButtonSize, string> = {
  sm: "h-9 px-4 text-sm",
  md: "h-11 px-6 text-[0.9375rem]",
  lg: "h-12 px-7 text-base",
};

/**
 * Class string for the button look — use it to style a framework `<Link>`:
 * `<Link className={buttonClasses({ size: "sm" })}>…</Link>`.
 */
export function buttonClasses(opts: { variant?: ButtonVariant; size?: ButtonSize; fullWidth?: boolean } = {}): string {
  const { variant = "primary", size = "md", fullWidth } = opts;
  return cn(base, variants[variant], sizes[size], fullWidth && "w-full");
}

type CommonProps = {
  variant?: ButtonVariant;
  size?: ButtonSize;
  iconLeft?: ReactNode;
  iconRight?: ReactNode;
  fullWidth?: boolean;
};

export type ButtonProps = CommonProps & ButtonHTMLAttributes<HTMLButtonElement>;
export type ButtonLinkProps = CommonProps & AnchorHTMLAttributes<HTMLAnchorElement>;

function content(children: ReactNode, iconLeft?: ReactNode, iconRight?: ReactNode) {
  return (
    <>
      {iconLeft ? <span aria-hidden="true" className="-ml-0.5 inline-flex shrink-0">{iconLeft}</span> : null}
      {children}
      {iconRight ? <span aria-hidden="true" className="-mr-0.5 inline-flex shrink-0">{iconRight}</span> : null}
    </>
  );
}

export function Button({
  variant = "primary",
  size = "md",
  iconLeft,
  iconRight,
  fullWidth,
  className,
  children,
  ...props
}: ButtonProps) {
  return (
    <button
      className={cn(base, variants[variant], sizes[size], fullWidth && "w-full", className)}
      {...props}
    >
      {content(children, iconLeft, iconRight)}
    </button>
  );
}

export function ButtonLink({
  variant = "primary",
  size = "md",
  iconLeft,
  iconRight,
  fullWidth,
  className,
  children,
  ...props
}: ButtonLinkProps) {
  return (
    <a
      className={cn(base, variants[variant], sizes[size], fullWidth && "w-full", className)}
      {...props}
    >
      {content(children, iconLeft, iconRight)}
    </a>
  );
}
