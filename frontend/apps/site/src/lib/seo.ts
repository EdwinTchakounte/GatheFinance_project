/**
 * Helpers SEO — alternates canonical + hreflang calculés par page.
 *
 * Sans ça, Next.js fait hériter les `alternates` du layout `[locale]` à TOUTES
 * les sous-pages : chacune déclare alors `canonical = "/"` et des hreflang vers
 * l'accueil au lieu de son équivalent traduit (cannibalisation / désindexation).
 *
 * Routing : `fr` = locale par défaut SANS préfixe (`/contact`), `en` préfixée
 * (`/en/contact`). L'accueil est `/` (fr) et `/en` (en).
 */
export function pageAlternates(locale: string, path: string) {
  // `path` = chemin sans préfixe de locale, commençant par "/" ("/" pour l'accueil).
  const fr = path;
  const en = path === "/" ? "/en" : `/en${path}`;
  return {
    canonical: locale === "fr" ? fr : en,
    languages: { fr, en, "x-default": fr },
  };
}
