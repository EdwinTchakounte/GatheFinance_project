"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  ArrowDown,
  ArrowLeft,
  ArrowUp,
  CheckCircle2,
  Lock,
  Pencil,
  Plus,
  Save,
  Trash2,
} from "lucide-react";

import { buttonClasses } from "@gathe/ui";

import { Modal, ModalField, modalInputClass } from "@/components/modal";
import {
  adminApi,
  type ApiError,
  type FormField,
  type FormFieldOption,
  type FormFieldType,
  type FormSchemaAdmin,
  type FormSchemaJSON,
  type FormSection,
} from "@/lib/api";


const FIELD_TYPE_LABELS: Record<FormFieldType, string> = {
  text: "Texte court",
  email: "E-mail",
  tel: "Téléphone",
  number: "Nombre",
  textarea: "Texte long",
  select: "Liste déroulante",
  radio: "Boutons radio",
  checkbox: "Cases à cocher",
  file: "Fichier",
  date: "Date",
};
const FIELD_TYPES = Object.keys(FIELD_TYPE_LABELS) as FormFieldType[];

const TYPES_WITH_OPTIONS = new Set<FormFieldType>(["select", "radio", "checkbox"]);


/**
 * CH-4 — Éditeur d'une version FormSchema. Lecture-seule si is_active=true.
 * Sinon : édition titre/description, ajout/suppression/réordonnancement des
 * sections et des champs. Les champs verrouillés (is_locked) gardent leur id
 * et leur type ; seuls le label, le help_text, le placeholder, les options et
 * required restent éditables.
 */
