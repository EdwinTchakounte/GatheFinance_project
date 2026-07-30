import type { Metadata } from "next";
import Image from "next/image";
import { getTranslations, setRequestLocale } from "next-intl/server";
import {
  MapPin,
  Phone,
  Mail,
  Clock,
  ArrowUpRight,
  Quote,
  Banknote,
  Sparkles,
  HandHeart,
} from "lucide-react";

import { buttonClasses, Container } from "@gathe/ui";
import { Link } from "@/i18n/navigation";
import { PageHeader } from "@/components/page-shell";
import { CtaBand } from "@/components/cta-band";
import { Reveal } from "@/components/reveal";
import { AnchorStrip } from "@/components/anchor-strip";
import { SectionHeading } from "@/components/section-heading";
import { KeyFiguresBand } from "@/components/key-figures-band";
import { images, siteConfig } from "@/lib/site-config";
import { pageAlternates } from "@/lib/seo";

type Params = { params: Promise<{ locale: string }> };

export async function generateMetadata({ params }: Params): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "about" });
  return { title: t("title"), description: t("lead"), alternates: pageAlternates(locale, "/a-propos") };
}

const rich = {
  strong: (chunks: React.ReactNode) => (
    <strong className="font-semibold text-ink-900">{chunks}</strong>
  ),
};

/** Emphase pour les panneaux sombres (navy) : le noir y est illisible → blanc
 *  souligné d'un accent émeraude. */
const richOnDark = {
  strong: (chunks: React.ReactNode) => (
    <strong className="font-semibold text-white underline decoration-emerald/70 decoration-2 underline-offset-[6px]">
      {chunks}
    </strong>
  ),
};

function MeshAccent({
  variant = "blue",
}: {
  variant?: "blue" | "warm" | "split" | "dense";
}) {
  const styles: Record<string, React.CSSProperties> = {
    blue: {
      backgroundImage: [
        "radial-gradient(60% 50% at 20% 10%, rgba(14,77,146,0.10), transparent 70%)",
        "radial-gradient(50% 50% at 85% 30%, rgba(58,170,53,0.07), transparent 70%)",
        "radial-gradient(45% 45% at 60% 95%, rgba(194,116,42,0.08), transparent 70%)",
      ].join(", "),
    },
    warm: {
      backgroundImage: [
        "radial-gradient(55% 50% at 10% 100%, rgba(194,116,42,0.12), transparent 70%)",
        "radial-gradient(50% 40% at 85% 0%, rgba(14,77,146,0.09), transparent 70%)",
      ].join(", "),
    },
    split: {
      backgroundImage: [
        "radial-gradient(60% 55% at 0% 50%, rgba(14,77,146,0.10), transparent 70%)",
        "radial-gradient(55% 50% at 100% 50%, rgba(194,116,42,0.10), transparent 70%)",
        "radial-gradient(40% 40% at 50% 100%, rgba(58,170,53,0.06), transparent 70%)",
      ].join(", "),
    },
    dense: {
      backgroundImage: [
        "radial-gradient(50% 45% at 15% 15%, rgba(14,77,146,0.14), transparent 65%)",
        "radial-gradient(45% 40% at 85% 20%, rgba(194,116,42,0.12), transparent 65%)",
        "radial-gradient(45% 40% at 50% 95%, rgba(58,170,53,0.10), transparent 65%)",
        "radial-gradient(35% 35% at 90% 85%, rgba(14,77,146,0.10), transparent 65%)",
      ].join(", "),
    },
  };
  return (
    <div
      aria-hidden="true"
      className="pointer-events-none absolute inset-0 -z-10"
      style={styles[variant]}
    />
  );
}

function HeroNumeral({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <span
      aria-hidden="true"
      className={`pointer-events-none select-none font-editorial text-[10rem] font-medium leading-none text-blue-950/[0.06] sm:text-[14rem] lg:text-[18rem] ${className ?? ""}`}
    >
      {children}
    </span>
  );
}

/** Side rail décoratif vertical avec hairlines + label mono — comble la
 *  gauche/droite des sections en signature institutionnelle. */
