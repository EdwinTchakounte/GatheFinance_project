import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";
import { notFound } from "next/navigation";
import { DM_Sans, Inter, Lora, Plus_Jakarta_Sans, Syne } from "next/font/google";
import { NextIntlClientProvider } from "next-intl";
import { getMessages, getTranslations, setRequestLocale } from "next-intl/server";
// `getTranslations` is still used by generateMetadata below.

import { routing } from "@/i18n/routing";
import { ServiceWorkerRegister } from "@/components/sw-register";
import { JsonLd, organizationJsonLd, websiteJsonLd } from "@/components/json-ld";

const SITE_URL = (process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000").replace(/\/$/, "");

const jakarta = Plus_Jakarta_Sans({ subsets: ["latin", "latin-ext"], weight: ["500", "600", "700", "800"], variable: "--font-jakarta", display: "swap" });
const inter = Inter({ subsets: ["latin", "latin-ext"], variable: "--font-inter", display: "swap" });
const lora = Lora({ subsets: ["latin", "latin-ext"], variable: "--font-lora", display: "swap" });
// Dark fintech skin — Syne (display/editorial) + DM Sans (body).
const syne = Syne({ subsets: ["latin", "latin-ext"], weight: ["700", "800"], variable: "--font-syne", display: "swap" });
const dmSans = DM_Sans({ subsets: ["latin", "latin-ext"], weight: ["300", "400", "500"], variable: "--font-dmsans", display: "swap" });

export const viewport: Viewport = {
  themeColor: "#080808",
  colorScheme: "dark",
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
    applicationName: "Gathe Finance",
    alternates: { canonical: locale === "fr" ? "/" : "/en", languages: { fr: "/", en: "/en", "x-default": "/" } },
    openGraph: {
      type: "website",
      siteName: "Gathe Finance",
      title: t("homeTitle"),
      description: t("homeDescription"),
      locale: locale === "fr" ? "fr_FR" : "en_US",
      url: locale === "fr" ? "/" : "/en",
    },
    twitter: { card: "summary_large_image", title: t("homeTitle"), description: t("homeDescription") },
    robots: { index: true, follow: true },
    appleWebApp: { capable: true, statusBarStyle: "default", title: "Gathe Finance" },
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
    <html lang={locale} className={`${jakarta.variable} ${inter.variable} ${lora.variable} ${syne.variable} ${dmSans.variable}`} suppressHydrationWarning>
      <head>
        {/* Thème : clair par défaut ; sombre opt-in (persisté). Appliqué avant
            le paint pour éviter tout flash. */}
        <script
          dangerouslySetInnerHTML={{
            __html:
              "try{if(localStorage.getItem('gathe-theme')==='dark'){document.documentElement.dataset.theme='dark';document.documentElement.classList.add('dark');}}catch(e){}",
          }}
        />
      </head>
      <body>
        {/* Orbes ambiantes — visibles uniquement en thème sombre (CSS). */}
        <div aria-hidden="true" className="dark-orb dark-orb--green" />
        <div aria-hidden="true" className="dark-orb dark-orb--blue" />
        <JsonLd data={[organizationJsonLd(SITE_URL), websiteJsonLd(SITE_URL)]} />
        <NextIntlClientProvider messages={messages}>
          {props.children}
        </NextIntlClientProvider>
        <ServiceWorkerRegister />
      </body>
    </html>
  );
}
