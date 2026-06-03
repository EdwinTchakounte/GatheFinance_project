import Image from "next/image";
import { getTranslations } from "next-intl/server";
import { ArrowRight } from "lucide-react";

import { buttonClasses, Container } from "@gathe/ui";
import { Link } from "@/i18n/navigation";
import { images } from "@/lib/site-config";
import { Reveal } from "@/components/reveal";
import { SectionHeading } from "@/components/section-heading";

/** Manifesto section — 2 columns on a clean white surface. Left: numbered
 *  eyebrow + serif H2 + lead + objectives list with vertical filet & emerald
 *  bullets + CTA. Right: documentary portrait. No background decoration —
 *  the typography and the photograph do all the work. */
export async function AboutSection({ locale }: { locale: string }) {
  const t = await getTranslations({ locale, namespace: "home" });
  const ta = await getTranslations({ locale, namespace: "about" });
  const objectives = ta.raw("objectives") as string[];

  return (
    <section className="relative isolate overflow-hidden bg-paper section-pad">
      {/* Hairlines top + bottom */}
      <div aria-hidden="true" className="absolute inset-x-0 top-0 h-px bg-line-200" />
      <div aria-hidden="true" className="absolute inset-x-0 bottom-0 h-px bg-line-200" />

      <Container className="relative">
        <div className="grid items-start gap-12 lg:grid-cols-[1fr_0.78fr] lg:gap-20">
          {/* ---- text column ---- */}
          <div>
            <SectionHeading
              number="01"
              eyebrow={ta("missionTitle")}
              title={t("about.title")}
              lead={t("about.text")}
            />

            <ul className="mt-10 space-y-5 border-l border-line-200 pl-7">
              {objectives.map((item, i) => (
                <Reveal as="li" key={i} delay={i * 60} className="relative">
                  <span aria-hidden="true" className="absolute -left-[31px] top-2 size-1.5 rounded-full bg-emerald" />
                  <p className="text-[0.98rem] leading-relaxed text-ink-700">
                    {item}
                  </p>
                </Reveal>
              ))}
            </ul>

            <Reveal delay={500} className="mt-10 flex flex-wrap items-center gap-x-6 gap-y-3">
              <Link href="/a-propos" className={buttonClasses({ variant: "success" })}>
                {t("about.cta")} <ArrowRight aria-hidden="true" className="size-4" />
              </Link>
            </Reveal>
          </div>

          {/* ---- portrait column ---- */}
          <Reveal className="relative">
            <div className="relative aspect-[4/4.4] overflow-hidden rounded-md shadow-[var(--shadow-md)] ring-1 ring-line-200">
              <Image
                src={images.businesswoman}
                alt="Entrepreneuse camerounaise accompagnée par la coopérative"
                fill
                sizes="(min-width: 1024px) 38vw, 90vw"
                className="object-cover"
              />
              <div aria-hidden="true" className="absolute inset-0 bg-gradient-to-t from-blue-950/30 via-transparent to-transparent" />
            </div>
          </Reveal>
        </div>
      </Container>
    </section>
  );
}