export default function FormSchemaEditorPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const schemaId = Number(id);
  const router = useRouter();

  const [schema, setSchema] = useState<FormSchemaAdmin | null>(null);
  const [draft, setDraft] = useState<FormSchemaJSON | null>(null);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [activating, setActivating] = useState(false);
  const [duplicating, setDuplicating] = useState(false);
  const [message, setMessage] = useState<{ tone: "ok" | "err"; text: string } | null>(null);
  const [editingField, setEditingField] = useState<{
    sectionIdx: number;
    fieldIdx: number | null; // null = nouveau champ
  } | null>(null);

  async function reload() {
    setLoading(true);
    try {
      adminApi.primeCsrf().catch(() => undefined);
      const s = await adminApi.forms.detail(schemaId);
      setSchema(s);
      setDraft(s.schema);
      setTitle(s.title);
      setDescription(s.description);
    } catch (err) {
      const apiErr = err as ApiError;
      setMessage({ tone: "err", text: apiErr.detail ?? "Chargement impossible." });
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    reload();
    /* eslint-disable-next-line react-hooks/exhaustive-deps */
  }, [schemaId]);

  const readOnly = schema?.is_active ?? false;

  function patchDraft(next: FormSchemaJSON) {
    setDraft(next);
  }

  function addSection() {
    if (!draft) return;
    const id = prompt("Identifiant interne de la section (snake_case)") || "";
    if (!id.trim()) return;
    const title = prompt("Titre affiché") || "Nouvelle section";
    patchDraft({
      ...draft,
      sections: [
        ...draft.sections,
        { id: id.trim(), title: title.trim(), fields: [] },
      ],
    });
  }

  function removeSection(idx: number) {
    if (!draft) return;
    if (!confirm("Supprimer cette section et tous ses champs ?")) return;
    patchDraft({ ...draft, sections: draft.sections.filter((_, i) => i !== idx) });
  }

  function moveSection(idx: number, dir: -1 | 1) {
    if (!draft) return;
    const next = [...draft.sections];
    const swap = idx + dir;
    if (swap < 0 || swap >= next.length) return;
    [next[idx], next[swap]] = [next[swap]!, next[idx]!];
    patchDraft({ ...draft, sections: next });
  }

  function moveField(sectionIdx: number, fieldIdx: number, dir: -1 | 1) {
    if (!draft) return;
    const section = draft.sections[sectionIdx];
    if (!section) return;
    const nextFields = [...section.fields];
    const swap = fieldIdx + dir;
    if (swap < 0 || swap >= nextFields.length) return;
    [nextFields[fieldIdx], nextFields[swap]] = [nextFields[swap]!, nextFields[fieldIdx]!];
    const nextSections = [...draft.sections];
    nextSections[sectionIdx] = { ...section, fields: nextFields };
    patchDraft({ ...draft, sections: nextSections });
  }

  function removeField(sectionIdx: number, fieldIdx: number) {
    if (!draft) return;
    const section = draft.sections[sectionIdx];
    if (!section) return;
    const f = section.fields[fieldIdx];
    if (f?.is_locked) {
      alert("Ce champ est verrouillé (câblé en dur) — il ne peut pas être supprimé.");
      return;
    }
    if (!confirm(`Supprimer le champ « ${f?.label ?? "?"} » ?`)) return;
    const nextFields = section.fields.filter((_, i) => i !== fieldIdx);
    const nextSections = [...draft.sections];
    nextSections[sectionIdx] = { ...section, fields: nextFields };
    patchDraft({ ...draft, sections: nextSections });
  }

  function upsertField(sectionIdx: number, fieldIdx: number | null, next: FormField) {
    if (!draft) return;
    const section = draft.sections[sectionIdx];
    if (!section) return;
    const fields = [...section.fields];
    if (fieldIdx === null) fields.push(next);
    else fields[fieldIdx] = next;
    const sections = [...draft.sections];
    sections[sectionIdx] = { ...section, fields };
    patchDraft({ ...draft, sections });
  }

  async function onSave() {
    if (!schema || !draft || readOnly) return;
    setSaving(true);
    setMessage(null);
    try {
      const updated = await adminApi.forms.update(schema.id, {
        title,
        description,
        schema: draft,
      });
      setSchema(updated);
      setDraft(updated.schema);
      setMessage({ tone: "ok", text: "Brouillon sauvegardé." });
    } catch (err) {
      const apiErr = err as ApiError;
      setMessage({ tone: "err", text: apiErr.detail ?? "Sauvegarde impossible." });
    } finally {
      setSaving(false);
    }
  }

  async function onActivate() {
    if (!schema) return;
    if (!confirm(`Activer la v${schema.version} ? La version actuellement active sera désactivée.`)) {
      return;
    }
    setActivating(true);
    try {
      const updated = await adminApi.forms.activate(schema.id);
      setSchema(updated);
      setMessage({ tone: "ok", text: `v${updated.version} activée.` });
    } catch (err) {
      const apiErr = err as ApiError;
      setMessage({ tone: "err", text: apiErr.detail ?? "Activation impossible." });
    } finally {
      setActivating(false);
    }
  }

  // La version active est gelée (versioning). Pour la modifier, on la duplique
  // en brouillon éditable et on ouvre directement le nouvel éditeur — le flux
  // « Dupliquer en brouillon » de la liste, rendu accessible en un clic ici.
  async function onEditActive() {
    if (!schema || duplicating) return;
    setDuplicating(true);
    setMessage(null);
    try {
      const draftSchema = await adminApi.forms.duplicate(schema.id);
      router.push(`/forms/${draftSchema.id}`);
    } catch (err) {
      const apiErr = err as ApiError;
      setMessage({ tone: "err", text: apiErr.detail ?? "Duplication impossible." });
      setDuplicating(false);
    }
  }

  if (loading) {
    return <section className="text-sm text-ink-500">Chargement…</section>;
  }
  if (!schema || !draft) {
    return <section className="text-sm text-ink-500">Schéma introuvable.</section>;
  }

  return (
    <section className="space-y-6">
      <header className="space-y-2">
        <button
          onClick={() => router.push("/forms")}
          className="inline-flex items-center gap-1 text-sm text-ink-500 hover:text-ink-700"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          Retour aux formulaires
        </button>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="font-display text-2xl text-ink-900">
              {schema.kind_display} · v{schema.version}
            </h1>
            <p className="text-xs text-ink-500">
              {readOnly
                ? "Version active (gelée) — clique « Modifier » pour créer un brouillon éditable"
                : "Brouillon — éditable"}
              {schema.activated_at &&
                ` · activé le ${new Date(schema.activated_at).toLocaleDateString("fr-FR")}`}
            </p>
          </div>
          <div className="flex gap-2">
            {readOnly && (
              <button
                onClick={onEditActive}
                disabled={duplicating}
                className={buttonClasses({ variant: "primary", size: "sm" })}
                title="Crée un brouillon éditable à partir de cette version active"
              >
                <Pencil className="mr-1 h-3.5 w-3.5" />
                {duplicating ? "Duplication…" : "Modifier"}
              </button>
            )}
            {!readOnly && (
              <button
                onClick={onSave}
                disabled={saving}
                className={buttonClasses({ variant: "primary", size: "sm" })}
              >
                <Save className="mr-1 h-3.5 w-3.5" />
                {saving ? "Sauvegarde…" : "Sauvegarder"}
              </button>
            )}
            {!readOnly && (
              <button
                onClick={onActivate}
                disabled={activating}
                className={buttonClasses({ variant: "success", size: "sm" })}
              >
                <CheckCircle2 className="mr-1 h-3.5 w-3.5" />
                {activating ? "…" : "Activer cette version"}
              </button>
            )}
          </div>
        </div>
      </header>

      {message && (
        <div
          className={`rounded-md border p-3 text-sm ${
            message.tone === "ok"
              ? "border-emerald-200 bg-emerald-50 text-emerald-700"
              : "border-red-300 bg-red-50 text-red-900"
          }`}
        >
          {message.text}
        </div>
      )}

      {/* Métadonnées schéma */}
      <section className="rounded-2xl border border-line-200 bg-paper p-6">
        <h2 className="mb-3 font-display text-sm font-semibold uppercase tracking-wider text-ink-500">
          Métadonnées
        </h2>
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label className="mb-1 block text-sm font-medium text-ink-900">Titre</label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              disabled={readOnly}
              className={modalInputClass}
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-ink-900">Description</label>
            <input
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              disabled={readOnly}
              className={modalInputClass}
            />
          </div>
        </div>
      </section>

      {/* Sections + fields */}
      <div className="space-y-4">
        {draft.sections.map((section, sIdx) => (
          <section
            key={section.id}
            className="rounded-2xl border border-line-200 bg-paper p-6"
          >
            <header className="mb-3 flex flex-wrap items-center justify-between gap-2">
              <div>
                <h2 className="font-display text-lg text-ink-900">{section.title}</h2>
                <p className="text-xs text-ink-500">id: {section.id}</p>
              </div>
              {!readOnly && (
                <div className="flex gap-1">
                  <button
                    onClick={() => moveSection(sIdx, -1)}
                    disabled={sIdx === 0}
                    className={buttonClasses({ variant: "ghost", size: "sm" })}
                    title="Monter"
                  >
                    <ArrowUp className="h-3.5 w-3.5" />
                  </button>
                  <button
                    onClick={() => moveSection(sIdx, 1)}
                    disabled={sIdx === draft.sections.length - 1}
                    className={buttonClasses({ variant: "ghost", size: "sm" })}
                    title="Descendre"
                  >
                    <ArrowDown className="h-3.5 w-3.5" />
                  </button>
                  <button
                    onClick={() => removeSection(sIdx)}
                    className={buttonClasses({ variant: "ghost", size: "sm" })}
                    title="Supprimer la section"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              )}
            </header>

            <div className="space-y-2">
              {section.fields.length === 0 && (
                <p className="rounded-md border border-line-200 bg-paper-soft p-3 text-xs text-ink-500">
                  Aucun champ dans cette section.
                </p>
              )}
              {section.fields.map((field, fIdx) => (
                <FieldRow
                  key={field.id}
                  field={field}
                  readOnly={readOnly}
                  canMoveUp={fIdx > 0}
                  canMoveDown={fIdx < section.fields.length - 1}
                  onMoveUp={() => moveField(sIdx, fIdx, -1)}
                  onMoveDown={() => moveField(sIdx, fIdx, 1)}
                  onEdit={() => setEditingField({ sectionIdx: sIdx, fieldIdx: fIdx })}
                  onRemove={() => removeField(sIdx, fIdx)}
                />
              ))}
            </div>

            {!readOnly && (
              <button
                onClick={() => setEditingField({ sectionIdx: sIdx, fieldIdx: null })}
                className={buttonClasses({ variant: "secondary", size: "sm" }) + " mt-3"}
              >
                <Plus className="mr-1 h-3.5 w-3.5" />
                Ajouter un champ
              </button>
            )}
          </section>
        ))}

        {!readOnly && (
          <button
            onClick={addSection}
            className={buttonClasses({ variant: "ghost", size: "md" }) + " w-full border border-dashed border-line-400"}
          >
            <Plus className="mr-1 h-4 w-4" />
            Ajouter une section
          </button>
        )}
      </div>

      {editingField && (
        <FieldEditor
          existing={
            editingField.fieldIdx === null
              ? null
              : draft.sections[editingField.sectionIdx]!.fields[editingField.fieldIdx]!
          }
          existingFieldIds={new Set(
            draft.sections.flatMap((s) => s.fields.map((f) => f.id)),
          )}
          onClose={() => setEditingField(null)}
          onSave={(next) => {
            upsertField(editingField.sectionIdx, editingField.fieldIdx, next);
            setEditingField(null);
          }}
        />
      )}

      {/* Lien utile */}
      <p className="text-xs text-ink-500">
        Tu peux <Link href="/forms" className="text-blue-700 hover:underline">revenir à la liste</Link>{" "}
        pour dupliquer la version active si tu veux la modifier (les actifs sont
        gelés).
      </p>
    </section>
  );
}


