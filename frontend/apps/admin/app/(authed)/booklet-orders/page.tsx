"use client";

import { useEffect, useState, useCallback } from "react";

import { adminApi, type ApiError, type BookletOrderAdmin } from "@/lib/api";

type Tab = "tous" | "payee" | "en_impression" | "delivree";

const STATUT_TONE: Record<string, string> = {
  payee: "bg-blue-50 text-blue-700 ring-blue-200",
  en_impression: "bg-amber-50 text-amber-700 ring-amber-200",
  delivree: "bg-emerald-50 text-emerald-700 ring-emerald-200",
};


export default function BookletOrdersPage() {
  const [tab, setTab] = useState<Tab>("payee");
  const [rows, setRows] = useState<BookletOrderAdmin[]>([]);
  const [count, setCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await adminApi.booklet.list(tab === "tous" ? undefined : tab);
      setRows(res.results);
      setCount(res.count);
    } catch (err) {
      const apiErr = err as ApiError;
      setError(apiErr.detail ?? "Impossible de charger les commandes.");
    } finally {
      setLoading(false);
    }
  }, [tab]);

  useEffect(() => {
    load();
  }, [load]);

  async function onMarkPrinting(row: BookletOrderAdmin) {
    setBusyId(row.id);
    try {
      await adminApi.booklet.markPrinting(row.id);
      await load();
    } catch (err) {
      const apiErr = err as ApiError;
      alert(apiErr.detail ?? "Action echouee.");
    } finally {
      setBusyId(null);
    }
  }

  async function onMarkDelivered(row: BookletOrderAdmin) {
    setBusyId(row.id);
    try {
      await adminApi.booklet.markDelivered(row.id);
      await load();
    } catch (err) {
      const apiErr = err as ApiError;
      alert(apiErr.detail ?? "Action echouee.");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="space-y-6">
      <header>
        <p className="font-display text-[0.7rem] font-semibold uppercase tracking-[0.18em] text-blue-700">
          Carnets
        </p>
        <h1 className="mt-2 font-editorial text-2xl font-medium text-ink-900 sm:text-3xl">
          Commandes de carnet
        </h1>
        <p className="mt-1 text-sm text-ink-600">
          Pilotage du workflow Article 4 : payée → en impression → délivrée.
        </p>
      </header>

      {/* Tabs filtres */}
      <div className="flex flex-wrap gap-2">
        {([
          { v: "payee", l: "À imprimer" },
          { v: "en_impression", l: "En impression" },
          { v: "delivree", l: "Délivrées" },
          { v: "tous", l: "Toutes" },
        ] as { v: Tab; l: string }[]).map((t) => (
          <button
            key={t.v}
            onClick={() => setTab(t.v)}
            className={
              "rounded-full px-3.5 py-1.5 text-sm font-medium transition-all " +
              (tab === t.v
                ? "bg-blue-700 text-white shadow-sm"
                : "bg-paper text-ink-700 ring-1 ring-line-200 hover:bg-cream")
            }
          >
            {t.l}
          </button>
        ))}
        <span className="ml-auto self-center text-xs text-ink-500">
          {count} commande{count > 1 ? "s" : ""} affichée{count > 1 ? "s" : ""}
        </span>
      </div>

      {error ? (
        <p className="rounded-lg border border-terra-400/40 bg-terra-50/60 p-3 text-sm text-terra-700">
          {error}
        </p>
      ) : null}

      {/* Table */}
      <div className="overflow-x-auto rounded-xl border border-line-200 bg-paper shadow-sm">
        <table className="w-full text-sm">
          <thead className="bg-cream/60 text-xs uppercase tracking-wide text-ink-600">
            <tr>
              <th className="px-4 py-3 text-left">Membre</th>
              <th className="px-4 py-3 text-left">Téléphone</th>
              <th className="px-4 py-3 text-left">Paiement</th>
              <th className="px-4 py-3 text-left">Créée le</th>
              <th className="px-4 py-3 text-left">Statut</th>
              <th className="px-4 py-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line-200">
            {loading ? (
              <tr><td colSpan={6} className="px-4 py-8 text-center text-ink-500">Chargement…</td></tr>
            ) : rows.length === 0 ? (
              <tr><td colSpan={6} className="px-4 py-8 text-center text-ink-500">
                Aucune commande dans cet état.
              </td></tr>
            ) : rows.map((row) => {
              const tone = STATUT_TONE[row.statut] ?? "bg-ink-50 text-ink-700 ring-ink-200";
              return (
                <tr key={row.id} className="hover:bg-cream/30">
                  <td className="px-4 py-3">
                    <p className="font-medium text-ink-900">
                      {row.member_prenom} {row.member_nom}
                    </p>
                    <p className="font-mono text-xs text-ink-500">{row.member_numero}</p>
                  </td>
                  <td className="px-4 py-3 text-ink-700">{row.member_phone || "—"}</td>
                  <td className="px-4 py-3 text-ink-700">
                    #{row.payment_id}
                    <span className="ml-2 text-xs text-ink-500">
                      {Number(row.payment_montant).toLocaleString("fr-FR")} XAF
                    </span>
                  </td>
                  <td className="px-4 py-3 text-ink-700">
                    {new Date(row.created_at).toLocaleDateString("fr-CM")}
                  </td>
                  <td className="px-4 py-3">
                    <span className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium ring-1 ring-inset ${tone}`}>
                      {row.statut_display}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right">
                    {row.statut === "payee" ? (
                      <button
                        onClick={() => onMarkPrinting(row)}
                        disabled={busyId === row.id}
                        className="rounded-lg bg-amber-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-amber-700 disabled:opacity-60"
                      >
                        Mettre en impression
                      </button>
                    ) : row.statut === "en_impression" ? (
                      <button
                        onClick={() => onMarkDelivered(row)}
                        disabled={busyId === row.id}
                        className="rounded-lg bg-emerald-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-emerald-700 disabled:opacity-60"
                      >
                        Marquer délivré
                      </button>
                    ) : (
                      <span className="text-xs text-ink-500">
                        {row.date_delivrance ? `Le ${new Date(row.date_delivrance).toLocaleDateString("fr-CM")}` : "—"}
                      </span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
