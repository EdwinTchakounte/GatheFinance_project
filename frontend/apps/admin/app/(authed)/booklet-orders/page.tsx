"use client";

import { useEffect, useState, useCallback } from "react";

import { DataTable, type DataColumn } from "@/components/data-table";
import { adminApi, type ApiError, type BookletOrderAdmin } from "@/lib/api";
import { fullName } from "@/lib/name";
import { StatusPill } from "@/components/status-pill";

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

  const columns: DataColumn<BookletOrderAdmin>[] = [
    {
      key: "membre",
      label: "Membre",
      locked: true,
      text: (r) => `${fullName(r.member_prenom, r.member_nom)} ${r.member_numero}`,
      render: (r) => (
        <div>
          <p className="font-medium text-ink-900">
            {fullName(r.member_prenom, r.member_nom)}
          </p>
          <p className="font-mono text-xs text-ink-500">{r.member_numero}</p>
        </div>
      ),
    },
    {
      key: "phone",
      label: "Téléphone",
      text: (r) => r.member_phone || "",
      render: (r) => <span className="text-ink-700">{r.member_phone || ""}</span>,
    },
    {
      key: "paiement",
      label: "Paiement",
      text: (r) => String(r.payment_montant),
      render: (r) => (
        <span className="text-ink-700">
          #{r.payment_id}
          <span className="ml-2 text-xs text-ink-500">
            {Number(r.payment_montant).toLocaleString("fr-FR")} XAF
          </span>
        </span>
      ),
    },
    {
      key: "date",
      label: "Créée le",
      defaultVisible: false,
      text: (r) => new Date(r.created_at).toLocaleDateString("fr-CM"),
    },
    {
      key: "statut",
      label: "Statut",
      text: (r) => r.statut_display,
      render: (r) => <StatusPill statut={r.statut} label={r.statut_display} />,
    },
  ];

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
          Suivi des carnets : payée → en impression → délivrée.
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

      {loading ? (
        <p className="text-ink-600">Chargement…</p>
      ) : (
        <DataTable
          columns={columns}
          rows={rows}
          rowKey={(r) => r.id}
          emptyLabel="Aucune commande dans cet état."
          exportFilename="commandes-carnet"
          exportTitle="Commandes de carnet — GATHE Finance"
          exportSubtitle={`Filtre : ${tab}`}
          actions={(row) =>
            row.statut === "payee" ? (
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
                {row.date_delivrance
                  ? `Le ${new Date(row.date_delivrance).toLocaleDateString("fr-CM")}`
                  : ""}
              </span>
            )
          }
        />
      )}
    </div>
  );
}