function SideRail({
  label,
  position = "left",
}: {
  label: string;
  position?: "left" | "right";
}) {
  return (
    <div
      aria-hidden="true"
      className={`pointer-events-none absolute top-32 hidden ${
        position === "left" ? "left-6" : "right-6"
      } z-0 flex-col items-center gap-3 lg:flex`}
    >
      <span className="h-12 w-px bg-gradient-to-b from-transparent via-line-200 to-line-200" />
      <span className="rotate-[-90deg] whitespace-nowrap font-mono text-[0.65rem] font-medium uppercase tracking-[0.24em] text-ink-400">
        {label}
      </span>
      <span className="h-12 w-px bg-gradient-to-t from-transparent via-line-200 to-line-200" />
    </div>
  );
}

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
      <section
        id="mission"
        className="relative isolate overflow-hidden bg-paper section-pad"
      >
        <MeshAccent variant="dense" />
        <SideRail label="Mission · 2025" position="left" />
        <Container className="relative">
          <div className="relative grid items-center gap-12 lg:grid-cols-[1.05fr_0.95fr] lg:gap-20">
            <HeroNumeral className="absolute -left-6 -top-16 lg:-left-12 lg:-top-24">
              01
            </HeroNumeral>

            <div className="relative">
              <SectionHeading
                number="01"
                eyebrow={t("missionTitle")}
                title={t("missionTitle")}
              />
              <p className="lead-with-cap mt-7 max-w-2xl text-lg leading-relaxed text-ink-600">
                {t.rich("intro", rich)}
              </p>

              {/* Mini-band de signatures factuelles sous le lead */}
              <div className="mt-9 flex flex-wrap gap-3">
                <SignatureChip
                  icon={<MapPin className="size-3.5" />}
                  label="Akwa · Douala"
                />
                <SignatureChip
                  icon={<Sparkles className="size-3.5" />}
                  label="Auto-financement solidaire"
                  accent
                />
                <SignatureChip
                  icon={<HandHeart className="size-3.5" />}
                  label="Coopérative de membres"
                />
              </div>
            </div>

            <Reveal className="relative">
              <div
                aria-hidden="true"
                className="absolute -inset-6 rounded-3xl bg-gradient-to-tr from-blue-100 via-paper to-terra-100 blur-2xl"
              />
              <div
                aria-hidden="true"
                className="absolute -bottom-4 -right-4 hidden h-full w-full rounded-md border-2 border-terra-500/40 lg:block"
              />
              <div className="relative aspect-[4/4.4] overflow-hidden rounded-md shadow-[0_30px_60px_-20px_rgba(14,77,146,0.35)] ring-1 ring-line-200">
                <Image
                  src={images.entrepreneurFamily}
                  alt="Entrepreneurs camerounais accompagnés par la coopérative"
                  fill
                  sizes="(min-width: 1024px) 40vw, 90vw"
                  className="object-cover"
                />
                <div
                  aria-hidden="true"
                  className="absolute inset-0 bg-gradient-to-t from-blue-950/55 via-blue-950/10 to-transparent"
                />
                <div className="absolute bottom-5 left-5 inline-flex items-center gap-2 rounded-full border border-white/20 bg-white/10 px-3.5 py-1.5 backdrop-blur-md">
                  <span
                    aria-hidden="true"
                    className="size-1.5 rounded-full bg-emerald shadow-[0_0_10px_rgba(58,170,53,0.7)]"
                  />
                  <span className="font-mono text-[0.68rem] font-medium uppercase tracking-[0.18em] text-white">
                    Akwa · Douala
                  </span>
                </div>
              </div>

              {/* Mini-card supporting flottante en bas droite de la photo */}
              <Reveal
                delay={250}
                className="absolute -bottom-6 -right-6 hidden max-w-[14rem] rounded-2xl bg-paper p-4 shadow-[0_20px_40px_-15px_rgba(14,77,146,0.3)] ring-1 ring-line-200 lg:block"
              >
                <div className="flex items-center gap-3">
                  <span
                    className="flex size-9 items-center justify-center rounded-lg bg-gradient-to-br from-emerald to-emerald-400 text-white"
                    aria-hidden="true"
                  >
                    <Banknote className="size-4" />
                  </span>
                  <div>
                    <p className="font-mono text-[0.62rem] font-semibold uppercase tracking-[0.14em] text-terra-600">
                      Règlement Intérieur
                    </p>
                    <p className="mt-0.5 text-[0.75rem] font-medium text-ink-800">
                      Tous les barèmes en clair
                    </p>
                  </div>
                </div>
              </Reveal>
            </Reveal>
          </div>

          {/* Objectifs — 3-col grid avec accent + halo hover */}
          <div className="mt-20 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {objectives.map((item, i) => (
              <Reveal
                key={i}
                delay={i * 60}
                className="group relative isolate overflow-hidden rounded-[1.5rem] bg-paper p-8 shadow-[0_1px_2px_rgba(14,29,58,0.04),0_12px_28px_-20px_rgba(14,29,58,0.16)] ring-1 ring-line-200/60 transition-all duration-500 hover:-translate-y-1 hover:shadow-[0_24px_48px_-24px_rgba(14,77,146,0.2)] hover:ring-line-200"
              >
                <div
                  aria-hidden="true"
                  className="absolute -right-12 -top-12 size-32 rounded-full bg-gradient-to-br from-blue-100 via-paper to-terra-100 opacity-0 blur-2xl transition-opacity duration-300 group-hover:opacity-100"
                />
                <div className="relative flex items-start justify-between gap-4">
                  <span className="font-mono text-[0.72rem] font-semibold tracking-[0.14em] text-terra-600">
                    {String(i + 1).padStart(2, "0")}
                  </span>
                  <span
                    aria-hidden="true"
                    className="size-2 rounded-full bg-gradient-to-br from-terra-500 to-emerald shadow-[0_0_8px_rgba(58,170,53,0.4)]"
                  />
                </div>
                <span
                  aria-hidden="true"
                  className="relative mt-5 block h-px w-12 bg-gradient-to-r from-terra-500 via-emerald to-blue-700 transition-all duration-300 group-hover:w-20"
                />
                <p className="relative mt-5 text-[0.98rem] leading-relaxed text-ink-700">
                  {item}
                </p>
              </Reveal>
            ))}
          </div>

          {/* Callout panel navy dramatique */}
          <Reveal className="relative mt-20 overflow-hidden rounded-3xl bg-gradient-to-br from-blue-950 via-blue-900 to-blue-700 p-10 text-white shadow-[0_30px_60px_-20px_rgba(14,77,146,0.45)] sm:p-14">
            <div
              aria-hidden="true"
              className="absolute -bottom-20 -right-20 size-80 rounded-full bg-emerald/20 blur-3xl"
            />
            <div
              aria-hidden="true"
              className="absolute -left-20 -top-20 size-80 rounded-full bg-terra-500/15 blur-3xl"
            />
            <Quote
              aria-hidden="true"
              className="absolute right-6 top-6 size-28 text-white/[0.08]"
            />
            <div className="relative max-w-3xl">
              <span className="inline-block font-mono text-[0.72rem] font-semibold uppercase tracking-[0.18em] text-emerald">
                Notre conviction
              </span>
              <p className="mt-5 font-editorial text-2xl italic leading-[1.4] text-white sm:text-[1.7rem]">
                {t.rich("callout", richOnDark)}
              </p>
            </div>
          </Reveal>
        </Container>
      </section>

      {/* ===== KeyFigures — 4 chiffres règlement, déjà éditorial premium ===== */}
      <KeyFiguresBand />

      {/* ===== Team — mosaïque de photos + texte + side rail ===== */}
      <section
        id="equipe"
        className="relative isolate overflow-hidden bg-gradient-to-b from-paper to-cream/40 section-pad"
      >
        <MeshAccent variant="split" />
        <SideRail label="Équipe · Accompagnement" position="right" />
        <Container className="relative">
          <div className="grid items-center gap-12 lg:grid-cols-[1.05fr_0.95fr] lg:gap-20">
            <div className="relative">
              <HeroNumeral className="absolute -left-6 -top-16 lg:-left-12 lg:-top-24">
                02
              </HeroNumeral>
              <SectionHeading
                number="02"
                eyebrow={tn("aboutTeam")}
                title={t("teamTitle")}
                lead={t("teamText")}
              />
              <Link
                href="/contact"
                className={`${buttonClasses({ variant: "primary" })} mt-8 inline-flex items-center gap-2`}
              >
                {tn("contact")}
                <ArrowUpRight aria-hidden="true" className="size-4" />
              </Link>
            </div>

            {/* Mosaïque 3-photos : 1 grande + 2 petites empilées */}
            <Reveal className="relative">
              <div
                aria-hidden="true"
                className="absolute -inset-8 rounded-3xl bg-gradient-to-br from-blue-100 via-paper to-emerald/15 blur-2xl"
              />
              <div className="relative grid grid-cols-5 grid-rows-2 gap-3">
                <div className="relative col-span-3 row-span-2 aspect-[4/5] overflow-hidden rounded-md shadow-[0_30px_60px_-20px_rgba(14,77,146,0.35)] ring-1 ring-line-200">
                  <Image
                    src={images.brcTeamSupport}
                    alt="Conseillers en entretien d'accompagnement"
                    fill
                    sizes="(min-width: 1024px) 28vw, 60vw"
                    className="object-cover"
                  />
                  <div
                    aria-hidden="true"
                    className="absolute inset-0 bg-gradient-to-t from-blue-950/55 via-transparent to-transparent"
                  />
                </div>
                <div className="relative col-span-2 row-span-1 aspect-[4/3] overflow-hidden rounded-md shadow-md ring-1 ring-line-200">
                  <Image
                    src={images.brcFormFilling}
                    alt="Constitution de dossier coopérative"
                    fill
                    sizes="(min-width: 1024px) 18vw, 38vw"
                    className="object-cover"
                  />
                </div>
                <div className="relative col-span-2 row-span-1 aspect-[4/3] overflow-hidden rounded-md shadow-md ring-1 ring-line-200">
                  <Image
                    src={images.brcCompletion}
                    alt="Dossier finalisé chez la coopérative"
                    fill
                    sizes="(min-width: 1024px) 18vw, 38vw"
                    className="object-cover"
                  />
                </div>
              </div>
            </Reveal>
          </div>
        </Container>
      </section>

      {/* ===== Agences ===== */}
      <section
        id="agences"
        className="relative isolate overflow-hidden bg-gradient-to-br from-cream via-paper to-cream section-pad"
      >
        <MeshAccent variant="warm" />
        <SideRail label="Siège · Akwa" position="left" />
        <Container className="relative">
          <div className="relative">
            <HeroNumeral className="absolute -left-6 -top-16 lg:-left-12 lg:-top-24">
              03
            </HeroNumeral>
            <SectionHeading
              number="03"
              eyebrow={t("agenciesTitle")}
              title={t("agenciesTitle")}
              lead={t("agenciesIntro")}
            />
          </div>

          {/* Grid : 4 contact cards riches */}
          <div className="mt-12 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
            <ContactCard
              icon={<MapPin className="size-5" />}
              label={t("agencyAddress")}
              accent="from-terra-500 to-amber-400"
            >
              {siteConfig.contact.address}
            </ContactCard>
            <ContactCard
              icon={<Phone className="size-5" />}
              label={t("agencyPhone")}
              accent="from-blue-700 to-blue-400"
            >
              <a
                href={siteConfig.contact.phoneHref}
                className="hover:text-blue-700"
              >
                {siteConfig.contact.phone}
              </a>
            </ContactCard>
            <ContactCard
              icon={<Mail className="size-5" />}
              label={t("agencyEmail")}
              accent="from-emerald to-emerald-400"
            >
              <a
                href={siteConfig.contact.emailHref}
                className="hover:text-blue-700"
              >
                {siteConfig.contact.email}
              </a>
            </ContactCard>
            <ContactCard
              icon={<Clock className="size-5" />}
              label={t("agencyHours")}
              accent="from-terra-500 to-emerald"
            >
              {siteConfig.contact.openingHours}
            </ContactCard>
          </div>
        </Container>
      </section>

      {/* ===== Explorer aussi — 3 liens vers les autres pages vitrine ===== */}
      <section className="relative isolate overflow-hidden bg-paper section-pad-sm">
        <Container>
          <Reveal className="mb-10 flex items-end justify-between gap-6">
            <div>
              <span className="label-num">Aller plus loin</span>
              <h2 className="mt-4 font-editorial text-[clamp(1.6rem,2.4vw,2rem)] font-medium text-ink-900">
                {tn("home")} · {tn("services")} · {tn("join")}
              </h2>
            </div>
          </Reveal>
          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            <ExploreCard
              href="/services-financiers"
              title={tn("services")}
              eyebrow="Produits"
              image={images.fcfaBills}
              accent="from-blue-700/85 to-blue-950/90"
            />
            <ExploreCard
              href="/devenir-membre"
              title={tn("join")}
              eyebrow="Adhésion"
              image={images.brcBusinessFormation}
              accent="from-terra-500/85 to-blue-950/90"
            />
            <ExploreCard
              href="/contact"
              title={tn("contact")}
              eyebrow="Échange"
              image={images.onlineSupport}
              accent="from-emerald/85 to-blue-950/90"
            />
          </div>
        </Container>
      </section>

      <CtaBand />
    </>
  );
}


