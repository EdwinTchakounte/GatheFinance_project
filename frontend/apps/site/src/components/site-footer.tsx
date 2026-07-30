import { getTranslations } from "next-intl/server";
import { Facebook, Linkedin, MapPin, Phone, Mail, Clock } from "lucide-react";

import { buttonClasses, Container, Logo } from "@gathe/ui";
import { Link } from "@/i18n/navigation";
import { serviceAnchors, siteConfig } from "@/lib/site-config";

export async function SiteFooter() {
  const t = await getTranslations();
  const year = new Date().getFullYear();

  const whyLinks = [
    { href: "/a-propos#mission", label: t("footer.whyMission") },
    { href: "/a-propos#equipe", label: t("footer.whyTeam") },
    { href: "/a-propos#agences", label: t("footer.whyAgencies") },
    { href: "/contact", label: t("footer.whyContact") },
  ];

  return (
    <footer className="bg-blue-950 text-blue-100/80">
      {/* Brand / wordmark band */}
      <Container className="flex flex-col items-start justify-between gap-6 border-b border-white/10 py-10 sm:flex-row sm:items-end">
        <div>
          <Logo variant="light" className="h-9 w-auto" />
          <p className="mt-4 max-w-md text-sm leading-relaxed text-blue-100/80">
            {t("home.about.title")}
          </p>
        </div>
        <div className="flex items-center gap-5">
          <div className="flex gap-2.5">
            <a
              href={siteConfig.social.facebook}
              target="_blank"
              rel="noopener noreferrer"
              aria-label={t("footer.followFacebook")}
              className="inline-flex size-10 items-center justify-center rounded-full border border-white/15 text-white transition-colors hover:border-emerald hover:text-emerald"
            >
              <Facebook aria-hidden="true" className="size-4" />
            </a>
            <a
              href={siteConfig.social.linkedin}
              target="_blank"
              rel="noopener noreferrer"
              aria-label={t("footer.followLinkedin")}
              className="inline-flex size-10 items-center justify-center rounded-full border border-white/15 text-white transition-colors hover:border-emerald hover:text-emerald"
            >
              <Linkedin aria-hidden="true" className="size-4" />
            </a>
          </div>
          <Link href="/devenir-membre" className={buttonClasses({ variant: "success" })}>
            {t("common.joinCoop")}
          </Link>
        </div>
      </Container>

      {/* Press 3-col with hairline filets between columns */}
      <Container className="grid gap-10 py-14 sm:grid-cols-2 lg:grid-cols-3 lg:gap-0">
        <div className="lg:pr-10">
          <h2 className="label-num label-num--on-dark">{t("footer.whyTitle")}</h2>
          <ul className="mt-5 space-y-2.5 text-sm">
            {whyLinks.map((l) => (
              <li key={l.href}>
                <Link href={l.href} className="transition-colors hover:text-white">
                  {l.label}
                </Link>
              </li>
            ))}
          </ul>
        </div>

        <div className="lg:border-l lg:border-white/10 lg:px-10">
          <h2 className="label-num label-num--on-dark">{t("footer.servicesTitle")}</h2>
          <ul className="mt-5 space-y-2.5 text-sm">
            <li><Link href={serviceAnchors[2].href} className="transition-colors hover:text-white">{t("footer.servicesSavings")}</Link></li>
            <li><Link href={serviceAnchors[0].href} className="transition-colors hover:text-white">{t("footer.servicesCredit")}</Link></li>
            <li><Link href={serviceAnchors[1].href} className="transition-colors hover:text-white">{t("footer.servicesTransfers")}</Link></li>
            <li><Link href={serviceAnchors[3].href} className="transition-colors hover:text-white">{t("footer.servicesInvestment")}</Link></li>
            <li><Link href={serviceAnchors[4].href} className="transition-colors hover:text-white">{t("footer.servicesEducation")}</Link></li>
          </ul>
        </div>

        <div className="lg:border-l lg:border-white/10 lg:px-10">
          <h2 className="label-num label-num--on-dark">{t("footer.headOffice")}</h2>
          <ul className="mt-5 space-y-3 text-sm">
            <li className="flex gap-2.5">
              <MapPin aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-emerald" />
              <span>{siteConfig.contact.address}</span>
            </li>
            <li className="flex gap-2.5">
              <Phone aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-emerald" />
              <span>
                <a href={siteConfig.contact.phoneHref} className="transition-colors hover:text-white">{siteConfig.contact.phone}</a>
                <br />
                <span className="text-blue-100/80">{t("footer.landline")}: {siteConfig.contact.landline}</span>
              </span>
            </li>
            <li className="flex gap-2.5">
              <Mail aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-emerald" />
              <a href={siteConfig.contact.emailHref} className="transition-colors hover:text-white">{siteConfig.contact.email}</a>
            </li>
            <li className="flex gap-2.5">
              <Clock aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-emerald" />
              <span>{siteConfig.contact.openingHours}</span>
            </li>
          </ul>
        </div>

      </Container>

      {/* Edition foot */}
      <div className="border-t border-white/10">
        <Container className="flex flex-col items-start justify-between gap-3 py-5 text-xs text-blue-100/80 sm:flex-row sm:items-center">
          <p>© {year} {siteConfig.name} · {t("footer.copyrightTagline")}</p>
          <nav aria-label="Liens légaux" className="flex gap-4">
            <Link href="/mentions-legales" className="transition-colors hover:text-white">{t("footer.legalNotice")}</Link>
            <Link href="/politique-confidentialite" className="transition-colors hover:text-white">{t("footer.privacyPolicy")}</Link>
          </nav>
        </Container>
      </div>
    </footer>
  );
}
