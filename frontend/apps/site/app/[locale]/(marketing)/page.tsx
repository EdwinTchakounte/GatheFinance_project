import Image from "next/image";
import { getTranslations, setRequestLocale } from "next-intl/server";
import { ArrowRight, ArrowUpRight } from "lucide-react";

import { buttonClasses, cn, Container } from "@gathe/ui";
import { Link } from "@/i18n/navigation";
import { ArticleCard } from "@/components/article-card";
import { InstitutionalDecor } from "@/components/institutional-decor";
import { CtaBand } from "@/components/cta-band";
import { CurveDivider } from "@/components/curve-divider";
import { Reveal } from "@/components/reveal";
import { SectionHeading } from "@/components/section-heading";
import { Hero } from "@/sections/hero";
import { AboutSection } from "@/sections/about";
import { servicePillars, siteConfig } from "@/lib/site-config";
import { getBlogPosts } from "@/lib/wagtail";

type Params = { params: Promise<{ locale: string }> };

const VALUES = ["accessibility", "transparency", "community", "local"] as const;

// Home shows 4 services (matches the reference site: Crédit, Épargne, Transferts, Investissement).
// "education" stays in the codebase for the inner "Services financiers" page.
const HOME_PILLAR_KEYS = ["credit", "savings", "transfers", "investment"] as const;

