import type { ReactNode } from "react";
import { notFound } from "next/navigation";
import { getTranslations, setRequestLocale } from "next-intl/server";

import { routing } from "@/i18n/routing";
import { SiteHeader } from "@/components/site-header";
import { SiteFooter } from "@/components/site-footer";
import { SmoothScroll } from "@/components/smooth-scroll";
import { CookieBanner } from "@/components/cookie-banner";


/**
 * Marketing-pages chrome — header, footer, smooth-scroll, cookie banner.
 * Le portail membre vit dans `apps/portal/` (son propre workspace Next.js,
 * URL distincte) ; le groupe de routes `(marketing)` n'a donc plus de chrome
 * « privé » à éviter, mais on le garde pour isoler les pages publiques d'éventuels
 * futurs segments (mentions légales, blog, etc.).
 *
 * `setRequestLocale(locale)` est appelé ici (en plus du parent `[locale]/layout.tsx`)
 * car next-intl ≥ 3 exige que chaque layout/page Server qui appelle
 * `getTranslations()` ait le locale fixé dans son propre rendu — sinon
 * l'hydration échoue (le serveur rend FR par défaut, le client rend la bonne
 * locale après hydration).
 */
export default async function MarketingLayout({
  children,
  params,
}: {
  children: ReactNode;
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  if (!(routing.locales as readonly string[]).includes(locale)) notFound();
  setRequestLocale(locale);
  const t = await getTranslations("nav");
  return (
    <>
      <SmoothScroll />
      <a
        href="#main"
        className="sr-only rounded-md bg-blue-700 px-4 py-2 text-sm text-white focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50"
      >
        {t("skipToContent")}
      </a>
      <SiteHeader />
      <main id="main">{children}</main>
      <SiteFooter />
      <CookieBanner />
    </>
  );
}
