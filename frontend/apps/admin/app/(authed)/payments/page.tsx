"use client";

import { useEffect, useMemo, useState } from "react";
import { Search } from "lucide-react";

import { ExportMenu } from "@/components/export-menu";
import { Pagination } from "@/components/pagination";
import type { ExportColumn } from "@/lib/export";
import { adminApi, type ApiError, type PaymentRow } from "@/lib/api";


type StatutFilter = "" | "en_attente" | "valide" | "rejete" | "annule";
type TypeFilter =
  | ""
  | "epargne"
  | "frais_adhesion"
  | "frais_inscription"
  | "frais_demande_credit"
  | "frais_reconduction"
  | "frais_carnet"
  | "remboursement";


const paymentsExportColumns: ExportColumn<PaymentRow>[] = [
  { key: "id", label: "ID", value: (r) => r.id },
  {
    key: "membre",
    label: "Membre",
    value: (r) => `${r.member.prenom} ${r.member.nom}`,
  },
  {
    key: "numero_membre",
    label: "N° membre",
    value: (r) => r.member.numero_membre,
  },
  { key: "type", label: "Type", value: (r) => r.type_display },
  { key: "montant", label: "Montant", value: (r) => r.montant },
  { key: "source", label: "Source", value: (r) => r.source },
  { key: "statut", label: "Statut", value: (r) => r.statut_display },
  { key: "ref", label: "Référence", value: (r) => r.reference_externe },
  { key: "provider", label: "Provider", value: (r) => r.provider_code },
  {
    key: "nb_jours",
    label: "Jours couverts",
    value: (r) => r.nb_jours_couverts ?? "",
  },
  { key: "versement", label: "Versement", value: (r) => r.date_versement },
  {
    key: "validation",
    label: "Validation",
    value: (r) => r.date_validation ?? "",
  },
  { key: "motif_rejet", label: "Motif rejet", value: (r) => r.motif_rejet },
];


export default function PaymentsPage() {
  return (
    
      <Inner />
    
  );
}


