import Image from "next/image";
import { getTranslations } from "next-intl/server";
import { Facebook, Linkedin, User } from "lucide-react";

import { buttonClasses, Container, Logo } from "@gathe/ui";
import { Link } from "@/i18n/navigation";
import { images, mainNav, siteConfig } from "@/lib/site-config";
import { NavMenu, type NavEntry } from "./nav-menu";
import { LocaleSwitcher } from "./locale-switcher";
import { MobileNav } from "./mobile-nav";

export async function SiteHeader() {
  const t = await getTranslations("nav");
  // Bilingual taglines pulled from existing messages (no invented content).
  const tHomeFr = await getTranslations({ locale: "fr", namespace: "home" });
  const tHomeEn = await getTranslations({ locale: "en", namespace: "home" });

  const navItems: NavEntry[] = mainNav.map((item) => ({
    label: t(item.key),
    href: item.href,
    children: item.children?.map((c) => ({
      label: t(c.key),
      href: c.href,
      desc: c.descKey ? t(c.descKey) : undefined,
    })),
  }));

  return (
    <header className="sticky top-0 z-40">
      {/* ===== Mobile band — light surface so the wordmark blends naturally ===== */}
      <div className="border-b border-line-200 bg-paper md:hidden">
        <Container className="flex items-center justify-between py-2.5">
          <Link href="/" aria-label={siteConfig.name} className="inline-flex">
            <Logo className="h-9 w-auto" />
          </Link>
          <div className="flex items-center gap-2">
            <a
              href={siteConfig.social.facebook}
              target="_blank"
              rel="noopener noreferrer"
              aria-label="Facebook"
              className="inline-flex size-9 items-center justify-center rounded-full border border-line-200 text-ink-600 transition-colors hover:border-blue-700 hover:text-blue-700"
            >
              <Facebook aria-hidden="true" className="size-3.5" />
            </a>
            <a
              href={siteConfig.social.linkedin}
              target="_blank"
              rel="noopener noreferrer"
              aria-label="LinkedIn"
              className="inline-flex size-9 items-center justify-center rounded-full border border-line-200 text-ink-600 transition-colors hover:border-blue-700 hover:text-blue-700"
            >
              <Linkedin aria-hidden="true" className="size-4" />
            </a>
          </div>
        </Container>
      </div>

      {/* ===== Desktop institutional band — bilingual tagline + central logo + social ===== */}
      <div className="relative isolate hidden overflow-hidden bg-blue-950 text-white md:block">
        <Image
          src={images.entrepreneurs}
          alt=""
          fill
          sizes="100vw"
          loading="lazy"
          className="object-cover object-center opacity-[0.08]"
        />
        <div aria-hidden="true" className="absolute inset-0 bg-blue-950/88" />
        <div aria-hidden="true" className="absolute inset-x-0 bottom-0 h-px bg-surface-50/12" />

        <Container className="relative">
          <div className="grid items-center gap-4 py-2.5 md:grid-cols-[1fr_auto_1fr] md:gap-5 lg:py-3">
            {/* Left — FR tagline */}
            <div className="pr-4 text-right lg:pr-8">
              <p lang="fr" className="font-display text-[0.7rem] font-medium uppercase leading-[1.3] tracking-[0.08em] text-terra-300">
                {tHomeFr("about.title")}
              </p>
            </div>

            {/* Center — wordmark */}
            <Link
              href="/"
              aria-label={siteConfig.name}
              className="shrink-0 transition-opacity hover:opacity-85"
            >
              <Logo className="h-10 w-auto lg:h-11" />
            </Link>

            {/* Right — EN tagline */}
            <div className="pl-4 text-left lg:pl-8">
              <p lang="en" className="font-display text-[0.7rem] font-medium uppercase leading-[1.3] tracking-[0.08em] text-terra-300">
                {tHomeEn("about.title")}
              </p>
            </div>
          </div>

          {/* Social icons — far-right edge, vertically centered (desktop only) */}
          <div className="absolute right-4 top-1/2 hidden -translate-y-1/2 items-center gap-1.5 lg:flex">
            <a
              href={siteConfig.social.facebook}
              target="_blank"
              rel="noopener noreferrer"
              aria-label="Facebook"
              className="inline-flex size-7 items-center justify-center rounded-full border border-white/20 text-white/80 transition-colors hover:border-emerald hover:text-emerald"
            >
              <Facebook aria-hidden="true" className="size-3" />
            </a>
            <a
              href={siteConfig.social.linkedin}
              target="_blank"
              rel="noopener noreferrer"
              aria-label="LinkedIn"
              className="inline-flex size-7 items-center justify-center rounded-full border border-white/20 text-white/80 transition-colors hover:border-emerald hover:text-emerald"
            >
              <Linkedin aria-hidden="true" className="size-3.5" />
            </a>
          </div>
        </Container>
      </div>

      {/* ===== Main nav bar — nav links on the left, button on the right ===== */}
      <div className="border-b border-line-200 bg-paper/95 backdrop-blur-md">
        <Container className="flex h-[56px] items-center justify-between gap-4 md:h-[60px]">
          {/* Left — hamburger (mobile) + nav links (desktop) */}
          <div className="flex items-center gap-1">
            <MobileNav items={navItems} joinLabel={t("join")} memberLabel={t("memberSpace")} />
            <NavMenu items={navItems} />
          </div>

          {/* Right — locale switcher + member space + join button */}
          <div className="flex items-center gap-2.5">
            <LocaleSwitcher className="hidden sm:flex" />
            {/* Portail membre — surface séparée (apps/portal) → URL absolue. */}
            <a
              href={`${process.env.NEXT_PUBLIC_PORTAL_URL ?? "http://localhost:3201"}/connexion`}
              className="hidden items-center gap-1.5 px-2 py-1.5 text-sm font-medium text-ink-700 transition-colors hover:text-blue-700 sm:inline-flex"
            >
              <User aria-hidden="true" className="size-4" />
              {t("memberSpace")}
            </a>
            <Link
              href="/devenir-membre"
              className={`${buttonClasses({ size: "sm" })} hidden sm:inline-flex`}
            >
              {t("join")}
            </Link>
          </div>
        </Container>
      </div>
    </header>
  );
}
