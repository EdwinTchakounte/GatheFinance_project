import type { Metadata } from "next";
import Image from "next/image";
import { getTranslations, setRequestLocale } from "next-intl/server";
import {
  Banknote,
  ShoppingCart,
  Sprout,
  Home as HomeIcon,
  User,
  ArrowLeftRight,
  PiggyBank,
  Wallet,
  Target,
  Users2,
  ShieldCheck,
  GraduationCap,
  MessageCircle,
  ArrowUpRight,
} from "lucide-react";

import { Container } from "@gathe/ui";
import { Link } from "@/i18n/navigation";
import { PageHeader } from "@/components/page-shell";
import { CtaBand } from "@/components/cta-band";
import { InstitutionalDecor } from "@/components/institutional-decor";
import { AnchorStrip } from "@/components/anchor-strip";
import { KeyFiguresBand } from "@/components/key-figures-band";
import { Reveal } from "@/components/reveal";
import { SectionHeading } from "@/components/section-heading";
import { images } from "@/lib/site-config";
import { pageAlternates } from "@/lib/seo";

type Params = { params: Promise<{ locale: string }> };

const rich = {
  strong: (c: React.ReactNode) => (
    <strong className="font-semibold text-ink-900">{c}</strong>
  ),
};

const ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
  consumption: ShoppingCart,
  micro: Sprout,
  realEstate: HomeIcon,
  personal: User,
  sendReceive: ArrowLeftRight,
  deposit: Wallet,
  accounts: PiggyBank,
  plans: Target,
  community: Users2,
  secured: ShieldCheck,
  workshops: GraduationCap,
  advice: MessageCircle,
};

const PILLARS = [
  {
    id: "credit",
    key: "credit",
    items: ["consumption", "micro", "realEstate", "personal"],
  },
  { id: "transferts", key: "transfers", items: ["sendReceive", "deposit"] },
  { id: "epargne", key: "savings", items: ["accounts", "plans"] },
  { id: "investissement", key: "investment", items: ["community", "secured"] },
  { id: "education", key: "education", items: ["workshops", "advice"] },
] as const;

const PILLAR_ICONS: Record<
  string,
  React.ComponentType<{ className?: string }>
> = {
  credit: Banknote,
  transfers: ArrowLeftRight,
  savings: PiggyBank,
  investment: Users2,
  education: GraduationCap,
};

const PILLAR_IMAGES: Record<string, { src: string; alt: string }> = {
  transfers: {
    src: images.cooperativeInvestment,
    alt: "Transfert d'argent entre membres de la coopérative",
  },
  savings: {
    src: images.fatherDaughterSaving,
    alt: "Père et fille déposant une épargne en pièces",
  },
  investment: {
    src: images.entrepreneurs,
    alt: "Entrepreneurs camerounais en cercle de discussion",
  },
  education: {
    src: images.trainingWorkshop,
    alt: "Atelier de formation à l'éducation financière",
  },
};

/** Pour les piliers sans photo (crédit) — image hero contextuelle. */
const PILLAR_FALLBACK_IMAGE: { src: string; alt: string } = {
  src: images.brcBusinessFormation,
  alt: "Conseil personnalisé en agence",
};

/** Accents gradient par pilier — chacun a sa signature couleur, brand-aligned. */
const PILLAR_ACCENT: Record<string, string> = {
  credit: "from-blue-700 to-blue-400",
  transfers: "from-terra-500 to-amber-400",
  savings: "from-emerald to-emerald-400",
  investment: "from-blue-700 to-emerald",
  education: "from-terra-500 to-emerald",
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


export async function generateMetadata({
  params,
}: Params): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "services" });
  return { title: t("title"), description: t("lead"), alternates: pageAlternates(locale, "/services-financiers") };
}