function FieldRow({
  field,
  readOnly,
  canMoveUp,
  canMoveDown,
  onMoveUp,
  onMoveDown,
  onEdit,
  onRemove,
}: {
  field: FormField;
  readOnly: boolean;
  canMoveUp: boolean;
  canMoveDown: boolean;
  onMoveUp: () => void;
  onMoveDown: () => void;
  onEdit: () => void;
  onRemove: () => void;
}) {
  return (
    <div className="flex flex-wrap items-center gap-3 rounded-md border border-line-200 bg-paper-soft p-3">
      <div className="flex-1 min-w-[200px]">
        <div className="flex items-center gap-2">
          <span className="font-medium text-ink-900">{field.label}</span>
          {field.is_locked && (
            <span title="Verrouillé : câblé en dur" className="inline-flex items-center text-ink-500">
              <Lock className="h-3 w-3" />
            </span>
          )}
          {field.required && (
            <span className="rounded-full bg-terra-50 px-1.5 py-0.5 text-[10px] font-medium text-terra-700">
              Requis
            </span>
          )}
        </div>
        <p className="mt-0.5 text-xs text-ink-500">
          <code>{field.id}</code> · {FIELD_TYPE_LABELS[field.type]}
          {field.condition && ` · conditionnel`}
        </p>
      </div>
      {!readOnly && (
        <div className="flex gap-1">
          <button
            onClick={onMoveUp}
            disabled={!canMoveUp}
            className={buttonClasses({ variant: "ghost", size: "sm" })}
          >
            <ArrowUp className="h-3.5 w-3.5" />
          </button>
          <button
            onClick={onMoveDown}
            disabled={!canMoveDown}
            className={buttonClasses({ variant: "ghost", size: "sm" })}
          >
            <ArrowDown className="h-3.5 w-3.5" />
          </button>
          <button onClick={onEdit} className={buttonClasses({ variant: "ghost", size: "sm" })}>
            Éditer
          </button>
          <button
            onClick={onRemove}
            disabled={field.is_locked}
            className={buttonClasses({ variant: "ghost", size: "sm" })}
            title={field.is_locked ? "Verrouillé" : "Supprimer"}
          >
            <Trash2 className="h-3.5 w-3.5" />
          </button>
        </div>
      )}
    </div>
  );
}


