import type { Metadata } from "next";
import { pageAlternates, SITE_URL } from "@/lib/seo";
import { JsonLd, breadcrumbJsonLd } from "@/components/json-ld";
import { getTranslations, setRequestLocale } from "next-intl/server";
import { Info } from "lucide-react";

import { Container } from "@gathe/ui";
import { PageHeader } from "@/components/page-shell";
import { ContactForm } from "@/components/contact-form";
import { InstitutionalDecor } from "@/components/institutional-decor";
import { Reveal } from "@/components/reveal";
import { images } from "@/lib/site-config";

type Params = { params: Promise<{ locale: string }> };

export async function generateMetadata({ params }: Params): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "membership" });
  return { title: t("title"), description: t("lead"), alternates: pageAlternates(locale, "/devenir-membre") };
}

const VALUES = ["accessibility", "transparency", "community", "local"] as const;

export default async function MembershipPage({ params }: Params) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations({ locale, namespace: "membership" });
  const th = await getTranslations({ locale, namespace: "home" });
  const tn = await getTranslations({ locale, namespace: "nav" });
  const tf = await getTranslations({ locale, namespace: "form" });

  return (
    <>
      <JsonLd
        data={breadcrumbJsonLd(SITE_URL, [
          { name: tn("home"), path: "/" },
          { name: t("title"), path: "/devenir-membre" },
        ])}
      />
      <PageHeader
        eyebrow={t("eyebrow")}
        title={t("title")}
        lead={t("lead")}
        homeLabel={tn("home")}
        image={images.brcBusinessFormation}
      />

      {/* ===== Why join — values grid ===== */}
      <section className="relative isolate overflow-hidden section-pad bg-paper">
        <InstitutionalDecor variant="flow" />
        <Container className="relative">
          <div className="max-w-3xl">
            <span className="label-num">01 · {t("whyTitle")}</span>
            <h2 className="mt-4 font-editorial text-section font-medium text-ink-900">
              {t("whyTitle")}
            </h2>
          </div>

          <div className="mt-12 grid gap-px bg-line-200 sm:grid-cols-2 lg:grid-cols-4">
            {VALUES.map((v, i) => (
              <Reveal
                as="div"
                key={v}
                delay={i * 70}
                className="flex flex-col bg-paper p-7 transition-colors hover:bg-cream lg:p-9"
              >
                <span className="font-display text-[0.72rem] font-medium tracking-[0.12em] text-terra-600">
                  {`0${i + 1}`}
                </span>
                <h3 className="mt-3 font-editorial text-xl font-medium leading-snug text-ink-900">
                  {th(`values.items.${v}.title`)}
                </h3>
                <p className="mt-3 text-sm leading-relaxed text-ink-600">
                  {th(`values.items.${v}.text`)}
                </p>
              </Reveal>
            ))}
          </div>

          {/* Key figures — strip */}
          <dl className="mt-12 grid grid-cols-1 gap-10 pt-2 sm:grid-cols-2">
            <div>
              <dt className="stat-label">{th("stats.projectsLabel")}</dt>
              <dd className="stat-num mt-2 text-[clamp(2.25rem,3.4vw,3rem)]">{th("stats.projectsValue")}</dd>
            </div>
            <div className="sm:border-l sm:border-line-200 sm:pl-10">
              <dt className="stat-label">{th("stats.fundedLabel")}</dt>
              <dd className="stat-num mt-2 text-[clamp(2.25rem,3.4vw,3rem)]">
                {th("stats.fundedValue")}{" "}
                <span className="text-emerald">{th("stats.fundedSuffix")}</span>
              </dd>
            </div>
          </dl>
        </Container>
      </section>

      {/* ===== Membership form ===== */}
      <section id="formulaire" className="section-pad bg-cream scroll-mt-[8rem]">
        <Container>
          <div className="mx-auto max-w-2xl">
            <div className="text-center">
              <span className="label-num inline-flex">02 · {t("formTitle")}</span>
              <h2 className="mt-4 font-editorial text-section font-medium text-ink-900">
                {t("formTitle")}
              </h2>
            </div>
            <div className="mt-6 flex items-start gap-3 border-l-2 border-terra-500 bg-paper px-5 py-3.5 text-sm text-ink-700">
              <Info aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-terra-600" />
              <p>{t("afterNote")}</p>
            </div>
            <div className="mt-8 rounded-[1.5rem] bg-paper p-7 shadow-[0_1px_2px_rgba(14,29,58,0.04),0_12px_28px_-20px_rgba(14,29,58,0.16)] ring-1 ring-line-200/60 sm:p-9">
              <ContactForm endpoint="adhesion" submitLabel={tf("submit")} />
            </div>
          </div>
        </Container>
      </section>
    </>
  );
}