function SignatureChip({
  icon,
  label,
  accent = false,
}: {
  icon: React.ReactNode;
  label: string;
  accent?: boolean;
}) {
  return (
    <span
      className={`inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-[0.72rem] font-semibold uppercase tracking-[0.12em] ${
        accent
          ? "border-transparent bg-gradient-to-br from-terra-500/15 to-emerald/15 text-ink-900 shadow-[inset_0_0_0_1px_rgba(194,116,42,0.25)]"
          : "border-line-200 bg-paper text-ink-600"
      }`}
    >
      <span
        aria-hidden="true"
        className={accent ? "text-terra-600" : "text-ink-500"}
      >
        {icon}
      </span>
      {label}
    </span>
  );
}


function ContactCard({
  icon,
  label,
  accent,
  children,
}: {
  icon: React.ReactNode;
  label: string;
  accent: string;
  children: React.ReactNode;
}) {
  return (
    <div className="group relative isolate overflow-hidden rounded-[1.5rem] bg-paper p-7 shadow-[0_1px_2px_rgba(14,29,58,0.04),0_12px_28px_-20px_rgba(14,29,58,0.18)] ring-1 ring-line-200/60 transition-all duration-500 hover:-translate-y-1 hover:shadow-[0_24px_48px_-24px_rgba(14,77,146,0.22)] hover:ring-line-200">
      {/* Halo diffus au hover — plus doux qu'une barre supérieure tranchée */}
      <div
        aria-hidden="true"
        className={`absolute -right-12 -top-12 size-36 rounded-full bg-gradient-to-br ${accent} opacity-0 blur-3xl transition-opacity duration-500 group-hover:opacity-[0.12]`}
      />
      <div
        className={`relative flex size-12 items-center justify-center rounded-2xl bg-gradient-to-br ${accent} text-white shadow-[0_10px_24px_-12px_rgba(14,77,146,0.45)]`}
        aria-hidden="true"
      >
        {icon}
      </div>
      <p className="relative mt-5 text-[0.7rem] font-semibold uppercase tracking-[0.18em] text-ink-500">
        {label}
      </p>
      <div className="relative mt-2 text-sm leading-relaxed text-ink-700">
        {children}
      </div>
    </div>
  );
}


