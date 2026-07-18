"use client";

import { useEffect, useState } from "react";

import { DataTable, type DataColumn } from "@/components/data-table";
import { adminApi, type ApiError, type AvalisteConsentRow } from "@/lib/api";


function fmtMoney(v: string | number) {
  const n = typeof v === "string" ? Number(v) : v;
  if (!Number.isFinite(n)) return String(v);
  return n.toLocaleString("fr-FR");
}

function fmtDate(iso: string) {
  try {
    return new Date(iso).toLocaleDateString("fr-FR", {
      day: "2-digit",
      month: "short",
      year: "2-digit",
    });
  } catch {
    return iso;
  }
}

type Filter = "all" | "pending" | "accepted" | "refused";


/**
 * Onglet « Avalistes / cautions » — supervision de tous les mandats d'avaliste.
 *
 * Lecture seule côté admin : la décision (accepter / refuser) appartient à
 * l'avaliste depuis son espace membre (Q13, non-rétractable). Ici on visualise
 * qui garantit qui, la caution gelée et l'état.
 */
export default function AvalistePage() {
  const [filter, setFilter] = useState<Filter>("pending");
  const [rows, setRows] = useState<AvalisteConsentRow[]>([]);
  const [counts, setCounts] = useState<Record<string, number>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    adminApi.avaliste
      .list({ statut: filter === "all" ? undefined : filter })
      .then((res) => {
        if (cancelled) return;
        setRows(res.results);
        setCounts(res.counts ?? {});
        setError(null);
      })
      .catch((e) => {
        if (!cancelled) setError((e as ApiError).detail ?? "Chargement impossible.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [filter]);

  const columns: DataColumn<AvalisteConsentRow>[] = [
    {
      key: "demandeur",
      label: "Demandeur",
      text: (r) => `${r.demandeur.prenom} ${r.demandeur.nom} ${r.demandeur.numero_membre}`,
      render: (r) => (
        <div>
          <p className="font-medium text-ink-900">
            {r.demandeur.prenom} {r.demandeur.nom}
          </p>
          <p className="font-mono text-xs text-ink-500">{r.demandeur.numero_membre}</p>
        </div>
      ),
    },
    {
      key: "avaliste",
      label: "Avaliste (garant)",
      text: (r) => `${r.avaliste.prenom} ${r.avaliste.nom} ${r.avaliste.numero_membre}`,
      render: (r) => (
        <div>
          <p className="font-medium text-ink-900">
            {r.avaliste.prenom} {r.avaliste.nom}
          </p>
          <p className="font-mono text-xs text-ink-500">{r.avaliste.numero_membre}</p>
        </div>
      ),
    },
    {
      key: "montant_demande",
      label: "Montant crédit",
      numeric: true,
      align: "right",
      text: (r) => r.loan_request.montant_demande,
      render: (r) => (
        <span className="font-mono text-ink-900">
          {fmtMoney(r.loan_request.montant_demande)} XAF
        </span>
      ),
    },
    {
      key: "montant_gele",
      label: "Caution gelée",
      numeric: true,
      align: "right",
      text: (r) => r.montant_gele,
      render: (r) => (
        <span className="font-mono font-medium text-amber-700">
          {fmtMoney(r.montant_gele)} XAF
        </span>
      ),
    },
    {
      key: "ratio",
      label: "Couverture",
      align: "right",
      text: (r) => r.couverture.ratio,
      render: (r) => <span className="font-mono text-ink-700">×{r.couverture.ratio}</span>,
    },
    {
      key: "statut",
      label: "Statut",
      text: (r) => r.statut_display,
      render: (r) => <StatusBadge statut={r.statut} label={r.statut_display} />,
    },
    {
      key: "date",
      label: "Créé le",
      text: (r) => r.created_at,
      render: (r) => <span className="text-ink-600">{fmtDate(r.created_at)}</span>,
    },
  ];

  return (
    <section className="space-y-6">
      <header>
        <h1 className="font-editorial text-3xl font-medium tracking-tight text-ink-900">
          Avalistes / cautions
        </h1>
        <p className="text-sm text-ink-500">
          Supervision des mandats d&apos;avaliste : qui garantit qui, la caution
          gelée sur l&apos;épargne du garant, et l&apos;état. La décision
          appartient à l&apos;avaliste depuis son espace (acceptation
          définitive, Q13).
        </p>
      </header>

      <FilterTabs value={filter} onChange={setFilter} counts={counts} />

      {error ? (
        <p className="rounded-md border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-800">
          {error}
        </p>
      ) : loading ? (
        <p className="text-ink-600">Chargement…</p>
      ) : (
        <DataTable
          columns={columns}
          rows={rows}
          rowKey={(r) => r.id}
          emptyLabel="Aucun mandat d'avaliste pour ce filtre."
          leftMeta={
            <>
              <span className="font-mono font-medium text-ink-900">{rows.length}</span>
              <span>mandat{rows.length > 1 ? "s" : ""}</span>
            </>
          }
          exportFilename="avalistes-cautions"
          exportTitle="Avalistes / cautions — GATHE Finance"
          exportSubtitle={`Filtre : ${filter}`}
        />
      )}
    </section>
  );
}


function FilterTabs({
  value,
  onChange,
  counts,
}: {
  value: Filter;
  onChange: (v: Filter) => void;
  counts: Record<string, number>;
}) {
  const tabs: Array<{ key: Filter; label: string; count?: number }> = [
    { key: "pending", label: "En attente", count: counts.pending },
    { key: "accepted", label: "Acceptés", count: counts.accepted },
    { key: "refused", label: "Refusés", count: counts.refused },
    { key: "all", label: "Tous" },
  ];
  return (
    <div className="flex flex-wrap gap-2">
      {tabs.map((t) => (
        <button
          key={t.key}
          type="button"
          onClick={() => onChange(t.key)}
          className={`rounded-md px-3 py-1.5 text-sm font-medium transition ${
            value === t.key
              ? "bg-ink-900 text-paper"
              : "border border-line-200 bg-paper text-ink-700 hover:bg-cream"
          }`}
        >
          {t.label}
          {typeof t.count === "number" ? (
            <span className="ml-1.5 opacity-70">({t.count})</span>
          ) : null}
        </button>
      ))}
    </div>
  );
}


function StatusBadge({
  statut,
  label,
}: {
  statut: AvalisteConsentRow["statut"];
  label: string;
}) {
  const map: Record<AvalisteConsentRow["statut"], string> = {
    pending: "bg-ink-100 text-ink-700",
    accepted: "bg-emerald-100 text-emerald-800",
    refused: "bg-red-100 text-red-700",
  };
  return (
    <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${map[statut]}`}>
      {label}
    </span>
  );
}
