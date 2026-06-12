"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { CheckCircle2, Copy, Edit3, FileEdit, Plus, Trash2 } from "lucide-react";

import { buttonClasses } from "@gathe/ui";

import {
  adminApi,
  type ApiError,
  type FormSchemaAdmin,
  type FormSchemaKind,
} from "@/lib/api";


const KIND_LABELS: Record<FormSchemaKind, string> = {
  adhesion: "Adhésion",
  loan_request: "Demande de crédit",
  loan_renewal: "Reconduction de crédit",
};
const KINDS: FormSchemaKind[] = ["adhesion", "loan_request", "loan_renewal"];


/**
 * CH-4 — Liste des FormSchema par kind. Pour chaque kind : version active +
 * brouillons en file d'attente. Actions : éditer un brouillon, dupliquer une
 * version, activer, supprimer un brouillon.
 */
export default function FormSchemasListPage() {
  const [items, setItems] = useState<FormSchemaAdmin[]>([]);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState<{ tone: "ok" | "err"; text: string } | null>(null);
  const [acting, setActing] = useState<number | null>(null);

  async function reload() {
    setLoading(true);
    try {
      adminApi.primeCsrf().catch(() => undefined);
      setItems(await adminApi.forms.list());
    } catch (err) {
      const apiErr = err as ApiError;
      setMessage({ tone: "err", text: apiErr.detail ?? "Chargement impossible." });
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    reload();
  }, []);

  async function onDuplicate(schema: FormSchemaAdmin) {
    setActing(schema.id);
    try {
      await adminApi.forms.duplicate(schema.id);
      setMessage({
        tone: "ok",
        text: `${KIND_LABELS[schema.kind]} v${schema.version} dupliqué en brouillon.`,
      });
      await reload();
    } catch (err) {
      const apiErr = err as ApiError;
      setMessage({ tone: "err", text: apiErr.detail ?? "Duplication impossible." });
    } finally {
      setActing(null);
    }
  }

  async function onActivate(schema: FormSchemaAdmin) {
    if (!confirm(`Activer ${KIND_LABELS[schema.kind]} v${schema.version} ? La version actuellement active sera désactivée.`)) {
      return;
    }
    setActing(schema.id);
    try {
      await adminApi.forms.activate(schema.id);
      setMessage({
        tone: "ok",
        text: `${KIND_LABELS[schema.kind]} v${schema.version} activé. Les nouvelles soumissions utilisent ce schéma.`,
      });
      await reload();
    } catch (err) {
      const apiErr = err as ApiError;
      setMessage({ tone: "err", text: apiErr.detail ?? "Activation impossible." });
    } finally {
      setActing(null);
    }
  }

  async function onDelete(schema: FormSchemaAdmin) {
    if (!confirm(`Supprimer ${KIND_LABELS[schema.kind]} v${schema.version} ? Irréversible.`)) {
      return;
    }
    setActing(schema.id);
    try {
      await adminApi.forms.delete(schema.id);
      setMessage({ tone: "ok", text: "Brouillon supprimé." });
      await reload();
    } catch (err) {
      const apiErr = err as ApiError;
      setMessage({ tone: "err", text: apiErr.detail ?? "Suppression impossible." });
    } finally {
      setActing(null);
    }
  }

  return (
    <main className="space-y-6 p-8">
      <header className="space-y-1">
        <h1 className="font-display text-2xl text-ink-900">Formulaires dynamiques</h1>
        <p className="max-w-3xl text-sm text-ink-500">
          Configure les champs des trois formulaires métier (adhésion publique,
          demande de crédit, reconduction). Une seule version active par
          formulaire ; les autres sont des brouillons modifiables. Les champs
          verrouillés (🔒) sont câblés en dur dans le code — ne peuvent pas être
          supprimés ni changés de type.
        </p>
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

      {loading ? (
        <p className="text-sm text-ink-500">Chargement…</p>
      ) : (
        <div className="space-y-8">
          {KINDS.map((kind) => {
            const all = items.filter((s) => s.kind === kind);
            const active = all.find((s) => s.is_active) ?? null;
            const drafts = all.filter((s) => !s.is_active);
            return (
              <section
                key={kind}
                className="rounded-2xl border border-line-200 bg-paper p-6"
              >
                <header className="mb-4 flex flex-wrap items-center justify-between gap-3">
                  <h2 className="font-display text-lg text-ink-900">
                    {KIND_LABELS[kind]}
                  </h2>
                  {active && (
                    <button
                      onClick={() => onDuplicate(active)}
                      disabled={acting === active.id}
                      className={buttonClasses({ variant: "secondary", size: "sm" })}
                    >
                      <Copy className="mr-1 h-3.5 w-3.5" />
                      Dupliquer en brouillon
                    </button>
                  )}
                </header>

                {/* Version active */}
                {active ? (
                  <ScheduleRow
                    schema={active}
                    isActive
                    acting={acting === active.id}
                    onActivate={() => onActivate(active)}
                    onDelete={() => onDelete(active)}
                  />
                ) : (
                  <p className="rounded-md border border-orange-200 bg-orange-50 p-3 text-sm text-orange-900">
                    Aucune version active. Crée un brouillon puis active-le.
                  </p>
                )}

                {/* Brouillons */}
                {drafts.length > 0 && (
                  <div className="mt-3 space-y-2">
                    <p className="text-xs font-semibold uppercase tracking-wider text-ink-500">
                      Brouillons
                    </p>
                    {drafts.map((draft) => (
                      <ScheduleRow
                        key={draft.id}
                        schema={draft}
                        isActive={false}
                        acting={acting === draft.id}
                        onActivate={() => onActivate(draft)}
                        onDelete={() => onDelete(draft)}
                      />
                    ))}
                  </div>
                )}
              </section>
            );
          })}
        </div>
      )}
    </main>
  );
}


