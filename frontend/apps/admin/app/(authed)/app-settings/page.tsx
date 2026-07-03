"use client";

import { useEffect, useMemo, useState } from "react";
import { Check, Loader2, RotateCcw, Search } from "lucide-react";

import {
  adminApi,
  type ApiError,
  type AppSettingGroup,
  type AppSettingRow,
  type AppSettingsResponse,
} from "@/lib/api";


export default function AppSettingsPage() {
  const [data, setData] = useState<AppSettingsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState("");

  async function reload() {
    setLoading(true);
    setError(null);
    try {
      setData(await adminApi.appSettings.list());
    } catch (err) {
      setError((err as ApiError).detail ?? "Chargement impossible.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Replace the row by its updated copy returned by the PATCH.
  function patchRow(updated: AppSettingRow) {
    setData((prev) =>
      prev
        ? {
            ...prev,
            settings: prev.settings.map((s) =>
              s.key === updated.key ? updated : s,
            ),
          }
        : prev,
    );
  }

  // Group settings by group key, in the order returned by the server.
  const grouped = useMemo(() => {
    if (!data) return [];
    const q = filter.trim().toLowerCase();
    return data.groups
      .map((g) => ({
        group: g,
        rows: data.settings.filter(
          (s) =>
            s.group === g.key &&
            (!q ||
              s.key.toLowerCase().includes(q) ||
              s.label.toLowerCase().includes(q) ||
              s.description.toLowerCase().includes(q)),
        ),
      }))
      .filter((b) => b.rows.length > 0);
  }, [data, filter]);

  return (
    <div className="px-8 py-8 lg:px-12 lg:py-10">
      <header className="mb-6">
        <p className="font-display text-[0.7rem] font-semibold uppercase tracking-[0.18em] text-terra-600">
          Configuration
        </p>
        <h1 className="mt-2 font-editorial text-3xl font-medium text-ink-900">
          Règles &amp; paramètres
        </h1>
        <p className="mt-1 max-w-2xl text-sm text-ink-600">
          Toutes les règles modifiables sans déploiement : ancienneté,
          éligibilité au crédit, garanties, escalade judiciaire, campagnes,
          etc. Chaque modification est immédiate et tracée dans le journal
          d&apos;audit.
        </p>
      </header>

      {/* Search */}
      <div className="mb-5 flex items-center gap-2 rounded-md border border-line-200 bg-paper px-3 py-2">
        <Search className="size-4 shrink-0 text-ink-500" aria-hidden="true" />
        <input
          type="text"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder="Filtrer par clé, libellé ou description…"
          className="flex-1 bg-transparent text-sm text-ink-900 outline-none placeholder:text-ink-400"
        />
        {filter ? (
          <button
            type="button"
            onClick={() => setFilter("")}
            className="text-xs text-ink-500 hover:text-ink-700"
          >
            Effacer
          </button>
        ) : null}
      </div>

      {error ? (
        <div className="mb-5 rounded-md border border-terra-400/40 bg-terra-50/60 px-4 py-2.5 text-sm text-terra-700">
          {error}
        </div>
      ) : null}

      {loading ? (
        <p className="text-ink-600">Chargement…</p>
      ) : grouped.length === 0 ? (
        <p className="text-ink-600">Aucun paramètre ne correspond.</p>
      ) : (
        <div className="space-y-8">
          {grouped.map(({ group, rows }) => (
            <GroupSection key={group.key} group={group} rows={rows} onPatched={patchRow} />
          ))}
        </div>
      )}
    </div>
  );
}


function GroupSection({
  group,
  rows,
  onPatched,
}: {
  group: AppSettingGroup;
  rows: AppSettingRow[];
  onPatched: (row: AppSettingRow) => void;
}) {
  return (
    <section>
      <h2 className="mb-3 font-display text-xs font-semibold uppercase tracking-wider text-ink-500">
        {group.label}
      </h2>
      <div className="overflow-hidden rounded-md border border-line-200 bg-paper">
        <table className="table-admin">
          <thead>
            <tr>
              <th className="w-1/3">Paramètre</th>
              <th>Description</th>
              <th className="w-64">Valeur</th>
              <th className="w-px" />
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <SettingRow key={row.key} row={row} onPatched={onPatched} />
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}


function SettingRow({
  row,
  onPatched,
}: {
  row: AppSettingRow;
  onPatched: (row: AppSettingRow) => void;
}) {
  const [draft, setDraft] = useState<string>(row.value);
  const [saving, setSaving] = useState(false);
  const [savedAt, setSavedAt] = useState<number | null>(null);
  const [rowError, setRowError] = useState<string | null>(null);

  // Reset draft when server-side value changes (rebuild from list reload).
  useEffect(() => {
    setDraft(row.value);
  }, [row.value]);

  const dirty = draft !== row.value;

  async function save(nextValue: string | boolean) {
    setSaving(true);
    setRowError(null);
    try {
      const updated = await adminApi.appSettings.update(row.key, nextValue);
      onPatched(updated);
      setSavedAt(Date.now());
    } catch (err) {
      setRowError((err as ApiError).detail ?? "Erreur d'enregistrement.");
    } finally {
      setSaving(false);
    }
  }

  function resetToDefault() {
    void save(row.default);
  }

  return (
    <tr>
      <td>
        <div className="font-medium text-ink-900">{row.label}</div>
        <div className="font-mono text-[11px] text-ink-500">{row.key}</div>
      </td>
      <td className="text-sm text-ink-600">{row.description}</td>
      <td>
        <div className="flex items-center gap-2">
          {row.type === "bool" ? (
            <BoolField
              value={String(draft).toLowerCase() === "true"}
              onChange={(v) => save(v)}
              disabled={saving}
            />
          ) : row.type === "enum" ? (
            <select
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              disabled={saving}
              className="w-full rounded-md border border-line-300 bg-paper px-2 py-1.5 text-sm text-ink-900 focus:border-blue-700 focus:outline-none"
            >
              {(row.choices ?? []).map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          ) : (
            <input
              type={row.type === "int" || row.type === "decimal" ? "text" : "text"}
              inputMode={
                row.type === "int"
                  ? "numeric"
                  : row.type === "decimal"
                    ? "decimal"
                    : undefined
              }
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              disabled={saving}
              className="w-full rounded-md border border-line-300 bg-paper px-2 py-1.5 font-mono text-sm text-ink-900 focus:border-blue-700 focus:outline-none"
            />
          )}
          {row.type !== "bool" && dirty ? (
            <button
              type="button"
              onClick={() => save(draft)}
              disabled={saving}
              className="rounded-md bg-blue-700 px-3 py-1.5 text-xs font-medium text-white hover:bg-blue-800 disabled:opacity-50"
            >
              {saving ? <Loader2 className="size-3.5 animate-spin" /> : "OK"}
            </button>
          ) : null}
        </div>
        {rowError ? (
          <p className="mt-1 text-xs text-terra-700">{rowError}</p>
        ) : null}
        {savedAt && !rowError ? (
          <p className="mt-1 inline-flex items-center gap-1 text-xs text-emerald-700">
            <Check className="size-3" /> Enregistré
          </p>
        ) : null}
      </td>
      <td className="whitespace-nowrap text-right text-xs text-ink-500">
        {row.is_admin_edited ? (
          <button
            type="button"
            onClick={resetToDefault}
            disabled={saving}
            className="inline-flex items-center gap-1 text-ink-500 hover:text-blue-700"
            title={`Restaurer le défaut : ${row.default}`}
          >
            <RotateCcw className="size-3" /> Défaut
          </button>
        ) : (
          <span className="text-ink-400">par défaut</span>
        )}
      </td>
    </tr>
  );
}


function BoolField({
  value,
  onChange,
  disabled,
}: {
  value: boolean;
  onChange: (v: boolean) => void;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={value}
      onClick={() => onChange(!value)}
      disabled={disabled}
      className={[
        "relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition-colors",
        value ? "bg-emerald-600" : "bg-line-300",
        disabled ? "opacity-50" : "",
      ].join(" ")}
    >
      <span
        className={[
          "inline-block size-5 rounded-full bg-white shadow transition-transform",
          value ? "translate-x-5" : "translate-x-0.5",
        ].join(" ")}
      />
    </button>
  );
}
