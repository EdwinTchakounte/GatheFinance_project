// Helpers partagés pour rendre les champs personnalisés (FormSchema) côté
// admin : demandes de crédit membres (loan-requests) et candidatures campagne.
// Sans JSX — la présentation reste propre à chaque page.
import type { FormField, FormSchemaJSON } from "@/lib/api";

/** « statut_pro » → « Statut Pro » (libellé de secours quand le champ est hors schéma). */
export function prettifyFieldKey(key: string): string {
  return key
    .replace(/[_.]+/g, " ")
    .trim()
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

/** Formate la valeur d'un champ selon son type (option → label, oui/non, date). */
export function formatFieldValue(field: FormField, value: unknown): string {
  if (value === null || value === undefined || value === "") return "";
  if (field.type === "checkbox") {
    if (Array.isArray(value)) {
      return value
        .map(
          (v) =>
            field.options?.find((o) => String(o.value) === String(v))?.label ??
            String(v),
        )
        .join(", ");
    }
    if (typeof value === "boolean") return value ? "Oui" : "Non";
    const s = String(value).toLowerCase();
    if (s === "true" || s === "oui") return "Oui";
    if (s === "false" || s === "non") return "Non";
  }
  if (field.type === "select" || field.type === "radio") {
    return (
      field.options?.find((o) => String(o.value) === String(value))?.label ??
      String(value)
    );
  }
  if (field.type === "date") {
    const d = new Date(String(value));
    return Number.isNaN(d.getTime())
      ? String(value)
      : d.toLocaleDateString("fr-FR", {
          day: "2-digit",
          month: "short",
          year: "numeric",
        });
  }
  return String(value);
}

/** Aplatis les champs du schéma en index { field_id → FormField }. */
export function buildFieldIndex(
  schema: FormSchemaJSON | null,
): Map<string, FormField> {
  const index = new Map<string, FormField>();
  for (const section of schema?.sections ?? []) {
    for (const field of section.fields ?? []) index.set(field.id, field);
  }
  return index;
}