function ScheduleRow({
  schema,
  isActive,
  acting,
  onActivate,
  onDelete,
}: {
  schema: FormSchemaAdmin;
  isActive: boolean;
  acting: boolean;
  onActivate: () => void;
  onDelete: () => void;
}) {
  const nbSections = schema.schema?.sections?.length ?? 0;
  const nbFields = schema.schema?.sections?.reduce(
    (sum, s) => sum + (s.fields?.length ?? 0),
    0,
  ) ?? 0;
  return (
    <div
      className={`flex flex-wrap items-center gap-3 rounded-md border p-3 text-sm ${
        isActive
          ? "border-emerald-200 bg-emerald-50/40"
          : "border-line-200 bg-paper-soft"
      }`}
    >
      <div className="flex-1 min-w-[200px]">
        <div className="flex items-center gap-2">
          <span className="font-semibold text-ink-900">{schema.title}</span>
          <span className="rounded-full bg-paper-soft px-2 py-0.5 text-xs text-ink-500">
            v{schema.version}
          </span>
          {isActive && (
            <span className="inline-flex items-center gap-1 rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-700">
              <CheckCircle2 className="h-3 w-3" />
              Actif
            </span>
          )}
        </div>
        <p className="mt-1 text-xs text-ink-500">
          {nbSections} section{nbSections > 1 ? "s" : ""} · {nbFields} champ{nbFields > 1 ? "s" : ""}
          {schema.activated_at &&
            ` · activé le ${new Date(schema.activated_at).toLocaleDateString("fr-FR")}`}
        </p>
      </div>
      <div className="flex shrink-0 gap-2">
        <Link
          href={`/forms/${schema.id}`}
          className={buttonClasses({ variant: "ghost", size: "sm" })}
        >
          {isActive ? <FileEdit className="mr-1 h-3.5 w-3.5" /> : <Edit3 className="mr-1 h-3.5 w-3.5" />}
          {isActive ? "Voir" : "Éditer"}
        </Link>
        {!isActive && (
          <>
            <button
              onClick={onActivate}
              disabled={acting}
              className={buttonClasses({ variant: "primary", size: "sm" })}
            >
              <CheckCircle2 className="mr-1 h-3.5 w-3.5" />
              Activer
            </button>
            <button
              onClick={onDelete}
              disabled={acting}
              className={buttonClasses({ variant: "ghost", size: "sm" })}
            >
              <Trash2 className="mr-1 h-3.5 w-3.5" />
            </button>
          </>
        )}
      </div>
    </div>
  );
}
