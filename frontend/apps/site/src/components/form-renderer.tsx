"use client";

import { useMemo, useState } from "react";

import { buttonClasses } from "@gathe/ui";

/**
 * CH-4 — Renderer générique de FormSchema (portail + vitrine).
 *
 * Reçoit le JSON d'un FormSchema servi par
 * `GET /api/v1/forms/schemas/{kind}/active/`, rend les sections + fields, gère
 * les conditions de visibilité, valide côté client puis renvoie un payload
 * `{ field_id: value }` au parent via `onSubmit`.
 *
 * Champs gérés : text, email, tel, number, textarea, select, radio, checkbox, file, date.
 * Conditions : `equals`, `not_equals`, `in` (référent l'id d'un autre champ).
 * Le flag `is_locked` est ignoré côté renderer — il n'a d'effet que dans
 * l'éditeur admin (Phase 3).
 */

// ----------------------------------------------------------------------
// Types — miroir du JSON Schema backend (apps_coop/forms/models.py).
// ----------------------------------------------------------------------
export type FieldType =
  | "text"
  | "email"
  | "tel"
  | "number"
  | "textarea"
  | "select"
  | "radio"
  | "checkbox"
  | "file"
  | "date";

export type FieldCondition = {
  field: string;
  operator: "equals" | "not_equals" | "in";
  value: unknown;
};

export type FieldOption = { value: string; label: string };

export type SchemaField = {
  id: string;
  type: FieldType;
  label: string;
  required?: boolean;
  placeholder?: string;
  help_text?: string;
  max_length?: number;
  min?: number;
  max?: number;
  accept?: string;
  max_size_mb?: number;
  options?: FieldOption[];
  condition?: FieldCondition;
  is_locked?: boolean;
};

export type SchemaSection = {
  id: string;
  title: string;
  description?: string;
  fields: SchemaField[];
};

export type FormSchemaPayload = {
  id?: number;
  kind?: string;
  version?: number;
  title?: string;
  description?: string;
  schema: { sections: SchemaSection[] };
};

export type FormValues = Record<string, unknown>;

// ----------------------------------------------------------------------
// Helpers
// ----------------------------------------------------------------------
function isFieldVisible(field: SchemaField, values: FormValues): boolean {
  const cond = field.condition;
  if (!cond) return true;
  const ref = values[cond.field];
  switch (cond.operator) {
    case "equals":
      return ref === cond.value;
    case "not_equals":
      return ref !== cond.value;
    case "in":
      return Array.isArray(cond.value) && (cond.value as unknown[]).includes(ref);
    default:
      return true;
  }
}

function validateField(field: SchemaField, value: unknown): string | null {
  // Required — appliqué uniquement si le champ est visible (vérifié par caller).
  if (field.required) {
    if (value === undefined || value === null || value === "" ||
        (Array.isArray(value) && value.length === 0)) {
      return "Ce champ est obligatoire.";
    }
  }
  if (value === undefined || value === null || value === "") return null;

  if (field.type === "email") {
    const s = String(value);
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(s)) return "Adresse e-mail invalide.";
  }

  if (field.type === "tel") {
    const digits = String(value).replace(/\D+/g, "");
    if (digits.length < 8) return "Numéro de téléphone trop court.";
  }

  if (field.type === "number") {
    const n = Number(value);
    if (Number.isNaN(n)) return "Doit être un nombre.";
    if (field.min !== undefined && n < field.min) return `Minimum ${field.min}.`;
    if (field.max !== undefined && n > field.max) return `Maximum ${field.max}.`;
  }

  if (field.max_length && typeof value === "string" && value.length > field.max_length) {
    return `Maximum ${field.max_length} caractères.`;
  }

  if (field.type === "file" && value instanceof File) {
    if (field.max_size_mb && value.size > field.max_size_mb * 1024 * 1024) {
      return `Fichier trop volumineux (max ${field.max_size_mb} Mo).`;
    }
  }

  return null;
}

// ----------------------------------------------------------------------
// Component
// ----------------------------------------------------------------------
export type FormRendererProps = {
  schema: FormSchemaPayload;
  initialValues?: FormValues;
  onSubmit: (values: FormValues) => void | Promise<void>;
  submitLabel?: string;
  submitting?: boolean;
  /** Erreur globale renvoyée par l'API (au-delà des erreurs par champ). */
  globalError?: string | null;
};

