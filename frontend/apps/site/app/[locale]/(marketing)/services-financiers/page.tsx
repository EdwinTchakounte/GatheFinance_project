import type { Metadata } from "next";
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

  return (
    <>
      <PageHeader
        eyebrow={t("eyebrow")}
        title={t("title")}
        lead={t("lead")}
        homeLabel={tn("home")}
        image={images.fcfaBills}
      />

      {/* Sticky anchor strip — editorial press style */}
      <div className="sticky top-[4.25rem] z-30 border-b border-line-200 bg-paper/95 backdrop-blur lg:top-[6.5rem]">
        <Container className="flex gap-x-6 gap-y-2 overflow-x-auto py-3 text-sm">
          {PILLARS.map((p, i) => (
            <a
              key={p.id}
              href={`#${p.id}`}
              className="shrink-0 whitespace-nowrap text-ink-600 transition-colors hover:text-blue-700"
            >
              <span className="mr-1.5 text-[0.7rem] font-medium tracking-[0.14em] text-terra-600">
                {`0${i + 1}`}
              </span>
              {t(`anchors.${p.key}`)}
            </a>
          ))}
        </Container>
      </div>

      {/* Intro */}
      <section className="relative isolate overflow-hidden bg-paper section-pad-sm">
        <InstitutionalDecor variant="weave" />
        <Container className="relative">
          <p className="max-w-4xl text-lg leading-relaxed text-ink-600">{t.rich("intro2", rich)}</p>
        </Container>
      </section>

      {/* Pillars */}
      {PILLARS.map((pillar, i) => {
        const PillarIcon = PILLAR_ICONS[pillar.key]!;
        const alt = i % 2 === 1;
        return (
          <section
            key={pillar.id}
            id={pillar.id}
            className={`section-pad scroll-mt-[8rem] ${alt ? "bg-cream" : "bg-paper"}`}
          >
            <Container>
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
