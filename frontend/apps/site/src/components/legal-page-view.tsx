import { getTranslations, setRequestLocale } from "next-intl/server";
import { Section } from "@gathe/ui";
import { PageHeader } from "./page-shell";
import { StreamField } from "./streamfield";
import { getLegalPage } from "@/lib/wagtail";

/** Renders a CMS LegalPage (mentions légales / politique de confidentialité). */
export async function LegalPageView({ locale, slug, titleKey }: { locale: string; slug: string; titleKey: string }) {
  setRequestLocale(locale);
  const t = await getTranslations({ locale });
  const page = await getLegalPage(slug, locale);
  const title = page?.title || t(titleKey);
  const hasBody = !!page?.body?.length;

  return (
    <>
      <PageHeader title={title} homeLabel={t("nav.home")} />
      <Section spacing="lg">
        {hasBody ? (
          <div className="mx-auto max-w-2xl">
            <StreamField blocks={page!.body} />
          </div>
        ) : (
          <div className="mx-auto max-w-2xl rounded-[var(--radius-xl)] border border-dashed border-line-200 bg-surface-50 p-8 text-ink-600">
            {t("legal.draftNotice")}
          </div>
        )}
      </Section>
    </>
  );
}
