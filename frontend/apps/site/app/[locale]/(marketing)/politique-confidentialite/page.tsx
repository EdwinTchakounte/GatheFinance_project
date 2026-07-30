import type { Metadata } from "next";
import { pageAlternates } from "@/lib/seo";
import { getTranslations } from "next-intl/server";
import { LegalPageView } from "@/components/legal-page-view";

type Params = { params: Promise<{ locale: string }> };

export async function generateMetadata({ params }: Params): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "footer" });
  return { title: t("privacyPolicy"), alternates: pageAlternates(locale, "/politique-confidentialite") };
}

export default async function PrivacyPolicyPage({ params }: Params) {
  const { locale } = await params;
  return <LegalPageView locale={locale} slug="politique-confidentialite" titleKey="footer.privacyPolicy" />;
}