export default async function ServicesPage({ params }: Params) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations({ locale, namespace: "services" });
  const tn = await getTranslations({ locale, namespace: "nav" });

  const anchors = PILLARS.map((p) => ({
    id: p.id,
    label: t(`anchors.${p.key}`),
  }));

  return (
    <>
      <PageHeader
        eyebrow={t("eyebrow")}
        title={t("title")}
        lead={t("lead")}
        homeLabel={tn("home")}
        image={images.fcfaBills}
      />

      <AnchorStrip anchors={anchors} />

      {/* Intro éditoriale enrichie + chip strip des piliers */}
      <section className="relative isolate overflow-hidden bg-paper section-pad-sm">
        <MeshAccent variant="warm" />
        <InstitutionalDecor variant="weave" />
        <Container className="relative">
          <Reveal className="max-w-4xl">
            <p className="lead-with-cap text-lg leading-relaxed text-ink-600">
              {t.rich("intro2", rich)}
            </p>
          </Reveal>

          {/* Strip des 5 piliers en chips factuels — chaque chip pointe vers l'ancre */}
          <Reveal delay={120} className="mt-10 flex flex-wrap gap-2.5">
            {PILLARS.map((p, i) => {
              const Icon = PILLAR_ICONS[p.key]!;
              return (
                <a
                  key={p.id}
                  href={`#${p.id}`}
                  className="group inline-flex items-center gap-2 rounded-full border border-line-200 bg-paper px-3.5 py-1.5 text-[0.72rem] font-semibold uppercase tracking-[0.12em] text-ink-700 transition-all hover:-translate-y-0.5 hover:border-blue-200 hover:text-blue-700 hover:shadow-[0_8px_20px_-12px_rgba(14,77,146,0.4)]"
                >
                  <span className="font-mono text-[0.66rem] text-terra-600">
                    {String(i + 1).padStart(2, "0")}
                  </span>
                  <Icon
                    aria-hidden="true"
                    className="size-3.5 text-ink-500 transition-colors group-hover:text-blue-700"
                  />
                  {t(`anchors.${p.key}`)}
                </a>
              );
            })}
          </Reveal>
        </Container>
      </section>

      <KeyFiguresBand />

      {/* Piliers — chacun avec MeshAccent + watermark + SideRail + photo riche
          + items grid riche. Alternance bg paper / cream. */}
      {PILLARS.map((pillar, i) => {
        const PillarIcon = PILLAR_ICONS[pillar.key]!;
        const alt = i % 2 === 1;
        const photo = PILLAR_IMAGES[pillar.key] ?? PILLAR_FALLBACK_IMAGE;
        const photoOnRight = i % 2 === 1;
        const number = String(i + 1).padStart(2, "0");
        const accent = PILLAR_ACCENT[pillar.key]!;
        const meshVariant: "blue" | "warm" | "split" | "dense" =
          i === 0 ? "dense" : alt ? "warm" : "split";

        return (
          <section
            key={pillar.id}
            id={pillar.id}
            className={`relative isolate overflow-hidden section-pad scroll-mt-[8rem] ${
              alt
                ? "bg-gradient-to-b from-cream via-paper/40 to-cream"
                : "bg-paper"
            }`}
          >
            <MeshAccent variant={meshVariant} />
            <SideRail
              label={`${t(`anchors.${pillar.key}`)} · ${number}`}
              position={alt ? "right" : "left"}
            />
            <Container className="relative">
              <div className="relative grid items-center gap-12 lg:grid-cols-[1.05fr_0.95fr] lg:gap-20">
                {/* Watermark gros numéro */}
                <HeroNumeral
                  className={`absolute ${
                    photoOnRight
                      ? "-left-6 -top-16 lg:-left-12 lg:-top-24"
                      : "-right-6 -top-16 lg:-right-12 lg:-top-24"
                  }`}
                >
                  {number}
                </HeroNumeral>

                {/* Texte */}
                <div className={`relative ${photoOnRight ? "" : "lg:order-2"}`}>
                  <Reveal>
                    <span className="label-num">
                      {number} · {t(`anchors.${pillar.key}`)}
                    </span>
                    <div className="mt-5 flex items-start gap-4">
                      <span
                        aria-hidden="true"
                        className={`inline-flex size-14 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br ${accent} text-white shadow-[0_10px_30px_-10px_rgba(14,77,146,0.5)]`}
                      >
                        <PillarIcon className="size-6" />
                      </span>
                      <h2 className="font-editorial text-section font-medium leading-tight text-ink-900">
                        {t(`pillars.${pillar.key}.title`)}
                      </h2>
                    </div>
                    <p className="mt-6 max-w-none text-lg leading-relaxed text-ink-600">
                      {t.rich(`pillars.${pillar.key}.intro`, rich)}
                    </p>
                  </Reveal>
                </div>

                {/* Photo riche : cadre offset + halo + glass tag + count badge */}
                <Reveal
                  className={`relative ${photoOnRight ? "" : "lg:order-1"}`}
                >
                  {/* Halo */}
                  <div
                    aria-hidden="true"
                    className={`absolute -inset-6 rounded-3xl bg-gradient-to-tr ${accent} opacity-10 blur-2xl`}
                  />
                  {/* Cadre offset coloré */}
                  <div
                    aria-hidden="true"
                    className={`absolute -bottom-4 ${
                      photoOnRight ? "-right-4" : "-left-4"
                    } hidden h-full w-full rounded-md border-2 ${
                      pillar.key === "savings" || pillar.key === "education"
                        ? "border-emerald/30"
                        : "border-terra-500/30"
                    } lg:block`}
                  />
                  <div className="relative aspect-[4/3] overflow-hidden rounded-md shadow-[0_30px_60px_-20px_rgba(14,77,146,0.35)] ring-1 ring-line-200">
                    <Image
                      src={photo.src}
                      alt={photo.alt}
                      fill
                      sizes="(min-width: 1024px) 40vw, 90vw"
                      className="object-cover"
                    />
                    <div
                      aria-hidden="true"
                      className="absolute inset-0 bg-gradient-to-tr from-blue-950/50 via-blue-950/10 to-transparent"
                    />
                    {/* Tag flottant haut-gauche : pilier + numéro */}
                    <div className="absolute left-5 top-5 inline-flex items-center gap-2 rounded-full border border-white/20 bg-white/10 px-3.5 py-1.5 backdrop-blur-md">
                      <span
                        aria-hidden="true"
                        className="size-1.5 rounded-full bg-emerald shadow-[0_0_10px_rgba(58,170,53,0.7)]"
                      />
                      <span className="font-mono text-[0.68rem] font-medium uppercase tracking-[0.18em] text-white">
                        Pilier {number}
                      </span>
                    </div>
                  </div>

                  {/* Mini-card flottante : compteur d'items factuel */}
                  <Reveal
                    delay={250}
                    className={`absolute -bottom-6 ${
                      photoOnRight ? "-left-6" : "-right-6"
                    } hidden rounded-2xl bg-paper p-4 shadow-[0_20px_40px_-15px_rgba(14,77,146,0.3)] ring-1 ring-line-200 lg:block`}
                  >
                    <div className="flex items-center gap-3">
                      <span
                        className={`flex size-11 items-center justify-center rounded-xl bg-gradient-to-br ${accent} text-white`}
                        aria-hidden="true"
                      >
                        <PillarIcon className="size-5" />
                      </span>
                      <div>
                        <p className="font-editorial text-2xl font-medium leading-none text-ink-900">
                          {pillar.items.length}
                        </p>
                        <p className="mt-1 text-[0.65rem] font-semibold uppercase tracking-[0.16em] text-ink-500">
                          {pillar.items.length > 1 ? "produits" : "produit"}
                        </p>
                      </div>
                    </div>
                  </Reveal>
                </Reveal>
              </div>

              {/* Grille d'items éditoriaux enrichis */}
              <div className="mt-16 grid gap-5 sm:grid-cols-2">
                {pillar.items.map((item, j) => {
                  const Icon = ICONS[item] ?? Banknote;
                  return (
                    <ItemCard
                      key={item}
                      number={`${number}.${j + 1}`}
                      icon={<Icon className="size-5" />}
                      title={t(`pillars.${pillar.key}.items.${item}.title`)}
                      text={t(`pillars.${pillar.key}.items.${item}.text`)}
                      accent={accent}
                    />
                  );
                })}
              </div>
            </Container>
          </section>
        );
      })}

      {/* ===== Aller plus loin ===== */}
      <section className="relative isolate overflow-hidden bg-paper section-pad-sm">
        <Container>
          <Reveal className="mb-10 flex items-end justify-between gap-6">
            <div>
              <span className="label-num">Aller plus loin</span>
              <h2 className="mt-4 font-editorial text-[clamp(1.6rem,2.4vw,2rem)] font-medium text-ink-900">
                {tn("about")} · {tn("join")} · {tn("contact")}
              </h2>
            </div>
          </Reveal>
          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            <ExploreCard
              href="/a-propos"
              title={tn("about")}
              eyebrow="Histoire"
              image={images.brcTeamGroup}
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


function ItemCard({
  number,
  icon,
  title,
  text,
  accent,
}: {
  number: string;
  icon: React.ReactNode;
  title: string;
  text: string;
  accent: string;
}) {
  return (
    <article className="group relative isolate flex flex-col gap-4 overflow-hidden rounded-2xl bg-paper p-7 shadow-[0_2px_6px_rgba(14,29,58,0.05)] ring-1 ring-line-200 transition-all duration-300 hover:-translate-y-1 hover:shadow-[0_20px_40px_-15px_rgba(14,77,146,0.2)] hover:ring-blue-200 lg:p-8">
      {/* Top accent line gradient — toujours visible */}
      <span
        aria-hidden="true"
        className={`absolute inset-x-0 top-0 h-1 bg-gradient-to-r ${accent} opacity-95`}
      />
      {/* Halo radial au hover */}
      <div
        aria-hidden="true"
        className={`absolute -right-16 -top-16 size-44 rounded-full bg-gradient-to-br ${accent} opacity-0 blur-3xl transition-opacity duration-300 group-hover:opacity-20`}
      />
      <div className="relative flex items-center justify-between gap-4 pt-1">
        <span className="font-mono text-[0.72rem] font-semibold tracking-[0.14em] text-terra-600">
          {number}
        </span>
        <span
          aria-hidden="true"
          className={`flex size-10 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br ${accent} text-white shadow-[0_8px_20px_-8px_rgba(14,77,146,0.4)]`}
        >
          {icon}
        </span>
      </div>
      <h3 className="relative font-editorial text-xl font-medium leading-snug text-ink-900">
        {title}
      </h3>
      <p className="relative text-[0.95rem] leading-relaxed text-ink-600">
        {text}
      </p>
      {/* Hairline accent qui s'étire au hover */}
      <span
        aria-hidden="true"
        className={`relative mt-1 block h-px w-12 bg-gradient-to-r ${accent} transition-all duration-300 group-hover:w-24`}
      />
    </article>
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
