import type { Metadata } from "next";
import { pageAlternates } from "@/lib/seo";
import { getTranslations, setRequestLocale } from "next-intl/server";
import { MapPin, Phone, Mail, Clock, MessageCircle, Facebook, Linkedin } from "lucide-react";

import { Container } from "@gathe/ui";
import { PageHeader } from "@/components/page-shell";
import { ContactForm } from "@/components/contact-form";
import { CtaBand } from "@/components/cta-band";
import { InstitutionalDecor } from "@/components/institutional-decor";
import { images, siteConfig } from "@/lib/site-config";

type Params = { params: Promise<{ locale: string }> };

export async function generateMetadata({ params }: Params): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "contact" });
  return { title: t("title"), description: t("lead"), alternates: pageAlternates(locale, "/contact") };
}

export default async function ContactPage({ params }: Params) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations({ locale, namespace: "contact" });
  const tn = await getTranslations({ locale, namespace: "nav" });
  const tc = await getTranslations({ locale, namespace: "common" });
  const whatsappUrl = `https://wa.me/${siteConfig.contact.whatsapp}`;

  return (
    <>
      <PageHeader
        eyebrow={t("eyebrow")}
        title={t("title")}
        lead={t("lead")}
        homeLabel={tn("home")}
        image={images.onlineSupport}
      />

      <section className="relative isolate overflow-hidden section-pad bg-paper">
        <InstitutionalDecor variant="grid" />
        <Container className="relative">
          <div className="grid gap-12 lg:grid-cols-[1.35fr_1fr] lg:gap-16">
            {/* ---- Form column ---- */}
            <div>
              <span className="label-num">01 · {t("formTitle")}</span>
              <h2 className="mt-4 font-editorial text-section font-medium text-ink-900">
                {t("formTitle")}
              </h2>
              <div className="mt-8 border-t border-line-200 pt-8">
                <ContactForm endpoint="contact" />
              </div>
            </div>

            {/* ---- Coordinates column ---- */}
            <aside>
              <span className="label-num">02 · {t("coordsTitle")}</span>
              <h2 className="mt-4 font-editorial text-section font-medium text-ink-900">
                {t("coordsTitle")}
              </h2>

              <div className="mt-8 border-l border-line-200 pl-6 lg:pl-8">
                <ul className="space-y-5 text-sm">
                  <li className="flex gap-3">
                    <MapPin aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-terra-600" />
                    <span className="leading-relaxed text-ink-700">{siteConfig.contact.address}</span>
                  </li>
                  <li className="flex gap-3">
                    <Phone aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-terra-600" />
                    <span className="leading-relaxed">
                      <a href={siteConfig.contact.phoneHref} className="text-ink-700 hover:text-blue-700">
                        {siteConfig.contact.phone}
                      </a>
                      <br />
                      <span className="text-ink-500">Fix: {siteConfig.contact.landline}</span>
                    </span>
                  </li>
                  <li className="flex gap-3">
                    <Mail aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-terra-600" />
                    <a
                      href={siteConfig.contact.emailHref}
                      className="leading-relaxed text-ink-700 hover:text-blue-700"
                    >
                      {siteConfig.contact.email}
                    </a>
                  </li>
                  <li className="flex gap-3">
                    <Clock aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-terra-600" />
                    <span className="leading-relaxed">
                      <span className="block font-medium text-ink-900">{tc("openingHoursLabel")}</span>
                      <span className="text-ink-700">{siteConfig.contact.openingHours}</span>
                    </span>
                  </li>
                </ul>

                <a
                  href={whatsappUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="mt-8 inline-flex items-center gap-2 border border-green-600 px-4 py-2.5 text-sm font-medium text-green-700 transition-colors hover:bg-green-50"
                >
                  <MessageCircle aria-hidden="true" className="size-4" />
                  {t("writeOnWhatsApp")}
                </a>

                <div className="mt-8 flex gap-3">
                  <a
                    href={siteConfig.social.facebook}
                    target="_blank"
                    rel="noopener noreferrer"
                    aria-label="Facebook"
                    className="inline-flex size-10 items-center justify-center rounded-full border border-line-200 text-ink-700 transition-colors hover:border-blue-700 hover:text-blue-700"
                  >
                    <Facebook aria-hidden="true" className="size-4" />
                  </a>
                  <a
                    href={siteConfig.social.linkedin}
                    target="_blank"
                    rel="noopener noreferrer"
                    aria-label="LinkedIn"
                    className="inline-flex size-10 items-center justify-center rounded-full border border-line-200 text-ink-700 transition-colors hover:border-blue-700 hover:text-blue-700"
                  >
                    <Linkedin aria-hidden="true" className="size-4" />
                  </a>
                </div>
              </div>
            </aside>
          </div>
        </Container>
      </section>

      <CtaBand />
    </>
  );
}
