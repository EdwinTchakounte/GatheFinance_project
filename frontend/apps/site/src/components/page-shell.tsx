import type { ReactNode } from "react";
import Image from "next/image";

import { Container } from "@gathe/ui";
import { Link } from "@/i18n/navigation";
import { images } from "@/lib/site-config";
import { CurveDivider } from "./curve-divider";

/**
 * Editorial page header — every inner page renders this banner at the top.
 *
 *  - A documentary photograph fills the background (`image` prop or a sensible
 *    default), tinted with a deep navy gradient overlay so the breadcrumb,
 *    eyebrow, H1 and lead always read at AAA contrast.
 *  - Type stack stays editorial: small breadcrumb, numbered eyebrow,
 *    serif Lora H1, optional lead in a quieter weight.
 */
export function PageHeader({
  eyebrow,
  title,
  lead,
  homeLabel,
  image = images.entrepreneurs,
  alt = "",
  nextSurface = "paper",
}: {
  eyebrow?: string;
  title: ReactNode;
  lead?: ReactNode;
  homeLabel: string;
  image?: string;
  alt?: string;
  nextSurface?: "paper" | "cream" | "white";
}) {
  return (
    <>
    <section className="relative isolate overflow-hidden bg-blue-950 text-white">
      {/* Documentary photograph */}
      <Image
        src={image}
        alt={alt}
        fill
        priority
        sizes="100vw"
        className="object-cover object-center"
      />

      {/* Deep navy overlay — readability layer */}
      <div
        aria-hidden="true"
        className="absolute inset-0 bg-[linear-gradient(105deg,rgba(5,29,58,0.92)_0%,rgba(5,29,58,0.82)_45%,rgba(5,29,58,0.6)_100%)]"
      />
      <div aria-hidden="true" className="absolute inset-0 bg-blue-950/25" />

      {/* Hairline top — the bottom transition is handled by CurveDivider */}
      <div aria-hidden="true" className="absolute inset-x-0 top-0 h-px bg-surface-50/12" />

      <Container width="wide" className="relative py-14 sm:py-20 lg:py-24">
        <nav aria-label="Fil d'Ariane" className="text-sm text-blue-100/80">
          <Link href="/" className="transition-colors hover:text-white">
            {homeLabel}
          </Link>
          <span aria-hidden="true" className="mx-2 text-white/30">
            /
          </span>
          <span className="text-white/90">{typeof title === "string" ? title : eyebrow}</span>
        </nav>
        <div className="mt-7">
          {eyebrow ? <span className="label-num label-num--on-dark">{eyebrow}</span> : null}
          <h1 className="mt-4 max-w-5xl text-balance font-editorial text-[clamp(2rem,4.5vw,3.75rem)] font-semibold leading-[1.1] text-white [text-shadow:0_2px_24px_rgba(5,29,58,0.55)]">
            {title}
          </h1>
          {lead ? (
            <p className="mt-6 max-w-3xl text-balance text-[1.0625rem] leading-[1.65] text-blue-50/90 lg:max-w-none lg:text-[0.92rem] lg:leading-[1.55] xl:text-[0.95rem] 2xl:text-[1rem]">
              {lead}
            </p>
          ) : null}
        </div>
      </Container>
    </section>
    <CurveDivider from="navy" to={nextSurface} height={70} />
    </>
  );
}

/** Temporary "content coming" block used by pages not yet integrated. */
export function ComingSoonNote({ children }: { children: ReactNode }) {
  return (
    <Container className="py-16">
      <div className="rounded-lg border border-dashed border-line-200 bg-cream p-8 text-ink-600">
        {children}
      </div>
    </Container>
  );
}
