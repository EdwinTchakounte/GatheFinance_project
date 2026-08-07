"use client";

import { useEffect, useMemo, useState } from "react";
import { Banknote, PiggyBank, RefreshCw, Smartphone } from "lucide-react";

import {
  adminApi,
  type ApiError,
  type CollecteEomRow,
} from "@/lib/api";
import { PageHeader } from "@/components/page-header";


function fmtXAF(v: string): string {
  const n = Number(v ?? 0);
  return Number.isFinite(n) ? n.toLocaleString("fr-FR") : "0";
}


export default function CollectePreferencesPage() {
  const [rows, setRows] = useState<CollecteEomRow[]>([]);
  const [summary, setSummary] = useState({
    cash: 0,
    mobile_money: 0,
    epargne: 0,
    total: 0,
  });
  const [onlyActive, setOnlyActive] = useState(true);
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const res = await adminApi.collecteEom.list(onlyActive);
      setRows(res.results);
      setSummary(res.summary);
    } catch (e) {
      setError((e as ApiError).detail ?? "Chargement impossible.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [onlyActive]);

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    if (!needle) return rows;
    return rows.filter(
      (r) =>
        r.nom.toLowerCase().includes(needle) ||
        r.numero_membre.toLowerCase().includes(needle),
    );
  }, [rows, q]);

  return (
    <div>
      <PageHeader
        eyebrow="Collecte"
        title="Fin de mois collecte"
        description="Choix de chaque membre à la clôture mensuelle : récupérer sa collecte en cash, se la faire verser en Mobile Money (destination indiquée), ou la basculer vers l&apos;épargne (1 % retenu par la coop)."
        actions={
          <button
            type="button"
            onClick={load}
            className="inline-flex items-center gap-1.5 rounded-md border border-line-200 bg-paper px-3 py-2 text-sm font-medium text-ink-700 hover:border-blue-400 hover:text-blue-700"
          >
            <RefreshCw className="size-4" aria-hidden="true" /> Rafraîchir
          </button>
        }
      />

      {/* Récap */}
      <div className="mb-5 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <SummaryCard
          icon={<Banknote className="size-5 text-amber-600" />}
          label="Retrait cash"
          value={summary.cash}
          tint="bg-amber-50"
        />
        <SummaryCard
          icon={<Smartphone className="size-5 text-blue-600" />}
          label="Versement MoMo"
          value={summary.mobile_money}
          tint="bg-blue-50"
        />
        <SummaryCard
          icon={<PiggyBank className="size-5 text-emerald-600" />}
          label="Bascule épargne"
          value={summary.epargne}
          tint="bg-emerald-50"
        />
        <SummaryCard
          icon={<span className="text-sm font-bold text-ink-500">Σ</span>}
          label="Total"
          value={summary.total}
          tint="bg-line-100"
        />
      </div>

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Rechercher un membre…"
          className="w-64 rounded-md border border-line-200 bg-paper px-3 py-2 text-sm text-ink-900 focus:border-blue-700 focus:outline-none focus:ring-1 focus:ring-blue-700"
        />
        <label className="inline-flex items-center gap-2 text-sm text-ink-700">
          <input
            type="checkbox"
            checked={onlyActive}
            onChange={(e) => setOnlyActive(e.target.checked)}
          />
          Solde &gt; 0 uniquement
        </label>
      </div>

      {error ? (
        <div className="mb-4 rounded-md border border-terra-400/40 bg-terra-50/60 px-4 py-2.5 text-sm text-terra-700">
          {error}
        </div>
      ) : null}

      <div className="overflow-x-auto rounded-xl border border-line-200 bg-paper">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-line-200 text-left text-xs uppercase tracking-wide text-ink-500">
              <th className="px-4 py-3 font-medium">Membre</th>
              <th className="px-4 py-3 font-medium">N°</th>
              <th className="px-4 py-3 text-right font-medium">Solde collecte</th>
              <th className="px-4 py-3 font-medium">Choix fin de mois</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={4} className="px-4 py-8 text-center text-ink-500">
                  Chargement…
                </td>
              </tr>
            ) : filtered.length === 0 ? (
              <tr>
                <td colSpan={4} className="px-4 py-8 text-center text-ink-500">
                  Aucun membre.
                </td>
              </tr>
            ) : (
              filtered.map((r) => (
                <tr key={r.member_id} className="border-b border-line-100">
                  <td className="px-4 py-3 font-medium text-ink-900">{r.nom}</td>
                  <td className="px-4 py-3 font-mono text-xs text-ink-600">
                    {r.numero_membre}
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums text-ink-900">
                    {fmtXAF(r.solde)} FCFA
                  </td>
                  <td className="px-4 py-3">
                    {r.preference === "epargne" ? (
                      <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-2.5 py-0.5 text-xs font-semibold text-emerald-700 ring-1 ring-inset ring-emerald-200">
                        <PiggyBank className="size-3.5" /> Bascule épargne
                      </span>
                    ) : r.preference === "mobile_money" ? (
                      <div className="flex flex-col gap-0.5">
                        <span className="inline-flex w-fit items-center gap-1.5 rounded-full bg-blue-50 px-2.5 py-0.5 text-xs font-semibold text-blue-700 ring-1 ring-inset ring-blue-200">
                          <Smartphone className="size-3.5" /> Versement MoMo
                        </span>
                        <span className="font-mono text-xs text-ink-600">
                          {r.payout_phone
                            ? `${r.payout_phone}${r.payout_network ? ` · ${r.payout_network}` : ""}`
                            : "destination manquante"}
                        </span>
                      </div>
                    ) : (
                      <span className="inline-flex items-center gap-1.5 rounded-full bg-amber-50 px-2.5 py-0.5 text-xs font-semibold text-amber-700 ring-1 ring-inset ring-amber-200">
                        <Banknote className="size-3.5" /> Retrait cash
                      </span>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}


function SummaryCard({
  icon,
  label,
  value,
  tint,
}: {
  icon: React.ReactNode;
  label: string;
  value: number;
  tint: string;
}) {
  return (
    <div className="flex items-center gap-3 rounded-xl border border-line-200 bg-paper px-4 py-3">
      <div
        className={`flex size-9 items-center justify-center rounded-lg ${tint}`}
      >
        {icon}
      </div>
      <div>
        <p className="text-xs text-ink-500">{label}</p>
        <p className="text-lg font-bold tabular-nums text-ink-900">{value}</p>
      </div>
    </div>
  );
}
