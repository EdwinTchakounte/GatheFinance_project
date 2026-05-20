import { defineRouting } from "next-intl/routing";

export const locales = ["fr", "en"] as const;
export type Locale = (typeof locales)[number];

/**
 * FR is the default and lives at "/"; EN lives at "/en/...".
 * (`localePrefix: "as-needed"` = no prefix for the default locale.)
 */
export const routing = defineRouting({
  locales,
  defaultLocale: "fr",
  localePrefix: "as-needed",
});
