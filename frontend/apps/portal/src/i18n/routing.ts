import { defineRouting } from "next-intl/routing";

export const locales = ["fr", "en"] as const;
export type Locale = (typeof locales)[number];

/**
 * Portail membre — mêmes locales que la vitrine ; FR par défaut sans préfixe.
 * Les pages n'utilisent pas (encore) `useTranslations`, mais on garde
 * l'arborescence `[locale]` pour rester aligné avec le site marketing et
 * permettre la bascule EN sans refactor.
 */
export const routing = defineRouting({
  locales,
  defaultLocale: "fr",
  localePrefix: "as-needed",
});
