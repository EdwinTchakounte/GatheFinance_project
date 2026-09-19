import type { Metadata } from "next";
import { pageAlternates, SITE_URL } from "@/lib/seo";
import { JsonLd, breadcrumbJsonLd } from "@/components/json-ld";
import { getTranslations, setRequestLocale } from "next-intl/server";
import { Shield, Smartphone } from "lucide-react";

import { Container } from "@gathe/ui";
import { PageHeader } from "@/components/page-shell";
import { InstitutionalDecor } from "@/components/institutional-decor";
import { DownloadAppButton } from "@/components/download-app-button";
import { images } from "@/lib/site-config";

type Params = { params: Promise<{ locale: string }> };

// CANAL PRINCIPAL depuis 2026-09 : le Google Play Store. C'est la voie que
// l'utilisateur connaît, qui gère les mises à jour toute seule, et qui évite
// de lui faire autoriser les « sources inconnues » sur son téléphone.
const PLAY_STORE_URL =
  "https://play.google.com/store/apps/details?id=com.gathefinance.gathe_finance";

// REPLI conservé : l'APK auto-hébergée (/downloads/Gathe-Finance.apk, servie
// avec un Content-Length natif → vraie progression). Utile hors Play Store —
// téléphone sans Services Google, ou installation en agence sans compte Google.
// Le téléchargement direct passe par le proxy Next `/api/download-app`
// (progression réelle) — cf. DownloadAppButton.
const APK_VERSION = "1.2.0";
const APK_SIZE = "74,5 Mo";

// QR code AUTO-HEBERGE (public/downloads/qr-app.png), généré avec la lib
// `qrcode`. Il encode désormais l'URL PLAY STORE — plus la vieille URL Google
// Drive, qui dépendait d'un fichier partagé pouvant disparaître et imposait à
// l'utilisateur un détour par l'UI Drive. À régénérer si l'URL change.
const QR_IMAGE_SRC = "/downloads/qr-app.png";

export async function generateMetadata({ params }: Params): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "download" });
  return { title: t("title"), description: t("lead"), alternates: pageAlternates(locale, "/telecharger-app") };
}

export default async function DownloadAppPage({ params }: Params) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations({ locale, namespace: "download" });
  const tn = await getTranslations({ locale, namespace: "nav" });

  // Le QR code mène au Play Store : scanné depuis un téléphone, il ouvre
  // directement la fiche de l'app, prête à installer.
  const apkAbsoluteUrl = PLAY_STORE_URL;

  return (
    <>
      <JsonLd
        data={breadcrumbJsonLd(SITE_URL, [
          { name: tn("home"), path: "/" },
          { name: t("title"), path: "/telecharger-app" },
        ])}
      />
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
          <div className="grid gap-10 lg:grid-cols-[1.2fr_1fr] lg:gap-16">
            {/* Bloc principal : bouton telecharger + caracteristiques */}
            <div className="space-y-8">
              <div className="rounded-2xl border border-line-200 bg-paper p-8 shadow-sm">
                <div className="flex items-start gap-4">
                  <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-xl bg-emerald-100">
                    <Smartphone className="h-7 w-7 text-emerald-700" aria-hidden="true" />
                  </div>
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-wide text-emerald-700">
                      {t("androidEyebrow")}
                    </p>
                    <h2 className="mt-1 font-editorial text-2xl font-medium text-ink-900">
                      {t("androidTitle")}
                    </h2>
                    <p className="mt-1 text-sm text-ink-600">
                      {t("androidDesc")}
                    </p>
                  </div>
                </div>

                {/* Canal PRINCIPAL : le Play Store. Mises à jour automatiques,
                    pas de « sources inconnues » à autoriser. */}
                <a
                  href={PLAY_STORE_URL}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="mt-6 inline-flex w-full items-center justify-center gap-2 rounded-xl bg-emerald-700 px-5 py-3.5 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-emerald-800"
                >
                  <Smartphone className="h-4 w-4" aria-hidden="true" />
                  Installer depuis Google Play
                </a>

                {/* REPLI : APK directe, avec vraie progression (proxy Next).
                    Pour les téléphones sans Services Google, ou l'installation
                    en agence sans compte Google. */}
                <div className="mt-4 border-t border-line-200 pt-4">
                  <p className="mb-2 text-xs text-ink-500">
                    Pas d&apos;accès au Play Store ? Installe le fichier
                    directement (autorise les « sources inconnues » si ton
                    téléphone le demande).
                  </p>
                  <DownloadAppButton label={t("downloadButton")} />
                </div>

                <dl className="mt-6 grid grid-cols-2 gap-4 text-sm sm:grid-cols-3">
                  <div>
                    <dt className="text-xs uppercase tracking-wide text-ink-500">
                      {t("metaVersion")}
                    </dt>
                    <dd className="mt-0.5 font-mono font-medium text-ink-900">
                      {APK_VERSION}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs uppercase tracking-wide text-ink-500">
                      {t("metaSize")}
                    </dt>
                    <dd className="mt-0.5 font-mono font-medium text-ink-900">
                      {APK_SIZE}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs uppercase tracking-wide text-ink-500">
                      {t("metaPlatform")}
                    </dt>
                    <dd className="mt-0.5 font-mono font-medium text-ink-900">
                      Android 7+
                    </dd>
                  </div>
                </dl>
              </div>

              {/* Instructions installation Android (sources inconnues) */}
              <div className="rounded-2xl border border-blue-200 bg-blue-50/40 p-6">
                <div className="flex items-start gap-3">
                  <Shield className="mt-0.5 h-5 w-5 shrink-0 text-blue-700" aria-hidden="true" />
                  <div>
                    <h3 className="font-semibold text-ink-900">
                      {t("installTitle")}
                    </h3>
                    <ol className="mt-2 list-decimal space-y-1 pl-5 text-sm text-ink-700">
                      <li>{t("installStep1")}</li>
                      <li>{t("installStep2")}</li>
                      <li>{t("installStep3")}</li>
                      <li>{t("installStep4")}</li>
                    </ol>
                  </div>
                </div>
              </div>

            </div>

            {/* QR code lateral */}
            <aside className="lg:sticky lg:top-24 lg:self-start">
              <div className="rounded-2xl border border-line-200 bg-paper p-8 text-center shadow-sm">
                <p className="text-xs font-semibold uppercase tracking-wide text-blue-700">
                  {t("qrEyebrow")}
                </p>
                <h3 className="mt-1 font-editorial text-xl font-medium text-ink-900">
                  {t("qrTitle")}
                </h3>
                <div className="mt-5 flex justify-center">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={QR_IMAGE_SRC}
                    width={240}
                    height={240}
                    alt={t("qrAlt")}
                    className="rounded-xl border border-line-200"
                  />
                </div>
                <p className="mt-4 text-xs text-ink-500">
                  {t("qrHelp")}
                </p>
                <p className="mt-2 break-all font-mono text-[11px] text-ink-500">
                  {apkAbsoluteUrl}
                </p>
              </div>
            </aside>
          </div>
        </Container>
      </section>
    </>
  );
}
