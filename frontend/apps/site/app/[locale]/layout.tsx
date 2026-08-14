import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";
import { notFound } from "next/navigation";
import localFont from "next/font/local";
import { NextIntlClientProvider } from "next-intl";
import { getMessages, getTranslations, setRequestLocale } from "next-intl/server";
// `getTranslations` is still used by generateMetadata below.

import { routing } from "@/i18n/routing";
import { ServiceWorkerRegister } from "@/components/sw-register";
import { JsonLd, organizationJsonLd, websiteJsonLd } from "@/components/json-ld";

const SITE_URL = (process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000").replace(/\/$/, "");

// Seules Syne (display/editorial) + DM Sans (corps) sont réellement mappées par
// globals.css (@theme). Les familles Jakarta/Inter/Lora étaient chargées sans
// être utilisées (écrasées dans la cascade) → retirées (payload WOFF2 en moins).
// Polices variables AUTO-HÉBERGÉES (subset latin, couvre le français) : plus
// aucune dépendance réseau à Google Fonts au moment du build.
const syne = localFont({ src: "../../../../fonts/syne-latin.woff2", weight: "600 800", variable: "--font-syne", display: "swap" });
const dmSans = localFont({ src: "../../../../fonts/dmsans-latin.woff2", weight: "300 700", variable: "--font-dmsans", display: "swap" });
// JetBrains Mono — chiffres, montants et références (design system).
const jetbrains = localFont({ src: "../../../../fonts/jetbrains-latin.woff2", weight: "400 600", variable: "--font-jetbrains", display: "swap" });

export const viewport: Viewport = {
  // Aligné sur le manifest (theme_color #0e4d92) — la vitrine est en thème clair
  // (manifest background_color #ffffff), d'où colorScheme "light".
  themeColor: "#0e4d92",
  colorScheme: "light",
};

export function generateStaticParams() {
  return routing.locales.map((locale) => ({ locale }));
}

export async function generateMetadata(props: { params: Promise<{ locale: string }> }): Promise<Metadata> {
  const { locale } = await props.params;
  const t = await getTranslations({ locale, namespace: "meta" });
  return {
    metadataBase: new URL(SITE_URL),
    title: { default: t("homeTitle"), template: `%s — ${t("siteName")}` },
    description: t("homeDescription"),
    applicationName: "GATHE Finance",
    alternates: { canonical: locale === "fr" ? "/" : "/en", languages: { fr: "/", en: "/en", "x-default": "/" } },
    openGraph: {
      type: "website",
      siteName: "GATHE Finance",
      title: t("homeTitle"),
      description: t("homeDescription"),
      locale: locale === "fr" ? "fr_FR" : "en_US",
      url: locale === "fr" ? "/" : "/en",
    },
    twitter: { card: "summary_large_image", title: t("homeTitle"), description: t("homeDescription") },
    keywords: [
      "coopérative épargne crédit Cameroun",
      "microfinance Douala",
      "crédit entrepreneur Cameroun",
      "épargne placement coopérative",
      "GATHE Finance",
    ],
    // Vérification des moteurs (Google Search Console / Bing) — pilotée par
    // variable d'env, no-op si absente. Colle le code fourni par la console.
    verification: {
      google: process.env.NEXT_PUBLIC_GOOGLE_SITE_VERIFICATION || undefined,
      other: process.env.NEXT_PUBLIC_BING_SITE_VERIFICATION
        ? { "msvalidate.01": process.env.NEXT_PUBLIC_BING_SITE_VERIFICATION }
        : {},
    },
    robots: {
      index: true,
      follow: true,
      googleBot: {
        index: true,
        follow: true,
        "max-image-preview": "large",
        "max-snippet": -1,
        "max-video-preview": -1,
      },
    },
    appleWebApp: { capable: true, statusBarStyle: "default", title: "GATHE Finance" },
  };
}

export default async function LocaleLayout(props: {
  children: ReactNode;
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await props.params;
  if (!(routing.locales as readonly string[]).includes(locale)) notFound();
  setRequestLocale(locale);
  const messages = await getMessages();

  return (
    <html lang={locale} className={`${syne.variable} ${dmSans.variable} ${jetbrains.variable}`} suppressHydrationWarning>
      <body>
        <JsonLd data={[organizationJsonLd(SITE_URL), websiteJsonLd(SITE_URL)]} />
        <NextIntlClientProvider messages={messages}>
          {props.children}
        </NextIntlClientProvider>
        <ServiceWorkerRegister />
      </body>
    </html>
  );
}