function Inner() {
  const [statut, setStatut] = useState<StatutFilter>("");
  const [typeFilter, setTypeFilter] = useState<TypeFilter>("");
  const [q, setQ] = useState("");
  const [items, setItems] = useState<PaymentRow[]>([]);
  const [count, setCount] = useState(0);
  const [limit, setLimit] = useState(25);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function reload() {
    setLoading(true);
    setError(null);
    try {
      const res = await adminApi.payments.list({
        statut: statut || undefined,
        type: typeFilter || undefined,
        q: q.trim() || undefined,
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
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [statut, typeFilter, limit, offset]);

  const totalValide = useMemo(
    () =>
      items
        .filter((p) => p.statut === "valide")
        .reduce((acc, p) => acc + Number(p.montant || 0), 0),
    [items],
  );

  return (
    <div className="px-8 py-8 lg:px-12 lg:py-10">
      <header className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="font-display text-[0.7rem] font-semibold uppercase tracking-[0.18em] text-terra-600">
            Paiements
          </p>
          <h1 className="mt-2 font-editorial text-3xl font-medium text-ink-900">
            Suivi des paiements
          </h1>
          <p className="mt-1 text-sm text-ink-600">
            Tous les versements traversant la plateforme (Mobile Money, espèces, virements).
          </p>
        </div>

        <div className="flex items-center gap-3 text-sm text-ink-600">
          <span className="font-mono text-ink-900 font-medium">{count}</span>
          <span>paiement{count > 1 ? "s" : ""}</span>
          <span className="text-ink-400">·</span>
          <span className="font-mono text-emerald font-medium">
            {totalValide.toLocaleString("fr-FR")}
          </span>
          <span>XAF validés (vue actuelle)</span>
          <ExportMenu
            filenamePrefix="paiements"
            title="Suivi des paiements — Gathé Finance"
            subtitle={[
              statut && `statut : ${statut}`,
              typeFilter && `type : ${typeFilter}`,
              q && `recherche : ${q}`,
            ]
              .filter(Boolean)
              .join(" · ") || "tous"}
            columns={paymentsExportColumns}
            rows={items}
          />
        </div>
      </header>

      <div className="mb-5 grid grid-cols-1 gap-3 md:grid-cols-[auto_auto_1fr]">
        <FilterPills
          label="Statut"
          value={statut}
          onChange={(v) => {
            setStatut(v as StatutFilter);
            setOffset(0);
          }}
          options={[
            { v: "", l: "Tous" },
            { v: "en_attente", l: "En attente" },
            { v: "valide", l: "Validés" },
            { v: "rejete", l: "Rejetés" },
            { v: "annule", l: "Annulés" },
          ]}
        />
        <FilterPills
          label="Type"
          value={typeFilter}
          onChange={(v) => {
            setTypeFilter(v as TypeFilter);
            setOffset(0);
          }}
          options={[
            { v: "", l: "Tous" },
            { v: "epargne", l: "Épargne" },
            { v: "remboursement", l: "Remboursement" },
            { v: "frais_adhesion", l: "Adhésion" },
            { v: "frais_demande_credit", l: "Frais crédit" },
            { v: "frais_carnet", l: "Carnet" },
          ]}
        />
        <form
          onSubmit={(e) => {
            e.preventDefault();
            setOffset(0);
            reload();
          }}
          className="flex items-center gap-2"
        >
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-ink-400" />
            <input
              type="search"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Recherche (n° membre, nom, référence Tara…)"
              className="w-full rounded-md border border-line-200 bg-paper py-2 pl-9 pr-3 text-sm placeholder:text-ink-400 focus:border-blue-700 focus:outline-none focus:ring-1 focus:ring-blue-700"
            />
          </div>
          <button
            type="submit"
            className="rounded-md border border-line-200 bg-paper px-3 py-2 text-xs font-medium text-ink-700 hover:border-blue-700 hover:text-blue-700"
          >
            Rechercher
          </button>
        </form>
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
          Aucun paiement ne correspond à ces filtres.
        </p>
      ) : (
        <div className="overflow-hidden rounded-md border border-line-200 bg-paper">
          <table className="table-admin">
            <thead>
              <tr>
                <th>Date</th>
                <th>Membre</th>
                <th>Type</th>
                <th className="text-right">Montant</th>
                <th>Référence</th>
                <th>Statut</th>
              </tr>
            </thead>
            <tbody>
              {items.map((p) => (
                <tr key={p.id}>
                  <td className="whitespace-nowrap text-sm">
                    <p className="text-ink-900">
                      {new Date(p.date_versement).toLocaleDateString("fr-FR", {
                        day: "2-digit",
                        month: "short",
                        year: "2-digit",
                      })}
                    </p>
                    <p className="font-mono text-xs text-ink-500">
                      {new Date(p.date_versement).toLocaleTimeString("fr-FR", {
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </p>
                  </td>
                  <td>
                    <p className="font-medium text-ink-900">
                      {p.member.prenom} {p.member.nom}
                    </p>
                    <p className="font-mono text-xs text-ink-500">
                      {p.member.numero_membre}
                    </p>
                  </td>
                  <td className="text-sm text-ink-700">
                    {p.type_display}
                    {/* Refonte 2026 — multi-jours pré-payé sur la collecte. */}
                    {p.type === "epargne" &&
                    typeof p.nb_jours_couverts === "number" &&
                    p.nb_jours_couverts > 1 ? (
                      <span
                        className="ml-1 inline-flex rounded-full bg-amber-100 px-1.5 py-0.5 text-[10px] font-medium text-amber-700"
                        title={`Versement pour ${p.nb_jours_couverts} jours`}
                      >
                        × {p.nb_jours_couverts} j
                      </span>
                    ) : null}
                  </td>
                  <td className="text-right font-mono text-sm text-ink-900">
                    {Number(p.montant).toLocaleString("fr-FR")}
                    <span className="ml-1 text-xs text-ink-500">XAF</span>
                  </td>
                  <td className="font-mono text-xs text-ink-600">
                    {p.reference_externe || (
                      <span className="text-ink-400">—</span>
                    )}
                    <p className="text-[10px] uppercase tracking-wide text-ink-400">
                      {p.provider_code}
                    </p>
                  </td>
                  <td>
                    <span
                      className={
                        "pill " +
                        (p.statut === "valide"
                          ? "pill-success"
                          : p.statut === "en_attente"
                            ? "pill-warning"
                            : p.statut === "rejete"
                              ? "pill-danger"
                              : "pill-muted")
                      }
                    >
                      {p.statut_display}
                    </span>
                    {p.statut === "rejete" && p.motif_rejet ? (
                      <p className="mt-1 max-w-[14rem] text-xs text-terra-700">
                        {p.motif_rejet}
                      </p>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {!loading && count > 0 ? (
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
      ) : null}
    </div>
  );
}


function FilterPills<T extends string>({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: T;
  onChange: (v: T) => void;
  options: { v: T; l: string }[];
}) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-[0.65rem] font-semibold uppercase tracking-wider text-ink-500">
        {label}
      </span>
      <div className="flex items-center gap-1 rounded-md border border-line-200 bg-paper p-1">
        {options.map((opt) => (
          <button
            key={opt.v || "all"}
            type="button"
            onClick={() => onChange(opt.v)}
            className={[
              "rounded px-2.5 py-1 text-xs font-medium transition-colors",
              value === opt.v
                ? "bg-blue-700 text-white"
                : "text-ink-700 hover:text-blue-700",
            ].join(" ")}
          >
            {opt.l}
          </button>
        ))}
      </div>
    </div>
  );
}
