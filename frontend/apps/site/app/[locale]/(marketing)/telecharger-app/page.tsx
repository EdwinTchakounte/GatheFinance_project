import type { Metadata } from "next";
import { getTranslations, setRequestLocale } from "next-intl/server";
import { Download, Shield, Smartphone } from "lucide-react";

import { Container } from "@gathe/ui";
import { PageHeader } from "@/components/page-shell";
import { InstitutionalDecor } from "@/components/institutional-decor";
import { images, siteConfig } from "@/lib/site-config";

type Params = { params: Promise<{ locale: string }> };

// APK heberge sur Google Drive (74 Mo, evite de gonfler le repo et le
// container Docker). File ID stable ; pour le rotater il suffit d'uploader
// une nouvelle version et de coller le nouvel ID ici.
const APK_DRIVE_FILE_ID = "1CqqRehipMPZOwk28oZ9q2DYJtgSqVlPQ";
// URL "share" (preview Drive) : utilisee pour le QR code → ouvre l'app
// Drive sur mobile, l'utilisateur clique "Télécharger" depuis l'app.
const APK_SHARE_URL =
  `https://drive.google.com/file/d/${APK_DRIVE_FILE_ID}/view?usp=sharing`;
// URL "direct download" : pour le bouton desktop, force le telechargement
// du blob sans passer par l'UI Drive (necessite le param uc + export).
const APK_DOWNLOAD_URL =
  `https://drive.google.com/uc?export=download&id=${APK_DRIVE_FILE_ID}`;
const APK_VERSION = "1.0.0";
const APK_SIZE = "74,5 Mo";

// QR code via service tiers (api.qrserver.com, gratuit, sans dependance npm).
// L'URL pointe vers la version absolue prod de l'APK pour scan depuis n'importe
// quel mobile. Si on n'est pas en prod (NEXT_PUBLIC_SITE_URL non set) on
// fallback sur un placeholder.
function qrUrl(targetUrl: string): string {
  const encoded = encodeURIComponent(targetUrl);
  return `https://api.qrserver.com/v1/create-qr-code/?size=240x240&data=${encoded}&margin=8`;
}

export async function generateMetadata({ params }: Params): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "download" });
  return { title: t("title"), description: t("lead") };
}

export default async function DownloadAppPage({ params }: Params) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations({ locale, namespace: "download" });
  const tn = await getTranslations({ locale, namespace: "nav" });

  // URL pour le QR code : on encode l'URL "share" Drive, qui ouvre
  // proprement l'app Drive sur mobile (clic → bouton Telecharger natif).
  const apkAbsoluteUrl = APK_SHARE_URL;

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

                <a
                  href={APK_DOWNLOAD_URL}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="mt-6 inline-flex w-full items-center justify-center gap-2 rounded-lg bg-emerald-700 px-6 py-3.5 text-sm font-semibold text-white shadow-sm transition-all hover:bg-emerald-800 sm:w-auto"
                >
                  <Download className="h-5 w-5" aria-hidden="true" />
                  {t("downloadButton")}
                </a>

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
                    src={qrUrl(apkAbsoluteUrl)}
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
