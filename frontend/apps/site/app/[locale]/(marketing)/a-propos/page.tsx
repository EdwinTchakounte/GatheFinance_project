import type { Metadata } from "next";
import Image from "next/image";
import { getTranslations, setRequestLocale } from "next-intl/server";
import { MapPin, Phone, Mail, Clock } from "lucide-react";

import { buttonClasses, Container } from "@gathe/ui";
import { Link } from "@/i18n/navigation";
import { PageHeader } from "@/components/page-shell";
import { CtaBand } from "@/components/cta-band";
import { InstitutionalDecor } from "@/components/institutional-decor";
import { Reveal } from "@/components/reveal";
import { AnchorStrip } from "@/components/anchor-strip";
import { images, siteConfig } from "@/lib/site-config";

type Params = { params: Promise<{ locale: string }> };

export async function generateMetadata({ params }: Params): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "about" });
  return { title: t("title"), description: t("lead") };
}

const rich = {
  strong: (chunks: React.ReactNode) => <strong className="text-ink-900">{chunks}</strong>,
};

export default async function AboutPage({ params }: Params) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations({ locale, namespace: "about" });
  const th = await getTranslations({ locale, namespace: "home" });
  const tn = await getTranslations({ locale, namespace: "nav" });
  const objectives = t.raw("objectives") as string[];

  return (
    <>
      <PageHeader
        eyebrow={t("eyebrow")}
        title={t("title")}
        lead={t("lead")}
        homeLabel={tn("home")}
        image={images.brcTeamGroup}
      />

      <AnchorStrip
        anchors={[
          { id: "mission", label: t("missionTitle") },
          { id: "equipe", label: tn("aboutTeam") },
          { id: "agences", label: t("agenciesTitle") },
        ]}
      />

      {/* ===== Mission ===== */}
      <section id="mission" className="relative isolate overflow-hidden section-pad bg-paper">
        <InstitutionalDecor variant="nodes" />
        <Container className="relative">
          <div className="grid items-start gap-12 lg:grid-cols-[1fr_0.82fr] lg:gap-20">
            <div>
              <span className="label-num">01 · {t("missionTitle")}</span>
              <h2 className="mt-4 font-editorial text-section font-medium text-ink-900">
                {t("missionTitle")}
              </h2>
              <p className="lead-with-cap mt-6 max-w-2xl text-lg leading-relaxed text-ink-600">
                {t.rich("intro", rich)}
              </p>

              <ul className="mt-9 space-y-4 border-l border-line-200 pl-6">
                {objectives.map((item, i) => (
                  <Reveal as="li" key={i} delay={i * 60} className="relative">
                    <span aria-hidden="true" className="absolute -left-[27px] top-2 size-1.5 rounded-full bg-terra-500" />
                    <p className="text-[0.98rem] leading-relaxed text-ink-700">
                      {item}
                    </p>
                  </Reveal>
                ))}
              </ul>

              <div className="mt-9 border-l-2 border-terra-500 bg-cream px-6 py-5">
                <p className="font-editorial italic text-[1.05rem] leading-relaxed text-ink-800">
                  {t.rich("callout", rich)}
                </p>
              </div>
            </div>

            <Reveal className="space-y-5">
              <div className="relative aspect-[4/3] overflow-hidden rounded-md">
                <Image
                  src={images.family}
                  alt="Famille d'entrepreneurs camerounais"
                  fill
                  sizes="(min-width: 1024px) 40vw, 90vw"
                  className="object-cover"
                />
              </div>

            </Reveal>
          </div>
        </Container>
      </section>

      {/* ===== Key figures ===== */}
      <section className="border-y border-line-200 bg-cream py-12 lg:py-16">
        <Container>
          <dl className="grid grid-cols-1 gap-10 sm:grid-cols-2">
            <div>
              <dt className="stat-label">{th("stats.projectsLabel")}</dt>
              <dd className="stat-num mt-2 text-[clamp(2rem,3.4vw,3rem)]">{th("stats.projectsValue")}</dd>
            </div>
            <div className="sm:border-l sm:border-line-200 sm:pl-10">
              <dt className="stat-label">{th("stats.fundedLabel")}</dt>
              <dd className="stat-num mt-2 text-[clamp(2rem,3.4vw,3rem)]">
                {th("stats.fundedValue")}{" "}
                <span className="text-emerald">{th("stats.fundedSuffix")}</span>
              </dd>
            </div>
          </dl>
        </Container>
      </section>

      {/* ===== Team ===== */}
      <section id="equipe" className="section-pad bg-paper">
        <Container>
          <div className="grid items-start gap-12 lg:grid-cols-[1fr_1fr]">
            <div>
              <span className="label-num">02 · {tn("aboutTeam")}</span>
              <h2 className="mt-4 font-editorial text-section font-medium text-ink-900">
                {t("teamTitle")}
              </h2>
              <p className="mt-6 max-w-2xl text-lg leading-relaxed text-ink-600">{t("teamText")}</p>
              <Link href="/contact" className={`${buttonClasses({ variant: "secondary" })} mt-7`}>
                {tn("contact")}
              </Link>
            </div>
            <Reveal className="relative aspect-[4/3] overflow-hidden rounded-md">
              <Image
                src={images.entrepreneurFamily}
                alt="Entrepreneurs camerounais accompagnés par la coopérative"
                fill
                sizes="(min-width: 1024px) 45vw, 90vw"
                className="object-cover"
              />
            </Reveal>
          </div>
        </Container>
      </section>

      {/* ===== Branches / head office ===== */}
      <section id="agences" className="section-pad bg-cream">
        <Container>
          <div className="max-w-3xl">
            <span className="label-num">03 · {t("agenciesTitle")}</span>
            <h2 className="mt-4 font-editorial text-section font-medium text-ink-900">
              {t("agenciesTitle")}
            </h2>
            <p className="mt-6 text-lg leading-relaxed text-ink-600">{t("agenciesIntro")}</p>
          </div>
          <div className="mt-10 grid gap-px bg-line-200 sm:grid-cols-2 lg:grid-cols-4">
            <Detail icon={<MapPin className="size-4" />}>{siteConfig.contact.address}</Detail>
            <Detail icon={<Phone className="size-4" />}>
              <a href={siteConfig.contact.phoneHref} className="hover:text-blue-700">
                {siteConfig.contact.phone}
              </a>
            </Detail>
            <Detail icon={<Mail className="size-4" />}>
              <a href={siteConfig.contact.emailHref} className="hover:text-blue-700">
                {siteConfig.contact.email}
              </a>
            </Detail>
            <Detail icon={<Clock className="size-4" />}>{siteConfig.contact.openingHours}</Detail>
          </div>
        </Container>
      </section>

      <CtaBand />
    </>
  );
}

function Detail({ icon, children }: { icon: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="flex items-start gap-3 bg-cream p-6 transition-colors hover:bg-paper">
      <span aria-hidden="true" className="mt-0.5 shrink-0 text-terra-600">
        {icon}
      </span>
      <span className="text-sm leading-relaxed text-ink-700">{children}</span>
    </div>
  );
}