export function FormRenderer({
  schema,
  initialValues,
  onSubmit,
  submitLabel = "Envoyer",
  submitting = false,
  globalError,
}: FormRendererProps) {
  const [values, setValues] = useState<FormValues>(initialValues ?? {});
  const [errors, setErrors] = useState<Record<string, string>>({});

  const allFields = useMemo(
    () => schema.schema.sections.flatMap((s) => s.fields),
    [schema],
  );

  function setValue(id: string, v: unknown) {
    setValues((prev) => ({ ...prev, [id]: v }));
    // Efface l'erreur du champ dès qu'il change.
    if (errors[id]) setErrors((e) => ({ ...e, [id]: "" }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (submitting) return;
    const next: Record<string, string> = {};
    for (const field of allFields) {
      if (!isFieldVisible(field, values)) continue;
      const err = validateField(field, values[field.id]);
      if (err) next[field.id] = err;
    }
    setErrors(next);
    if (Object.keys(next).length > 0) {
      const firstId = Object.keys(next)[0];
      document.getElementById(`field-${firstId}`)?.scrollIntoView({
        behavior: "smooth", block: "center",
      });
      return;
    }
    // Filtre les valeurs des champs masqués (au cas où l'utilisateur a rempli
    // puis fait disparaître par condition).
    const payload: FormValues = {};
    for (const field of allFields) {
      if (isFieldVisible(field, values) && values[field.id] !== undefined) {
        payload[field.id] = values[field.id];
      }
    }
    await onSubmit(payload);
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-8">
      {schema.schema.sections.map((section) => (
        <section key={section.id} className="rounded-md border border-line-200 bg-paper p-6">
          <header className="mb-4">
            <h2 className="font-display text-lg font-semibold text-ink-900">{section.title}</h2>
            {section.description ? (
              <p className="mt-1 text-sm text-ink-600">{section.description}</p>
            ) : null}
          </header>
          <div className="space-y-4">
            {section.fields.map((field) =>
              isFieldVisible(field, values) ? (
                <FieldRow
                  key={field.id}
                  field={field}
                  value={values[field.id]}
                  error={errors[field.id]}
                  onChange={(v) => setValue(field.id, v)}
                />
              ) : null,
            )}
          </div>
        </section>
      ))}

      {globalError ? (
        <p role="alert" className="rounded-md border border-terra-400/40 bg-terra-50/60 px-3 py-2 text-sm text-terra-700">
          {globalError}
        </p>
      ) : null}

      <div className="flex justify-end">
        <button
          type="submit"
          disabled={submitting}
          className={buttonClasses({ variant: "primary", size: "lg" })}
        >
          {submitting ? "Envoi…" : submitLabel}
        </button>
      </div>
    </form>
  );
}

// ----------------------------------------------------------------------
// DynamicFields — variante "controlled" pour insertion dans un form parent.
// ----------------------------------------------------------------------
/**
 * Rend les champs d'un FormSchema sans wrapper <form> ni bouton submit, à
 * insérer dans une page qui a déjà son propre formulaire (ex: la page de
 * demande de crédit qui a sa logique 3 voies). Mode controlled : le parent
 * détient `values` + reçoit `onChange`.
 *
 * Option `excludeFieldIds` : pour sauter les champs déjà rendus par le parent
 * (typiquement les hardcoded qui ont une UI dédiée pour leur logique métier).
 */
export type DynamicFieldsProps = {
  schema: FormSchemaPayload;
  values: FormValues;
  onChange: (values: FormValues) => void;
  excludeFieldIds?: Set<string>;
  errors?: Record<string, string>;
};

export function DynamicFields({
  schema,
  values,
  onChange,
  excludeFieldIds,
  errors,
}: DynamicFieldsProps) {
  function setValue(id: string, v: unknown) {
    onChange({ ...values, [id]: v });
  }

  // Filtre : sections vidées de leurs hardcoded — on ne garde que celles qui
  // ont au moins un champ à rendre.
  const filteredSections = schema.schema.sections
    .map((s) => ({
      ...s,
      fields: s.fields.filter((f) => !excludeFieldIds?.has(f.id)),
    }))
    .filter((s) => s.fields.length > 0);

  if (filteredSections.length === 0) return null;

  return (
    <>
      {filteredSections.map((section) => (
        <section key={section.id} className="rounded-md border border-line-200 bg-paper p-6">
          <header className="mb-4">
            <h2 className="font-display text-lg font-semibold text-ink-900">{section.title}</h2>
            {section.description ? (
              <p className="mt-1 text-sm text-ink-600">{section.description}</p>
            ) : null}
          </header>
          <div className="space-y-4">
            {section.fields.map((field) =>
              isFieldVisible(field, values) ? (
                <FieldRow
                  key={field.id}
                  field={field}
                  value={values[field.id]}
                  error={errors?.[field.id]}
                  onChange={(v) => setValue(field.id, v)}
                />
              ) : null,
            )}
          </div>
        </section>
      ))}
    </>
  );
}

/**
 * Helper : valide les champs dynamiques visibles selon le schéma. Retourne
 * un map d'erreurs vide si tout est OK. À utiliser depuis le parent avant le
 * submit.
 */
export function validateDynamicFields(
  schema: FormSchemaPayload,
  values: FormValues,
  excludeFieldIds?: Set<string>,
): Record<string, string> {
  const errors: Record<string, string> = {};
  for (const section of schema.schema.sections) {
    for (const field of section.fields) {
      if (excludeFieldIds?.has(field.id)) continue;
      if (!isFieldVisible(field, values)) continue;
      const err = validateField(field, values[field.id]);
      if (err) errors[field.id] = err;
    }
  }
  return errors;
}


// ----------------------------------------------------------------------
// Field row — un champ + label + erreur.
// ----------------------------------------------------------------------
type FieldRowProps = {
  field: SchemaField;
  value: unknown;
  error?: string;
  onChange: (v: unknown) => void;
};

function FieldRow({ field, value, error, onChange }: FieldRowProps) {
  const labelEl = (
    <label htmlFor={`field-${field.id}`} className="block text-sm font-medium text-ink-900">
      {field.label}
      {field.required ? <span className="ml-0.5 text-terra-600">*</span> : null}
    </label>
  );

  const errorEl = error ? (
    <p role="alert" className="mt-1 text-xs text-terra-700">{error}</p>
  ) : null;
  const helpEl = !error && field.help_text ? (
    <p className="mt-1 text-xs text-ink-500">{field.help_text}</p>
  ) : null;

  const baseInput =
    "mt-1 block w-full rounded-md border border-line-200 bg-paper px-3 py-2 text-ink-900 outline-none transition-colors focus:border-blue-700 focus:ring-1 focus:ring-blue-700";

  switch (field.type) {
    case "text":
    case "email":
    case "tel":
    case "date": {
      const t = field.type === "date" ? "date" : field.type === "tel" ? "tel" : field.type;
      return (
        <div>
          {labelEl}
          <input
            id={`field-${field.id}`}
            type={t}
            value={(value as string) ?? ""}
            onChange={(e) => onChange(e.target.value)}
            placeholder={field.placeholder}
            maxLength={field.max_length}
            className={baseInput}
          />
          {errorEl}{helpEl}
        </div>
      );
    }

    case "number":
      return (
        <div>
          {labelEl}
          <input
            id={`field-${field.id}`}
            type="number"
            value={(value as string) ?? ""}
            onChange={(e) => onChange(e.target.value === "" ? "" : Number(e.target.value))}
            placeholder={field.placeholder}
            min={field.min}
            max={field.max}
            className={baseInput}
          />
          {errorEl}{helpEl}
        </div>
      );

    case "textarea":
      return (
        <div>
          {labelEl}
          <textarea
            id={`field-${field.id}`}
            value={(value as string) ?? ""}
            onChange={(e) => onChange(e.target.value)}
            placeholder={field.placeholder}
            maxLength={field.max_length}
            rows={4}
            className={baseInput + " min-h-[100px]"}
          />
          {errorEl}{helpEl}
        </div>
      );

    case "select":
      return (
        <div>
          {labelEl}
          <select
            id={`field-${field.id}`}
            value={(value as string) ?? ""}
            onChange={(e) => onChange(e.target.value)}
            className={baseInput}
          >
            <option value="">— Choisir —</option>
            {(field.options ?? []).map((opt) => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
          {errorEl}{helpEl}
        </div>
      );

    case "radio":
      return (
        <fieldset id={`field-${field.id}`}>
          {labelEl}
          <div className="mt-2 space-y-2">
            {(field.options ?? []).map((opt) => (
              <label key={opt.value} className="flex items-center gap-2 text-sm text-ink-900">
                <input
                  type="radio"
                  name={field.id}
                  value={opt.value}
                  checked={value === opt.value}
                  onChange={() => onChange(opt.value)}
                />
                {opt.label}
              </label>
            ))}
          </div>
          {errorEl}{helpEl}
        </fieldset>
      );

    case "checkbox":
      // Si options présentes → multi-checkbox ; sinon → checkbox bool simple.
      if (field.options && field.options.length > 0) {
        const arr = (Array.isArray(value) ? value : []) as string[];
        return (
          <fieldset id={`field-${field.id}`}>
            {labelEl}
            <div className="mt-2 space-y-2">
              {field.options.map((opt) => (
                <label key={opt.value} className="flex items-center gap-2 text-sm text-ink-900">
                  <input
                    type="checkbox"
                    checked={arr.includes(opt.value)}
                    onChange={(e) => {
                      const next = e.target.checked
                        ? [...arr, opt.value]
                        : arr.filter((v) => v !== opt.value);
                      onChange(next);
                    }}
                  />
                  {opt.label}
                </label>
              ))}
            </div>
            {errorEl}{helpEl}
          </fieldset>
        );
      }
      return (
        <div>
          <label className="flex items-center gap-2 text-sm text-ink-900">
            <input
              id={`field-${field.id}`}
              type="checkbox"
              checked={Boolean(value)}
              onChange={(e) => onChange(e.target.checked)}
            />
            {field.label}
            {field.required ? <span className="ml-0.5 text-terra-600">*</span> : null}
          </label>
          {errorEl}{helpEl}
        </div>
      );

    case "file":
      return (
        <div>
          {labelEl}
          <input
            id={`field-${field.id}`}
            type="file"
            accept={field.accept}
            onChange={(e) => {
              const f = e.target.files?.[0] ?? null;
              onChange(f);
            }}
            className={baseInput + " p-1.5"}
          />
          {value instanceof File ? (
            <p className="mt-1 text-xs text-ink-500">
              {value.name} · {Math.round(value.size / 1024)} Ko
            </p>
          ) : null}
          {errorEl}{helpEl}
        </div>
      );

    default:
      return null;
  }
}
