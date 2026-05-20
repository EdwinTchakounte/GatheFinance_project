import { getRequestConfig } from "next-intl/server";
import { routing } from "./routing";

/**
 * Aucun message n'est encore utilisé côté portail (les pages n'appellent pas
 * `useTranslations`), mais on garde l'infrastructure pour rester compatible
 * avec `next-intl` et préparer l'i18n future. Les fichiers `messages/*.json`
 * sont volontairement vides.
 */
export default getRequestConfig(async ({ requestLocale }) => {
  const requested = await requestLocale;
  const locale =
    requested && (routing.locales as readonly string[]).includes(requested)
      ? requested
      : routing.defaultLocale;

  return {
    locale,
    messages: (await import(`../../messages/${locale}.json`)).default,
  };
});
