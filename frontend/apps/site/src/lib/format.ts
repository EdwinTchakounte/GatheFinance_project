/** Format an ISO date string for display, robust to bad locales / empty values. */
export function formatDate(value: string | null | undefined, locale: string): string {
  if (!value) return "";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "";
  const bcp47 = locale === "en" ? "en-GB" : "fr-FR";
  try {
    return d.toLocaleDateString(bcp47, { year: "numeric", month: "long", day: "numeric" });
  } catch {
    return d.toISOString().slice(0, 10);
  }
}