export default async function HomePage({ params }: Params) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations({ locale, namespace: "home" });
  const tc = await getTranslations({ locale, namespace: "common" });
  const ta = await getTranslations({ locale, namespace: "about" });
  const ts = await getTranslations({ locale, namespace: "services" });
  const tn = await getTranslations({ locale, namespace: "nav" });
  const posts = await getBlogPosts(locale, 3);

  return (
    <>
      <Hero locale={locale} />

      <CurveDivider from="navy" to="cream" height={70} />

      {/* ===== Trust strip — clean BRC ecosystem signature ===== */}
      <div className="bg-cream">
        <Container className="flex items-center justify-center py-4 text-center text-sm text-ink-600">
          <span>
            {ta("initiativeOf")}{" "}
            <a
              href={siteConfig.brc.url}
              target="_blank"
              rel="noopener noreferrer"
              className="font-medium text-ink-900 underline decoration-terra-400 underline-offset-2 transition-colors hover:decoration-terra-600"
            >
              {siteConfig.brc.name}
            </a>
          </span>
        </Container>
      </div>

      {/* ===== MANIFESTO — institutional dark band ===== */}
      <AboutSection locale={locale} />


      {/* ===== SERVICES — 4 cards (matches the reference site) ===== */}
      <section className="relative isolate overflow-hidden section-pad bg-paper">
        <InstitutionalDecor variant="grid" />
        <Container>
          <SectionHeading
            number="02"
            eyebrow={t("services.eyebrow")}
            title={t("services.title")}
            lead={ts("lead")}
          />

          {/* Bento asymmetric — 1 big tall card on the left, 2 stacked cards
              on the right, 1 wide horizontal card below. Cleanly degrades to
              a single column on mobile. */}
          <div className="mt-14 grid grid-cols-1 gap-5 md:grid-cols-12 md:gap-6 lg:mt-16">
            {servicePillars
              .filter((p) => HOME_PILLAR_KEYS.includes(p.key as (typeof HOME_PILLAR_KEYS)[number]))
              .map((pillar, i, arr) => {
                const isBig = i === 0;
                const isWide = i === arr.length - 1;
                const spanClass = isBig
                  ? "md:col-span-7 md:row-span-2"
                  : isWide
                    ? "md:col-span-12"
                    : "md:col-span-5";

                return (
                  <Reveal
                    key={pillar.key}
                    as="article"
                    delay={i * 80}
                    className={cn(
                      "group relative flex overflow-hidden rounded-md border border-line-200/70 bg-cream/35 backdrop-blur-sm",
                      "transition-shadow duration-500 hover:shadow-[var(--shadow-md)]",
                      spanClass,
                      isWide ? "flex-col md:flex-row md:items-stretch" : "flex-col",
                    )}
                  >
                    <div
                      className={cn(
                        "relative shrink-0 overflow-hidden",
                        isWide
                          ? "aspect-[16/9] md:aspect-auto md:w-[52%] md:min-h-[260px]"
                          : isBig
                            ? "aspect-[4/4.4] md:aspect-[4/4.6]"
                            : "aspect-[16/10]",
                      )}
                    >
                      <Image
                        src={pillar.image}
                        alt={pillar.alt}
                        fill
                        sizes={
                          isBig
                            ? "(min-width: 768px) 58vw, 92vw"
                            : isWide
                              ? "(min-width: 768px) 50vw, 92vw"
                              : "(min-width: 768px) 42vw, 92vw"
                        }
                        className="object-cover transition-transform duration-[900ms] ease-out group-hover:scale-[1.04]"
                      />
                      <span className="absolute left-3 top-3 bg-paper px-2.5 py-1 font-display text-[0.68rem] font-medium uppercase tracking-[0.14em] text-blue-700 shadow-sm">
                        {`0${i + 1}`} · {tn(pillar.labelKey)}
                      </span>
                      {/* Soft bottom gradient for caption readability on tall cards */}
                      {isBig ? (
                        <span
                          aria-hidden="true"
                          className="pointer-events-none absolute inset-x-0 bottom-0 h-24 bg-gradient-to-t from-blue-950/35 to-transparent"
                        />
                      ) : null}
                    </div>

                    <div
                      className={cn(
                        "flex flex-1 flex-col p-5 lg:p-6",
                        isBig && "lg:p-8",
                        isWide && "md:justify-center md:p-8 lg:p-10",
                      )}
                    >
                      <h3
                        className={cn(
                          "font-editorial font-medium leading-[1.22] text-ink-900",
                          isBig
                            ? "text-[1.55rem] lg:text-[1.85rem]"
                            : isWide
                              ? "text-[1.4rem] lg:text-[1.65rem]"
                              : "text-headline",
                        )}
                      >
                        {ts(`pillars.${pillar.key}.title`)}
                      </h3>
                      <p
                        className={cn(
                          "mt-3 grow leading-[1.65] text-ink-600",
                          isBig ? "text-[1rem]" : "text-[0.95rem]",
                        )}
                      >
                        {ts.rich(`pillars.${pillar.key}.intro`, {
                          strong: (c) => <strong className="text-ink-900">{c}</strong>,
                        })}
                      </p>
                      <Link
                        href={`/services-financiers#${pillar.anchor}`}
                        className="group/lnk mt-5 inline-flex items-center gap-1.5 text-sm font-semibold text-blue-700 transition-colors hover:text-blue-800"
                      >
                        {tc("learnMore")}
                        <ArrowRight
                          aria-hidden="true"
                          className="size-4 transition-transform duration-300 group-hover/lnk:translate-x-1"
                        />
                      </Link>
                    </div>

                    {/* Soft emerald accent that slides in on card hover */}
                    <span
                      aria-hidden="true"
                      className="pointer-events-none absolute inset-x-0 bottom-0 h-0.5 origin-left scale-x-0 bg-emerald transition-transform duration-500 group-hover:scale-x-100"
                    />
                  </Reveal>
                );
              })}
          </div>
        </Container>
      </section>


      {/* ===== VALUES — press grid on cream, hairline cards, no shadows ===== */}
      <section className="relative isolate overflow-hidden section-pad bg-paper">
        <InstitutionalDecor variant="weave" />
        <Container>
          <SectionHeading
            number="03"
            eyebrow={t("values.eyebrow")}
            title={t("values.title")}
          />

          <div className="mt-14 grid gap-px bg-line-200 sm:grid-cols-2 lg:grid-cols-4">
            {VALUES.map((v, i) => (
              <Reveal
                as="div"
                key={v}
                delay={i * 70}
                className="group relative flex flex-col bg-cream p-7 transition-colors hover:bg-paper lg:p-9"
              >
                <span className="font-display text-[0.72rem] font-medium tracking-[0.12em] text-terra-600">
                  {`0${i + 1}`}
                </span>
                <h3 className="mt-3 font-editorial text-xl font-medium leading-snug text-ink-900">
                  {t(`values.items.${v}.title`)}
                </h3>
                <p className="mt-3 text-sm leading-relaxed text-ink-600">
                  {t(`values.items.${v}.text`)}
                </p>
              </Reveal>
            ))}
          </div>
        </Container>
      </section>


      {/* ===== BLOG teaser ===== */}
      <section className="relative isolate overflow-hidden section-pad bg-paper">
        <InstitutionalDecor variant="nodes" />
        <Container>
          <div className="flex flex-wrap items-end justify-between gap-6 border-b border-line-200 pb-8">
            <SectionHeading
              number="04"
              eyebrow={t("blog.eyebrow")}
              title={t("blog.title")}
            />
            <Link
              href="/blog"
              className="group/lnk inline-flex items-center gap-1.5 pb-1 text-sm font-semibold text-blue-700 transition-colors hover:text-blue-800"
            >
              {t("blog.viewAll")}
              <ArrowUpRight aria-hidden="true" className="size-4 transition-transform group-hover/lnk:translate-x-0.5 group-hover/lnk:-translate-y-0.5" />
            </Link>
          </div>
          <div className="mt-12 grid gap-x-8 gap-y-10 sm:grid-cols-2 lg:grid-cols-3">
            {posts.length > 0
              ? posts.map((post, i) => (
                  <Reveal key={post.id} delay={i * 80}>
                    <ArticleCard post={post} locale={locale} />
                  </Reveal>
                ))
              : Array.from({ length: 3 }).map((_, i) => (
                  <div key={i} className="border-t border-line-200 pt-5">
                    <div className="aspect-[16/10] bg-line-100" aria-hidden="true" />
                    <div className="mt-4 h-3 w-16 rounded bg-line-200" aria-hidden="true" />
                    <div className="mt-3 h-4 w-3/4 rounded bg-line-200" aria-hidden="true" />
                    <div className="mt-2 h-3 w-full rounded bg-line-100" aria-hidden="true" />
                  </div>
                ))}
          </div>
        </Container>
      </section>

      <CtaBand />
    </>
  );
}
