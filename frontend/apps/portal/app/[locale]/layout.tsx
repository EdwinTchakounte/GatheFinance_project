import type { ReactNode } from "react";
import { NextIntlClientProvider } from "next-intl";
import { getMessages, setRequestLocale } from "next-intl/server";
import { notFound } from "next/navigation";

import { Container, Logo } from "@gathe/ui";
import { Link } from "@/i18n/navigation";
import { locales, type Locale } from "@/i18n/routing";


export function generateStaticParams() {
  return locales.map((locale) => ({ locale }));
}


/**
 * Shell visuel du portail membre — top bar minimaliste (logo + sous-titre)
 * et footer sobre. Aucune nav marketing : on est dans un espace privé.
 *
 * Le lien « ← Retour au site » pointe vers la vitrine publique via la variable
 * d'environnement `NEXT_PUBLIC_SITE_URL` (cross-origin, port distinct en dev).
 */
export default async function PortalLocaleLayout({
  children,
  params,
}: {
  children: ReactNode;
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  if (!(locales as readonly string[]).includes(locale)) notFound();
  setRequestLocale(locale as Locale);
  const messages = await getMessages();

  const siteUrl = process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3200";

  return (
    <NextIntlClientProvider locale={locale} messages={messages}>
      <div className="flex min-h-svh flex-col bg-cream">
        <header className="border-b border-line-200 bg-paper">
          <Container className="flex h-14 items-center justify-between">
            <Link
              href="/"
              aria-label="Gathe Finance · Espace membre"
              className="inline-flex items-center gap-3"
            >
              <Logo className="h-7 w-auto" />
              <span className="hidden font-display text-[0.72rem] font-medium uppercase tracking-[0.16em] text-ink-600 sm:inline">
                Espace membre
              </span>
            </Link>
            <a
              href={siteUrl}
              className="text-sm text-ink-600 transition-colors hover:text-blue-700"
            >
              ← Retour au site
            </a>
          </Container>
        </header>

        <div className="flex-1">{children}</div>

        <footer className="border-t border-line-200 bg-paper py-4 text-center text-xs text-ink-600">
          <Container>
            © {new Date().getFullYear()} Gathe Finance — Espace membre
          </Container>
        </footer>
      </div>
    </NextIntlClientProvider>
  );
}
