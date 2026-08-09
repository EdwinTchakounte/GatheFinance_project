import Image from "next/image";
import { getTranslations } from "next-intl/server";
import { ArrowRight } from "lucide-react";

import { buttonClasses, Container } from "@gathe/ui";
import { Link } from "@/i18n/navigation";
import { images } from "@/lib/site-config";
import { Reveal } from "@/components/reveal";
import { SectionHeading } from "@/components/section-heading";
import { AboutObjectives } from "@/components/about-objectives";

/** Manifesto section — 2 columns on a clean white surface. Left: numbered
 *  eyebrow + serif H2 + lead + objectives list with vertical filet & emerald
 *  bullets + CTA. Right: documentary portrait. No background decoration —
 *  the typography and the photograph do all the work. */
export async function AboutSection({ locale }: { locale: string }) {
  const t = await getTranslations({ locale, namespace: "home" });
  const ta = await getTranslations({ locale, namespace: "about" });
  const tc = await getTranslations({ locale, namespace: "common" });
  const objectives = ta.raw("objectives") as string[];

  return (
    <section className="relative isolate overflow-hidden bg-sand section-pad-sm">
      {/* Bande éditoriale chaude (sable) — l'UNIQUE de la page (cf. DS).
          Filets top/bottom légèrement plus chauds que le slate pur. */}
      <div aria-hidden="true" className="absolute inset-x-0 top-0 h-px bg-terra-200/60" />
      <div aria-hidden="true" className="absolute inset-x-0 bottom-0 h-px bg-terra-200/60" />

      <Container className="relative">
        {/* items-stretch : la colonne image épouse la hauteur de la colonne
            texte → image et texte alignés (haut ET bas). */}
        <div className="grid items-stretch gap-10 lg:grid-cols-[1fr_0.82fr] lg:gap-14">
          {/* ---- text column ---- */}
          <div className="flex flex-col">
            <SectionHeading
              number="01"
              eyebrow={ta("missionTitle")}
              title={t("about.title")}
              lead={t("about.text")}
              wideLead
            />

            {/* Objectifs repliés (3) + « Voir plus » — garde la colonne à une
                hauteur proche de la photo. */}
            <AboutObjectives
              items={objectives}
              moreLabel={tc("showMore")}
              lessLabel={tc("showLess")}
            />

            <div className="mt-auto pt-8">
              <Link href="/a-propos" className={buttonClasses({ variant: "success" })}>
                {t("about.cta")} <ArrowRight aria-hidden="true" className="size-4" />
              </Link>
            </div>
          </div>

          {/* ---- portrait column — s'étire à la hauteur du texte ---- */}
          <Reveal className="relative">
            <div className="relative h-full min-h-[18rem] overflow-hidden rounded-2xl shadow-[var(--shadow-md)] ring-1 ring-line-200">
              <Image
                src={images.businesswoman}
                alt="Entrepreneuse camerounaise accompagnée par la coopérative"
                fill
                sizes="(min-width: 1024px) 40vw, 90vw"
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
