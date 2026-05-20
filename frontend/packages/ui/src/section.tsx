import type { ElementType, HTMLAttributes, ReactNode } from "react";
import { cn } from "./cn";
import { Container } from "./container";

type Tone = "default" | "muted" | "dark";

const toneClasses: Record<Tone, string> = {
  default: "bg-paper text-ink-700",
  muted: "bg-cream text-ink-700",
  dark: "bg-blue-950 text-blue-100/85",
};

type SectionProps = HTMLAttributes<HTMLElement> & {
  as?: ElementType;
  tone?: Tone;
  /** vertical rhythm; "hero" is taller */
  spacing?: "hero" | "lg" | "md" | "none";
  containerWidth?: "content" | "wide" | "narrow";
  /** when true, no inner Container is rendered (caller manages layout) */
  bleed?: boolean;
};

const spacingClasses = {
  hero: "py-20 sm:py-24 lg:py-32",
  lg: "py-16 lg:py-24",
  md: "py-12 lg:py-16",
  none: "",
} as const;

export function Section({
  as: Tag = "section",
  tone = "default",
  spacing = "lg",
  containerWidth = "content",
  bleed = false,
  className,
  children,
  ...props
}: SectionProps) {
  return (
    <Tag className={cn(toneClasses[tone], spacingClasses[spacing], className)} {...props}>
      {bleed ? children : <Container width={containerWidth}>{children}</Container>}
    </Tag>
  );
}

/** Inline eyebrow with the institutional hairline. Use `tone="onDark"` on dark
 *  bands. Prefer the `.label-num` utility class for new code. */
export function Eyebrow({
  children,
  className,
  tone = "brand",
}: {
  children: ReactNode;
  className?: string;
  tone?: "brand" | "accent" | "onDark";
}) {
  const color =
    tone === "accent" ? "text-terra-600" : tone === "onDark" ? "text-blue-200" : "text-blue-700";
  return (
    <span
      className={cn(
        "inline-flex items-center gap-2 text-eyebrow font-semibold uppercase tracking-[0.14em]",
        color,
        className,
      )}
    >
      <span aria-hidden="true" className="h-px w-7 bg-current opacity-60" />
      {children}
    </span>
  );
}

type SectionHeaderProps = {
  eyebrow?: ReactNode;
  title: ReactNode;
  description?: ReactNode;
  align?: "left" | "center";
  onDark?: boolean;
  className?: string;
  as?: ElementType;
};

/** Editorial in-section header (Lora serif title + small eyebrow). */
export function SectionHeader({
  eyebrow,
  title,
  description,
  align = "left",
  onDark = false,
  className,
  as: TitleTag = "h2",
}: SectionHeaderProps) {
  return (
    <header
      className={cn(
        "flex flex-col gap-3",
        align === "center" && "items-center text-center",
        align === "center" ? "mx-auto max-w-3xl" : "max-w-4xl",
        className,
      )}
    >
      {eyebrow ? <Eyebrow tone={onDark ? "onDark" : "brand"}>{eyebrow}</Eyebrow> : null}
      <TitleTag
        className={cn(
          "font-editorial text-section font-semibold leading-tight tracking-tight",
          onDark ? "text-white" : "text-ink-900",
        )}
      >
        {title}
      </TitleTag>
      {description ? (
        <p className={cn("max-w-3xl text-lg leading-relaxed", onDark ? "text-blue-100/85" : "text-ink-600")}>
          {description}
        </p>
      ) : null}
    </header>
  );
}
