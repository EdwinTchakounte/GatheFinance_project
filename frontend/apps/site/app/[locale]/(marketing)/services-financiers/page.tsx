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
} from "lucide-react";

import { Container } from "@gathe/ui";
import { PageHeader } from "@/components/page-shell";
import { CtaBand } from "@/components/cta-band";
import { InstitutionalDecor } from "@/components/institutional-decor";
import { AnchorStrip } from "@/components/anchor-strip";
import { KeyFiguresBand } from "@/components/key-figures-band";
import { images } from "@/lib/site-config";

type Params = { params: Promise<{ locale: string }> };

const rich = { strong: (c: React.ReactNode) => <strong className="text-ink-900">{c}</strong> };

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
  { id: "credit", key: "credit", items: ["consumption", "micro", "realEstate", "personal"] },
  { id: "transferts", key: "transfers", items: ["sendReceive", "deposit"] },
  { id: "epargne", key: "savings", items: ["accounts", "plans"] },
  { id: "investissement", key: "investment", items: ["community", "secured"] },
  { id: "education", key: "education", items: ["workshops", "advice"] },
] as const;

const PILLAR_ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
  credit: Banknote,
  transfers: ArrowLeftRight,
  savings: PiggyBank,
  investment: Users2,
  education: GraduationCap,
};

// Photo accompagnant chaque pilier (hors crédit, déjà servi par l'image
// hero). Toutes ces images sont déjà au catalogue (site-config.ts), aucun
// nouvel asset n'est introduit. Layout alterné droite/gauche en fonction
// de la parité, façon storytelling éditorial press.
const PILLAR_IMAGES: Record<string, { src: string; alt: string }> = {
  transfers: { src: images.cooperativeInvestment, alt: "Transfert d'argent entre membres de la coopérative" },
  savings: { src: images.fatherDaughterSaving, alt: "Père et fille déposant une épargne en pièces" },
  investment: { src: images.entrepreneurs, alt: "Entrepreneurs camerounais en cercle de discussion" },
  education: { src: images.trainingWorkshop, alt: "Atelier de formation à l'éducation financière" },
};

export async function generateMetadata({ params }: Params): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "services" });
  return { title: t("title"), description: t("lead") };
}

export default async function ServicesPage({ params }: Params) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations({ locale, namespace: "services" });
  const tn = await getTranslations({ locale, namespace: "nav" });

  const anchors = PILLARS.map((p) => ({ id: p.id, label: t(`anchors.${p.key}`) }));

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

      {/* Intro éditorial avec lettrine */}
      <section className="relative isolate overflow-hidden bg-paper section-pad-sm">
        <InstitutionalDecor variant="weave" />
        <Container className="relative">
          <p className="lead-with-cap max-w-4xl text-lg leading-relaxed text-ink-600">
            {t.rich("intro2", rich)}
          </p>
        </Container>
      </section>

      <KeyFiguresBand />

      {/* Piliers — layout asymétrique éditorial : photo alternée droite/gauche
          sur tous sauf le 1er (crédit), dont l'image vit déjà dans le hero. */}
      {PILLARS.map((pillar, i) => {
        const PillarIcon = PILLAR_ICONS[pillar.key]!;
        const alt = i % 2 === 1;
        const photo = PILLAR_IMAGES[pillar.key];
        const photoOnRight = i % 2 === 1; // 1 (transferts) right, 2 (epargne) left…
        return (
          <section
            key={pillar.id}
            id={pillar.id}
            className={`section-pad scroll-mt-[8rem] ${alt ? "bg-cream" : "bg-paper"}`}
          >
            <Container>
              {photo ? (
                <div
                  className={`grid items-start gap-10 lg:gap-16 lg:grid-cols-[1.05fr_0.85fr]`}
                >
                  {/* Texte */}
                  <div className={photoOnRight ? "" : "lg:order-2"}>
                    <span className="label-num">
                      {`0${i + 1}`} · {t(`anchors.${pillar.key}`)}
                    </span>
                    <div className="mt-4 flex items-start gap-5">
                      <span
                        aria-hidden="true"
                        className="inline-flex size-12 shrink-0 items-center justify-center rounded-md border border-line-200 bg-paper text-blue-700"
                      >
                        <PillarIcon className="size-5" />
                      </span>
                      <h2 className="font-editorial text-section font-medium text-ink-900">
                        {t(`pillars.${pillar.key}.title`)}
                      </h2>
                    </div>
                    <p className="mt-6 text-lg leading-relaxed text-ink-600">
                      {t.rich(`pillars.${pillar.key}.intro`, rich)}
                    </p>
                  </div>

                  {/* Photo */}
                  <div className={`relative aspect-[4/3] overflow-hidden rounded-md ${photoOnRight ? "" : "lg:order-1"}`}>
                    <Image
                      src={photo.src}
                      alt={photo.alt}
                      fill
                      sizes="(min-width: 1024px) 40vw, 90vw"
                      className="object-cover"
                    />
                  </div>
                </div>
              ) : (
                <div className="max-w-4xl">
                  <span className="label-num">
                    {`0${i + 1}`} · {t(`anchors.${pillar.key}`)}
                  </span>
                  <div className="mt-4 flex items-start gap-5">
                    <span
                      aria-hidden="true"
                      className="inline-flex size-12 shrink-0 items-center justify-center rounded-md border border-line-200 bg-paper text-blue-700"
                    >
                      <PillarIcon className="size-5" />
                    </span>
                    <h2 className="font-editorial text-section font-medium text-ink-900">
                      {t(`pillars.${pillar.key}.title`)}
                    </h2>
                  </div>
                  <p className="mt-6 text-lg leading-relaxed text-ink-600">
                    {t.rich(`pillars.${pillar.key}.intro`, rich)}
                  </p>
                </div>
              )}

              <div
                className={`mt-10 grid gap-px bg-line-200 ${
                  pillar.items.length >= 3 ? "sm:grid-cols-2" : "sm:grid-cols-2"
                }`}
              >
                {pillar.items.map((item) => {
                  const Icon = ICONS[item] ?? Banknote;
                  return (
                    <article
                      key={item}
                      className={`flex gap-5 p-7 transition-colors hover:bg-paper lg:p-8 ${
                        alt ? "bg-cream" : "bg-paper"
                      }`}
                    >
                      <span
                        aria-hidden="true"
                        className="inline-flex size-10 shrink-0 items-center justify-center rounded-md border border-line-200 text-terra-600"
                      >
                        <Icon className="size-4.5" />
                      </span>
                      <div>
                        <h3 className="font-editorial text-lg font-medium leading-snug text-ink-900">
                          {t(`pillars.${pillar.key}.items.${item}.title`)}
                        </h3>
                        <p className="mt-2 text-[0.95rem] leading-relaxed text-ink-600">
                          {t(`pillars.${pillar.key}.items.${item}.text`)}
                        </p>
                      </div>
                    </article>
                  );
                })}
              </div>
            </Container>
          </section>
        );
      })}

      <CtaBand />
    </>
  );
}
