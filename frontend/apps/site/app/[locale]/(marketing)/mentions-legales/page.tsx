import type { Metadata } from "next";
import { pageAlternates } from "@/lib/seo";
import { getTranslations } from "next-intl/server";
import { LegalPageView } from "@/components/legal-page-view";

type Params = { params: Promise<{ locale: string }> };

export async function generateMetadata({ params }: Params): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "footer" });
  return { title: t("legalNotice"), alternates: pageAlternates(locale, "/mentions-legales") };
}

export default async function LegalNoticePage({ params }: Params) {
  const { locale } = await params;
  return <LegalPageView locale={locale} slug="mentions-legales" titleKey="footer.legalNotice" />;
}
