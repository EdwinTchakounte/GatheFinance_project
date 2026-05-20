import { getTranslations } from "next-intl/server";
import { buttonClasses, Container } from "@gathe/ui";
import { Link } from "@/i18n/navigation";

export default async function NotFound() {
  const t = await getTranslations("notFound");
  return (
    <Container className="flex min-h-[60vh] flex-col items-center justify-center py-24 text-center">
      <p className="font-display text-7xl font-bold text-blue-700">404</p>
      <h1 className="mt-4 text-2xl font-bold text-ink-900">{t("title")}</h1>
      <p className="mt-3 max-w-md text-ink-600">{t("text")}</p>
      <Link href="/" className={`${buttonClasses()} mt-8`}>
        {t("backHome")}
      </Link>
    </Container>
  );
}