function FieldEditor({
  existing,
  existingFieldIds,
  onClose,
  onSave,
}: {
  existing: FormField | null;
  existingFieldIds: Set<string>;
  onClose: () => void;
  onSave: (next: FormField) => void;
}) {
  const isNew = existing === null;
  const locked = existing?.is_locked ?? false;
  const [draftId, setDraftId] = useState(existing?.id ?? "");
  const [type, setType] = useState<FormFieldType>(existing?.type ?? "text");
  const [label, setLabel] = useState(existing?.label ?? "");
  const [helpText, setHelpText] = useState(existing?.help_text ?? "");
  const [placeholder, setPlaceholder] = useState(existing?.placeholder ?? "");
  const [required, setRequired] = useState(existing?.required ?? false);
  const [optionsText, setOptionsText] = useState(
    (existing?.options ?? [])
      .map((o) => `${o.value}|${o.label}`)
      .join("\n"),
  );
  const [error, setError] = useState<string | null>(null);

  function submit() {
    if (!label.trim()) {
      setError("Le libellé est obligatoire.");
      return;
    }
    if (!draftId.trim()) {
      setError("L'identifiant est obligatoire.");
      return;
    }
    if (isNew && existingFieldIds.has(draftId.trim())) {
      setError(`L'identifiant « ${draftId} » existe déjà.`);
      return;
    }
    let options: FormFieldOption[] | undefined;
    if (TYPES_WITH_OPTIONS.has(type)) {
      options = optionsText
        .split("\n")
        .map((l) => l.trim())
        .filter(Boolean)
        .map((line) => {
          const [value, label] = line.split("|").map((p) => p.trim());
          return { value: value || "", label: label || value || "" };
        });
      if (options.length === 0) {
        setError("Au moins une option est nécessaire pour ce type.");
        return;
      }
    }
    onSave({
      ...(existing ?? {}),
      id: draftId.trim(),
      type,
      label: label.trim(),
      help_text: helpText.trim() || undefined,
      placeholder: placeholder.trim() || undefined,
      required,
      options,
      is_locked: locked,
    });
  }

  return (
    <Modal
      open
      onClose={onClose}
      title={isNew ? "Ajouter un champ" : `Éditer « ${existing!.label} »`}
    >
      {locked && (
        <p className="rounded-md border border-orange-200 bg-orange-50 p-2 text-xs text-orange-900">
          <Lock className="mr-1 inline h-3 w-3" />
          Champ verrouillé : seul le libellé, le help-text, le placeholder, les
          options et le caractère obligatoire restent éditables.
        </p>
      )}
      <ModalField label="Identifiant interne (snake_case) *">
        <input
          type="text"
          value={draftId}
          disabled={!isNew || locked}
          onChange={(e) => setDraftId(e.target.value)}
          placeholder="ex: profession_secondaire"
          className={modalInputClass}
        />
      </ModalField>
      <ModalField label="Type de champ *">
        <select
          value={type}
          disabled={!isNew || locked}
          onChange={(e) => setType(e.target.value as FormFieldType)}
          className={modalInputClass}
        >
          {FIELD_TYPES.map((t) => (
            <option key={t} value={t}>{FIELD_TYPE_LABELS[t]}</option>
          ))}
        </select>
      </ModalField>
      <ModalField label="Libellé (affiché au membre) *">
        <input
          type="text"
          value={label}
          onChange={(e) => setLabel(e.target.value)}
          className={modalInputClass}
        />
      </ModalField>
      <ModalField label="Aide (texte sous le champ)">
        <input
          type="text"
          value={helpText}
          onChange={(e) => setHelpText(e.target.value)}
          className={modalInputClass}
        />
      </ModalField>
      <ModalField label="Placeholder">
        <input
          type="text"
          value={placeholder}
          onChange={(e) => setPlaceholder(e.target.value)}
          className={modalInputClass}
        />
      </ModalField>
      <ModalField label="Champ obligatoire ?">
        <label className="inline-flex items-center gap-2 text-sm text-ink-900">
          <input
            type="checkbox"
            checked={required}
            onChange={(e) => setRequired(e.target.checked)}
          />
          Le membre doit le remplir pour soumettre
        </label>
      </ModalField>
      {TYPES_WITH_OPTIONS.has(type) && (
        <ModalField label="Options (une par ligne, format : valeur|libellé)">
          <textarea
            value={optionsText}
            onChange={(e) => setOptionsText(e.target.value)}
            rows={4}
            placeholder={"salarie|Salarié\nindependant|Indépendant"}
            className={modalInputClass + " min-h-[100px] font-mono text-xs"}
          />
        </ModalField>
      )}
      {error && (
        <p className="rounded-md border border-red-300 bg-red-50 p-2 text-sm text-red-900">{error}</p>
      )}
      <div className="flex justify-end gap-2 pt-3">
        <button onClick={onClose} className={buttonClasses({ variant: "ghost", size: "sm" })}>
          Annuler
        </button>
        <button onClick={submit} className={buttonClasses({ variant: "primary", size: "sm" })}>
          {isNew ? "Ajouter" : "Enregistrer"}
        </button>
      </div>
    </Modal>
  );
}
