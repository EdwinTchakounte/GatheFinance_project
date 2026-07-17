"use client";

import { useEffect, useMemo, useState } from "react";
import { Search, RotateCcw, Eye } from "lucide-react";

import { Pagination } from "@/components/pagination";
import {
  adminApi,
  type ApiError,
  type AuditLogFacets,
  type AuditLogRow,
} from "@/lib/api";


const DEFAULT_LIMIT = 25;


export default function AuditPage() {
  return <Inner />;
}


function Inner() {
  // Filtres
  const [q, setQ] = useState("");
  const [action, setAction] = useState("");
  const [entiteType, setEntiteType] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  // Pagination
  const [limit, setLimit] = useState(DEFAULT_LIMIT);
  const [offset, setOffset] = useState(0);

  // Data
  const [items, setItems] = useState<AuditLogRow[]>([]);
  const [count, setCount] = useState(0);
  const [facets, setFacets] = useState<AuditLogFacets>({
    actions: [],
    entite_types: [],
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<AuditLogRow | null>(null);

  async function reload() {
    setLoading(true);
    setError(null);
    try {
      const res = await adminApi.audit.list({
        q: q.trim() || undefined,
        action: action || undefined,
        entite_type: entiteType || undefined,
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
        limit,
        offset,
      });
      setItems(res.results);
      setCount(res.count);
    } catch (err) {
      const apiErr = err as ApiError;
      setError(apiErr.detail ?? "Chargement impossible.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    adminApi.audit
      .facets()
      .then(setFacets)
      .catch(() => {
        /* facettes optionnelles */
      });
  }, []);

  // Recharge à chaque changement de filtre/pagination (sauf q : géré par submit).
  useEffect(() => {
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [action, entiteType, dateFrom, dateTo, limit, offset]);

  function resetFilters() {
    setQ("");
    setAction("");
    setEntiteType("");
    setDateFrom("");
    setDateTo("");
    setOffset(0);
  }

  const activeFilterCount = useMemo(
    () =>
      [q, action, entiteType, dateFrom, dateTo].filter(
        (v) => v && v.trim() !== "",
      ).length,
    [q, action, entiteType, dateFrom, dateTo],
  );

  return (
    <div className="px-8 py-8 lg:px-12 lg:py-10">
      <header className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="font-display text-[0.7rem] font-semibold uppercase tracking-[0.18em] text-terra-600">
            Audit
          </p>
          <h1 className="mt-2 font-editorial text-3xl font-medium text-ink-900">
            Journal d'audit
          </h1>
          <p className="mt-1 text-sm text-ink-600">
            Toutes les actions tracées sur la plateforme — mutations API
            automatiques et événements métier (décisions, validations,
            changements de configuration).
          </p>
        </div>

        <div className="flex items-center gap-3 text-sm text-ink-600">
          <span className="font-mono text-ink-900 font-medium">{count}</span>
          <span>entrée{count > 1 ? "s" : ""}</span>
          {activeFilterCount > 0 ? (
            <button
              type="button"
              onClick={resetFilters}
              className="inline-flex items-center gap-1.5 rounded-md border border-line-200 bg-paper px-2.5 py-1.5 text-xs font-medium text-ink-700 hover:border-blue-700 hover:text-blue-700"
            >
              <RotateCcw className="size-3.5" aria-hidden="true" />
              Réinitialiser ({activeFilterCount})
            </button>
          ) : null}
        </div>
      </header>

      {/* Barre de filtres */}
      <div className="mb-5 grid grid-cols-1 gap-3 md:grid-cols-[1fr_auto_auto_auto_auto]">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            setOffset(0);
            reload();
          }}
          className="relative"
        >
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-ink-400" />
          <input
            type="search"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Recherche (action, type d'entité, email auteur)…"
            className="w-full rounded-md border border-line-200 bg-paper py-2 pl-9 pr-3 text-sm placeholder:text-ink-400 focus:border-blue-700 focus:outline-none focus:ring-1 focus:ring-blue-700"
          />
        </form>

        <select
          value={action}
          onChange={(e) => {
            setAction(e.target.value);
            setOffset(0);
          }}
          className="rounded-md border border-line-200 bg-paper px-3 py-2 text-sm text-ink-900 focus:border-blue-700 focus:outline-none focus:ring-1 focus:ring-blue-700"
        >
          <option value="">Toutes les actions</option>
          {facets.actions.map((a) => (
            <option key={a} value={a}>
              {a}
            </option>
          ))}
        </select>

        <select
          value={entiteType}
          onChange={(e) => {
            setEntiteType(e.target.value);
            setOffset(0);
          }}
          className="rounded-md border border-line-200 bg-paper px-3 py-2 text-sm text-ink-900 focus:border-blue-700 focus:outline-none focus:ring-1 focus:ring-blue-700"
        >
          <option value="">Tous les types</option>
          {facets.entite_types.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>

        <input
          type="date"
          value={dateFrom}
          onChange={(e) => {
            setDateFrom(e.target.value);
            setOffset(0);
          }}
          className="rounded-md border border-line-200 bg-paper px-3 py-2 text-sm text-ink-900 focus:border-blue-700 focus:outline-none focus:ring-1 focus:ring-blue-700"
          aria-label="Depuis"
        />
        <input
          type="date"
          value={dateTo}
          onChange={(e) => {
            setDateTo(e.target.value);
            setOffset(0);
          }}
          className="rounded-md border border-line-200 bg-paper px-3 py-2 text-sm text-ink-900 focus:border-blue-700 focus:outline-none focus:ring-1 focus:ring-blue-700"
          aria-label="Jusqu'à"
        />
      </div>

      {error ? (
        <div className="mb-5 rounded-md border border-terra-400/40 bg-terra-50/60 px-4 py-2.5 text-sm text-terra-700">
          {error}
        </div>
      ) : null}

      {loading ? (
        <p className="text-ink-600">Chargement…</p>
      ) : items.length === 0 ? (
        <p className="rounded-md border border-dashed border-line-200 bg-paper/70 p-12 text-center text-sm text-ink-600">
          Aucune entrée ne correspond à ces filtres.
        </p>
      ) : (
        <div className="overflow-hidden rounded-md border border-line-200 bg-paper">
          <table className="table-admin">
            <thead>
              <tr>
                <th>Date</th>
                <th>Auteur</th>
                <th>Action</th>
                <th>Cible</th>
                <th>IP</th>
                <th className="text-right">Détails</th>
              </tr>
            </thead>
            <tbody>
              {items.map((row) => (
                <tr key={row.id}>
                  <td className="whitespace-nowrap text-sm">
                    <p className="text-ink-900">
                      {new Date(row.created_at).toLocaleDateString("fr-FR", {
                        day: "2-digit",
                        month: "short",
                        year: "2-digit",
                      })}
                    </p>
                    <p className="font-mono text-xs text-ink-500">
                      {new Date(row.created_at).toLocaleTimeString("fr-FR", {
                        hour: "2-digit",
                        minute: "2-digit",
                        second: "2-digit",
                      })}
                    </p>
                  </td>
                  <td>
                    {row.user ? (
                      <>
                        <p className="font-medium text-ink-900">
                          {row.user.full_name}
                        </p>
                        <p className="font-mono text-xs text-ink-500">
                          {row.user.email}
                          {row.user.is_superuser ? (
                            <span className="ml-1 rounded bg-blue-700/10 px-1 py-0.5 text-[10px] font-medium text-blue-700">
                              SUPER
                            </span>
                          ) : row.user.is_staff ? (
                            <span className="ml-1 rounded bg-emerald/10 px-1 py-0.5 text-[10px] font-medium text-emerald">
                              STAFF
                            </span>
                          ) : null}
                        </p>
                      </>
                    ) : (
                      <p className="text-xs italic text-ink-500">
                        Système / cron
                      </p>
                    )}
                  </td>
                  <td className="font-mono text-xs text-ink-700">
                    {row.action}
                  </td>
                  <td className="text-sm text-ink-700">
                    {row.entite_type ? (
                      <>
                        <span className="font-medium">{row.entite_type}</span>
                        {row.entite_id != null ? (
                          <span className="ml-1 font-mono text-xs text-ink-500">
                            #{row.entite_id}
                          </span>
                        ) : null}
                      </>
                    ) : null}
                  </td>
                  <td className="font-mono text-xs text-ink-600">
                    {row.ip || null}
                  </td>
                  <td className="text-right">
                    {Object.keys(row.details_json || {}).length > 0 ? (
                      <button
                        type="button"
                        onClick={() => setSelected(row)}
                        className="inline-flex items-center gap-1 rounded-md border border-line-200 bg-paper px-2 py-1 text-xs font-medium text-ink-700 hover:border-blue-700 hover:text-blue-700"
                      >
                        <Eye className="size-3.5" aria-hidden="true" />
                        Voir
                      </button>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          <Pagination
            count={count}
            limit={limit}
            offset={offset}
            onChange={setOffset}
            onLimitChange={(v) => {
              setLimit(v);
              setOffset(0);
            }}
          />
        </div>
      )}

      {/* Modal détails */}
      {selected ? (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-ink-900/40 p-4"
          onClick={() => setSelected(null)}
        >
          <div
            className="max-h-[80vh] w-full max-w-2xl overflow-hidden rounded-lg border border-line-200 bg-paper shadow-lg"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between border-b border-line-200 px-5 py-3">
              <div>
                <p className="font-mono text-xs text-ink-500">
                  Entrée #{selected.id}
                </p>
                <h2 className="font-editorial text-lg font-medium text-ink-900">
                  {selected.action}
                </h2>
              </div>
              <button
                type="button"
                onClick={() => setSelected(null)}
                className="rounded-md border border-line-200 bg-paper px-3 py-1.5 text-xs font-medium text-ink-700 hover:border-blue-700 hover:text-blue-700"
              >
                Fermer
              </button>
            </div>
            <div className="max-h-[60vh] overflow-y-auto px-5 py-4">
              <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-sm">
                <dt className="font-medium text-ink-700">Auteur</dt>
                <dd className="text-ink-900">
                  {selected.user
                    ? `${selected.user.full_name} · ${selected.user.email}`
                    : "Système / cron"}
                </dd>
                <dt className="font-medium text-ink-700">Cible</dt>
                <dd className="text-ink-900">
                  {selected.entite_type || ""}
                  {selected.entite_id != null ? ` #${selected.entite_id}` : ""}
                </dd>
                <dt className="font-medium text-ink-700">IP</dt>
                <dd className="font-mono text-ink-900">
                  {selected.ip || ""}
                </dd>
                <dt className="font-medium text-ink-700">User-Agent</dt>
                <dd className="break-all font-mono text-xs text-ink-700">
                  {selected.user_agent || ""}
                </dd>
                <dt className="font-medium text-ink-700">Horodatage</dt>
                <dd className="font-mono text-ink-900">
                  {new Date(selected.created_at).toLocaleString("fr-FR")}
                </dd>
              </dl>
              <div className="mt-4">
                <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-ink-500">
                  Détails
                </p>
                <pre className="overflow-x-auto rounded-md bg-cream p-3 text-xs leading-relaxed text-ink-900">
                  {JSON.stringify(selected.details_json, null, 2)}
                </pre>
              </div>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