function ExploreCard({
  href,
  title,
  eyebrow,
  image,
  accent,
}: {
  href: string;
  title: string;
  eyebrow: string;
  image: string;
  accent: string;
}) {
  return (
    <Link
      href={href}
      className="group relative isolate block aspect-[4/3] overflow-hidden rounded-2xl shadow-[0_8px_24px_-12px_rgba(14,77,146,0.3)] ring-1 ring-line-200 transition-all duration-300 hover:-translate-y-1 hover:shadow-[0_30px_60px_-20px_rgba(14,77,146,0.45)]"
    >
      <Image
        src={image}
        alt=""
        fill
        sizes="(min-width: 1024px) 32vw, 90vw"
        className="object-cover transition-transform duration-700 group-hover:scale-105"
      />
      <div
        aria-hidden="true"
        className={`absolute inset-0 bg-gradient-to-tr ${accent}`}
      />
      <div className="absolute inset-0 flex flex-col justify-end p-6">
        <span className="inline-block w-fit rounded-full border border-white/20 bg-white/10 px-3 py-1 font-mono text-[0.65rem] font-semibold uppercase tracking-[0.18em] text-white backdrop-blur-md">
          {eyebrow}
        </span>
        <div className="mt-3 flex items-end justify-between gap-3">
          <h3 className="font-editorial text-2xl font-medium leading-tight text-white">
            {title}
          </h3>
          <span
            aria-hidden="true"
            className="flex size-10 shrink-0 items-center justify-center rounded-full bg-white/15 text-white backdrop-blur-md transition-transform duration-300 group-hover:translate-x-1"
          >
            <ArrowUpRight className="size-5" />
          </span>
        </div>
      </div>
    </Link>
  );
}
