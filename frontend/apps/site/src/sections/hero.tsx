import { getTranslations } from "next-intl/server";
import { ArrowRight, BadgePercent, Briefcase, ChevronDown, Coins } from "lucide-react";

import { buttonClasses, Container } from "@gathe/ui";
import { Link } from "@/i18n/navigation";
import { images } from "@/lib/site-config";
import { Reveal } from "@/components/reveal";
import { CountUp } from "@/components/motion/count-up";
import { HeroSlider } from "@/components/hero-slider";
import { DecorBlobs } from "@/components/decor-blobs";
import { Magnetic } from "@/components/magnetic";

/** Institutional hero — documentary slide carousel behind a deep navy
 *  overlay. Eyebrow, headline and lead are centered to put the editorial
 *  statement front-and-centre; the lead is set in a serif voice so it reads
 *  like a press chapeau rather than UI body copy. */
export async function Hero({ locale }: { locale: string }) {
  const t = await getTranslations({ locale, namespace: "home" });
  const ta = await getTranslations({ locale, namespace: "about" });

  const slides = [
    { src: images.entrepreneurs },
    { src: images.brcBusinessFormation },
    { src: images.businesswoman },
    { src: images.brcTeamSupport },
    { src: images.entrepreneurFamily },
    { src: images.brcTeamEnterprise },
    { src: images.fatherDaughterSaving },
  ];

  return (
    <section className="relative isolate flex min-h-[88svh] flex-col overflow-hidden bg-blue-950 text-white">
      <HeroSlider slides={slides} />

      {/* Decorative blobs floating above the slider overlay for soft depth */}
      <DecorBlobs variant="dark" />

      <div aria-hidden="true" className="absolute inset-x-0 top-0 h-px bg-surface-50/12" />

      {/* Editorial filigree — large Lora "G" drop-cap in the top-left corner,
          partially clipped. Reads like a print magazine signature. Visible
          only from `lg` (≥ 1024px) where the hero has the room. */}
      <span
        aria-hidden="true"
        className={
          "pointer-events-none absolute -left-10 top-2 -z-[5] hidden select-none " +
          "font-editorial font-bold leading-none text-terra-300/[0.14] " +
          "lg:block lg:text-[16rem] xl:-left-16 xl:top-0 xl:text-[20rem] 2xl:text-[24rem]"
        }
      >
        G
      </span>

      {/* Main content — centered editorial block */}
      <div className="flex flex-1 items-center">
        <Container className="relative py-20 lg:py-24">
          <div className="relative mx-auto max-w-4xl text-center">
            <Reveal>
              <span className="label-num label-num--on-dark mx-auto">{t("hero.eyebrow")}</span>
            </Reveal>
            <Reveal delay={120}>
              <h1 className="mt-7 font-editorial text-display font-semibold leading-[1.02] tracking-[-0.02em] text-white [text-shadow:0_2px_28px_rgba(5,29,58,0.6)]">
                <span className="block whitespace-nowrap text-white">{t("hero.titlePre")}</span>
                <span className="mt-1 block text-emerald sm:mt-2">{t("hero.titleAccent")}</span>
              </h1>
            </Reveal>
            <Reveal delay={240}>
              <p
                className={
                  "mx-auto mt-9 max-w-3xl text-balance font-editorial italic " +
                  "text-[clamp(1.1rem,1.65vw,1.45rem)] leading-[1.55] text-blue-50"
                }
              >
                <span className="text-emerald/80 font-display not-italic mr-1.5">“</span>
                {t("hero.text")}
                <span className="text-emerald/80 font-display not-italic ml-1.5">”</span>
              </p>
            </Reveal>
            <Reveal delay={340}>
              <div className="mt-10 flex flex-col items-center justify-center gap-3 sm:flex-row">
                <Magnetic strength={0.32}>
                  <Link href="/devenir-membre" className={buttonClasses({ variant: "success", size: "lg" })}>
                    {t("hero.primaryCta")} <ArrowRight aria-hidden="true" className="size-4" />
                  </Link>
                </Magnetic>
                <Magnetic strength={0.22}>
                  <Link href="/services-financiers" className={buttonClasses({ variant: "onDark", size: "lg" })}>
                    {t("hero.secondaryCta")}
                  </Link>
                </Magnetic>
              </div>
            </Reveal>
          </div>
        </Container>
      </div>

      {/* Scroll hint — sober chevron + pulsing emerald filet, sits just above
          the KPI band. Hidden on mobile (the hero is already compact there). */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-x-0 bottom-[58px] z-10 hidden justify-center sm:bottom-[60px] sm:flex lg:bottom-[68px]"
      >
        <div className="flex flex-col items-center gap-1.5">
          <span className="font-display text-[0.6rem] font-medium uppercase tracking-[0.24em] text-emerald/80">
            Scroll
          </span>
          <span className="block h-7 w-px bg-emerald/55 scroll-hint-rule" />
          <ChevronDown aria-hidden="true" className="size-3.5 text-emerald scroll-hint-chevron" />
        </div>
      </div>

      {/* Stats strip — ultra-thin KPI band: 3-on-one-line everywhere, drastic
          height reduction (≈ 36-44px overall). Labels are folded into a single
          line next to the value, separated by a hairline em-dash. */}
      <div className="border-t border-white/15 bg-blue-950/90 backdrop-blur-sm">
        <Container className="grid grid-cols-3 items-center gap-2 py-1.5 sm:gap-5 sm:py-2 lg:py-2.5">
          <div className="flex items-center gap-1.5 sm:gap-2.5">
            <Briefcase aria-hidden="true" className="size-3.5 shrink-0 text-emerald sm:size-[18px]" />
            <p className="flex min-w-0 items-baseline gap-1.5 truncate font-display text-[0.78rem] leading-none text-white sm:text-[0.95rem]">
              <span className="font-semibold tracking-tight">
                <CountUp value={4500} locale={locale} />
              </span>
              <span className="hidden text-[0.7rem] font-normal text-blue-200/75 sm:inline">
                · {t("stats.projectsLabel")}
              </span>
            </p>
          </div>
          <div className="flex items-center gap-1.5 border-l border-white/12 pl-2 sm:gap-2.5 sm:pl-4 lg:pl-6">
            <Coins aria-hidden="true" className="size-3.5 shrink-0 text-emerald sm:size-[18px]" />
            <p className="flex min-w-0 items-baseline gap-1.5 truncate font-display text-[0.78rem] leading-none text-white sm:text-[0.95rem]">
              <span className="font-semibold tracking-tight">
                <CountUp value={400} locale={locale} suffix={` ${t("stats.fundedSuffix")}`} />
              </span>
              <span className="hidden text-[0.7rem] font-normal text-blue-200/75 sm:inline">
                · {t("stats.fundedLabel")}
              </span>
            </p>
          </div>
          <div className="flex items-center gap-1.5 border-l border-white/12 pl-2 sm:gap-2.5 sm:pl-4 lg:pl-6">
            <BadgePercent aria-hidden="true" className="size-3.5 shrink-0 text-emerald sm:size-[18px]" />
            <p className="truncate font-display text-[0.78rem] font-semibold leading-none tracking-tight text-emerald sm:text-[0.95rem]">
              {ta("zeroInterestBadge")}
            </p>
          </div>
        </Container>
      </div>
    </section>
  );
}
