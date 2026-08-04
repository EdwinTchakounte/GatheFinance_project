"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Coins, Search, Filter, Layers } from "lucide-react";

import { buttonClasses } from "@gathe/ui";

import { DataTable, type DataColumn } from "@/components/data-table";
import { StatusPill } from "@/components/status-pill";
import { fullName } from "@/lib/name";
import {
  adminApi,
  type ApiError,
  type LenderTranche,
  type LenderPoolSummary,
} from "@/lib/api";

const STATUT_OPTIONS = [
  { v: "disponible", l: "Disponible", color: "text-emerald bg-emerald/10 ring-emerald/30" },
  { v: "engagee", l: "Engagee", color: "text-blue-700 bg-blue-50 ring-blue-200" },
  { v: "liberee", l: "Liberee", color: "text-ink-600 bg-line-100 ring-line-200" },
  { v: "annulee", l: "Annulee", color: "text-terra-700 bg-terra-50/60 ring-terra-400/40" },
  { v: "all", l: "Toutes", color: "" },
] as const;


export default function LenderTranchesPage() {
  return <Inner />;
}

function Inner() {
  const [statut, setStatut] = useState<"disponible" | "engagee" | "liberee" | "annulee" | "all">("disponible");
  const [q, setQ] = useState("");
  const [montantMin, setMontantMin] = useState<string>("");
  const [items, setItems] = useState<LenderTranche[]>([]);
  const [summary, setSummary] = useState<LenderPoolSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [apportBusy, setApportBusy] = useState<number | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  async function handleApport(t: LenderTranche) {
    const ok = window.confirm(
      `Restituer par apport la part de ${fullName(t.member.prenom, t.member.nom)} ` +
        `(${formatXAF(t.montant)} XAF, crédit ${t.engaged_in_loan_dossier ?? ""}) ? ` +
        "Le prêteur sera restitué (capital + intérêts placement) et la coop " +
        "reprend le risque du crédit.",
    );
    if (!ok) return;
    setApportBusy(t.id);
    setNotice(null);
    try {
      const res = await adminApi.lenderTranches.restituteApport(t.id);
      setNotice(
        `Apport effectué — ${formatXAF(res.capital)} XAF restitués (+ ${formatXAF(
          res.interet_placement,
        )} XAF d'intérêts).`,
      );
      await reload();
    } catch (err) {
      setError((err as ApiError).detail ?? "Apport impossible.");
    } finally {
      setApportBusy(null);
    }
  }

  async function reload() {
    setLoading(true);
    setError(null);
    try {
      adminApi.primeCsrf().catch(() => undefined);
      const [list, sum] = await Promise.all([
        adminApi.lenderTranches.list({
          statut,
          q: q.trim() || undefined,
          montant_min: montantMin ? Number(montantMin) : undefined,
        }),
        adminApi.lenderTranches.summary(),
      ]);
      setItems(list.items);
      setSummary(sum);
    } catch (err) {
      const apiErr = err as ApiError;
      setError(apiErr.detail ?? "Chargement impossible.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    reload();
    // eslint-disable-next-line
  }, [statut]);

  const reserveDispo = useMemo(() => {
    if (!summary) return null;
    return {
      n: summary.disponible.n,
      total: Number(summary.disponible.total),
    };
  }, [summary]);

  const columns: DataColumn<LenderTranche>[] = [
    {
      key: "membre",
      label: "Membre",
      locked: true,
      text: (t) => `${fullName(t.member.prenom, t.member.nom)} ${t.member.numero_membre}`,
      render: (t) => (
        <div>
          <p className="font-medium text-ink-900">
            {fullName(t.member.prenom, t.member.nom)}
          </p>
          <p className="font-mono text-xs text-ink-600">{t.member.numero_membre}</p>
        </div>
      ),
    },
    {
      key: "montant",
      label: "Montant",
      numeric: true,
      align: "right",
      text: (t) => t.montant,
      render: (t) => (
        <span className="font-mono font-semibold tabular-nums text-ink-900">
          {formatXAF(t.montant)} XAF
        </span>
      ),
    },
    {
      key: "statut",
      label: "Statut",
      text: (t) => t.statut_display,
      render: (t) => {
        const opt = STATUT_OPTIONS.find((o) => o.v === t.statut);
        return (
          <StatusPill statut={t.statut} label={t.statut_display} />
        );
      },
    },
    {
      key: "engage",
      label: "Engagé dans",
      text: (t) => t.engaged_in_loan_dossier || "",
      render: (t) =>
        t.engaged_in_loan_dossier ? (
          <span className="font-mono text-sm text-ink-900">
            {t.engaged_in_loan_dossier}
          </span>
        ) : (
          <span className="text-xs text-ink-400"></span>
        ),
    },
    {
      key: "date",
      label: "Date dépôt",
      defaultVisible: false,
      text: (t) =>
        new Date(t.created_at).toLocaleDateString("fr-FR", {
          day: "2-digit",
          month: "short",
          year: "2-digit",
        }),
    },
    {
      key: "action",
      label: "Action",
      text: () => "",
      render: (t) =>
        t.statut === "engagee" ? (
          <button
            type="button"
            disabled={apportBusy !== null}
            onClick={() => handleApport(t)}
            className={buttonClasses({ variant: "secondary", size: "sm" })}
            title="Restituer ce prêteur par apport coop (crédit non soldé)"
          >
            {apportBusy === t.id ? "…" : "Restituer (apport)"}
          </button>
        ) : (
          <span className="text-xs text-ink-400">—</span>
        ),
    },
  ];

  return (
    <div className="space-y-6">
      <header className="mb-8">
        <p className="font-display text-[0.7rem] font-semibold uppercase tracking-[0.18em] text-terra-600">
          Épargne prêteur
        </p>
        <h1 className="mt-2 font-editorial text-3xl font-medium text-ink-900">
          Pool de tranches preteur
        </h1>
        <p className="mt-1 text-sm text-ink-600">
          Visualise les tranches d'épargne placement disponibles pour financer les crédits.
        </p>
      </header>

      {/* Guide — comment construire le funding d'un crédit par tranches. */}
      <div className="mb-6 flex items-start gap-3 rounded-md border border-blue-200 bg-blue-50/60 p-4">
        <Layers className="mt-0.5 size-5 shrink-0 text-blue-700" aria-hidden="true" />
        <div className="text-sm text-ink-700">
          <p className="font-medium text-ink-900">Construire un crédit par tranches</p>
          <p className="mt-0.5">
            Cette page présente la réserve mobilisable. Pour <strong>financer un crédit</strong>,
            ouvrez sa fiche dans{" "}
            <Link href="/loans" className="font-medium text-blue-700 hover:underline">
              Crédits
            </Link>{" "}
            puis cliquez sur <strong>« Funding »</strong> : vous sélectionnez les tranches
            à engager, le prêteur est notifié et reçoit automatiquement sa rémunération
            proportionnelle à sa mise (taux prêteur configurable).
          </p>
        </div>
      </div>

      {/* Summary cards */}
      {summary ? (
        <section className="mb-8 grid grid-cols-1 gap-4 md:grid-cols-4">
          <SummaryCard
            label="Reserve mobilisable"
            value={`${formatXAF(summary.disponible.total)} XAF`}
            sub={`${summary.disponible.n} tranches`}
            accent="emerald"
            icon={<Coins className="size-5 text-emerald" aria-hidden="true" />}
          />
          <SummaryCard
            label="Capital engage"
            value={`${formatXAF(summary.engagee.total)} XAF`}
            sub={`${summary.engagee.n} tranches en credit`}
            accent="blue"
            icon={<Layers className="size-5 text-blue-700" aria-hidden="true" />}
          />
          <SummaryCard
            label="Capital libere"
            value={`${formatXAF(summary.liberee.total)} XAF`}
            sub={`${summary.liberee.n} tranches (credits cloturés)`}
            accent="neutral"
            icon={<Layers className="size-5 text-ink-500" aria-hidden="true" />}
          />
          <SummaryCard
            label="Annulees"
            value={`${formatXAF(summary.annulee.total)} XAF`}
            sub={`${summary.annulee.n} tranches`}
            accent="terra"
            icon={<Layers className="size-5 text-terra-700" aria-hidden="true" />}
          />
        </section>
      ) : null}

      {/* Filters */}
      <section className="mb-5 rounded-md border border-line-200 bg-paper p-4">
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-1 rounded-md border border-line-200 bg-white p-1">
            {STATUT_OPTIONS.map((opt) => (
              <button
                key={opt.v}
                type="button"
                onClick={() => setStatut(opt.v)}
                className={[
                  "rounded px-3 py-1.5 text-xs font-medium transition-colors",
                  statut === opt.v ? "bg-blue-700 text-white" : "text-ink-700 hover:text-blue-700",
                ].join(" ")}
              >
                {opt.l}
              </button>
            ))}
          </div>
          <div className="relative flex-1 min-w-[16rem]">
            <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-ink-400" aria-hidden="true" />
            <input
              type="text"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && reload()}
              placeholder="Recherche numero membre, nom, prenom"
              className="w-full rounded-md border border-line-200 bg-white py-2 pl-9 pr-3 text-sm text-ink-900 placeholder:text-ink-400 focus:border-blue-700 focus:outline-none"
            />
          </div>
          <div className="flex items-center gap-2">
            <Filter className="size-4 text-ink-400" aria-hidden="true" />
            <input
              type="number"
              value={montantMin}
              onChange={(e) => setMontantMin(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && reload()}
              placeholder="Montant min XAF"
              className="w-40 rounded-md border border-line-200 bg-white px-3 py-2 text-sm text-ink-900 placeholder:text-ink-400 focus:border-blue-700 focus:outline-none"
            />
          </div>
          <button
            type="button"
            onClick={reload}
            className={buttonClasses({ variant: "primary", size: "sm" })}
          >
            Appliquer
          </button>
        </div>
        {reserveDispo && statut === "disponible" ? (
          <p className="mt-3 text-xs text-ink-600">
            Reserve actuellement libre d'engagement :{" "}
            <strong className="text-emerald">{formatXAF(String(reserveDispo.total))} XAF</strong>
            {" "}repartie sur <strong>{reserveDispo.n}</strong> tranches.
          </p>
        ) : null}
      </section>

      {error ? (
        <div className="mb-5 rounded-md border border-terra-400/40 bg-terra-50/60 px-4 py-2.5 text-sm text-terra-700">
          {error}
        </div>
      ) : null}

      {notice ? (
        <div className="mb-5 flex items-center justify-between gap-3 rounded-md border border-emerald-300 bg-emerald-50 px-4 py-2.5 text-sm text-emerald-800">
          <span>{notice}</span>
          <button type="button" onClick={() => setNotice(null)} className="text-emerald-700 hover:underline">
            ✕
          </button>
        </div>
      ) : null}

      {loading ? (
        <p className="text-ink-600">Chargement...</p>
      ) : (
        <DataTable
          columns={columns}
          rows={items}
          rowKey={(t) => t.id}
          emptyLabel="Aucune tranche pour ce filtre."
          exportFilename="tranches-preteur"
          exportTitle="Pool de tranches prêteur — GATHE Finance"
          exportSubtitle={`Filtre : ${statut}`}
        />
      )}
    </div>
  );
}


function SummaryCard({
  label,
  value,
  sub,
  accent,
  icon,
}: {
  label: string;
  value: string;
  sub: string;
  accent: "emerald" | "blue" | "neutral" | "terra";
  icon: React.ReactNode;
}) {
  const borderClass = {
    emerald: "border-emerald/30 bg-emerald/5",
    blue: "border-blue-300 bg-blue-50/50",
    neutral: "border-line-200 bg-paper",
    terra: "border-terra-400/40 bg-terra-50/40",
  }[accent];
  return (
    <div className={`rounded-md border p-4 ${borderClass}`}>
      <div className="flex items-center gap-2">
        {icon}
        <p className="text-[0.7rem] font-medium uppercase tracking-wide text-ink-600">{label}</p>
      </div>
      <p className="mt-2 font-mono text-xl font-semibold text-ink-900">{value}</p>
      <p className="mt-0.5 text-xs text-ink-600">{sub}</p>
    </div>
  );
}


function formatXAF(value: string | number): string {
  const n = typeof value === "string" ? Number(value) : value;
  if (Number.isNaN(n)) return "0";
  return new Intl.NumberFormat("fr-FR").format(Math.round(n));
}
