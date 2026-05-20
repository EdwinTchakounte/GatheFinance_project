"use client";

import { useEffect, useMemo, useState } from "react";
import { Search } from "lucide-react";

import { adminApi, type AdminLoanRow, type ApiError } from "@/lib/api";


type StatutFilter = "" | "actif" | "en_retard" | "cloture" | "contentieux";


export default function LoansPage() {
  return (
    
      <Inner />
    
  );
}


function Inner() {
  const [statut, setStatut] = useState<StatutFilter>("");
  const [q, setQ] = useState("");
  const [items, setItems] = useState<AdminLoanRow[]>([]);
  const [count, setCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function reload() {
    setLoading(true);
    setError(null);
    try {
      const res = await adminApi.loans.list({
        statut: statut || undefined,
        q: q.trim() || undefined,
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
  }, [statut]);

  const totalEncours = useMemo(
    () =>
      items
        .filter((l) => l.statut === "actif" || l.statut === "en_retard")
        .reduce((acc, l) => acc + Number(l.solde_restant || 0), 0),
    [items],
  );

  return (
    <div className="px-8 py-8 lg:px-12 lg:py-10">
      <header className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="font-display text-[0.7rem] font-semibold uppercase tracking-[0.18em] text-terra-600">
            Crédits
          </p>
          <h1 className="mt-2 font-editorial text-3xl font-medium text-ink-900">
            Portefeuille des crédits
          </h1>
          <p className="mt-1 text-sm text-ink-600">
            Tous les crédits décaissés ou en cours de remboursement.
          </p>
        </div>

        <div className="flex items-center gap-3 text-sm text-ink-600">
          <span className="font-mono text-ink-900 font-medium">{count}</span>
          <span>crédit{count > 1 ? "s" : ""}</span>
          <span className="text-ink-400">·</span>
          <span className="font-mono text-blue-700 font-medium">
            {totalEncours.toLocaleString("fr-FR")}
          </span>
          <span>XAF d'encours (vue actuelle)</span>
        </div>
      </header>

      <div className="mb-5 grid grid-cols-1 gap-3 md:grid-cols-[auto_1fr]">
        <div className="flex items-center gap-2">
          <span className="text-[0.65rem] font-semibold uppercase tracking-wider text-ink-500">
            Statut
          </span>
          <div className="flex items-center gap-1 rounded-md border border-line-200 bg-paper p-1">
            {[
              { v: "", l: "Tous" },
              { v: "actif", l: "Actifs" },
              { v: "en_retard", l: "En retard" },
              { v: "cloture", l: "Clôturés" },
              { v: "contentieux", l: "Contentieux" },
            ].map((opt) => (
              <button
                key={opt.v || "all"}
                type="button"
                onClick={() => setStatut(opt.v as StatutFilter)}
                className={[
                  "rounded px-2.5 py-1 text-xs font-medium transition-colors",
                  statut === opt.v
                    ? "bg-blue-700 text-white"
                    : "text-ink-700 hover:text-blue-700",
                ].join(" ")}
              >
                {opt.l}
              </button>
            ))}
          </div>
        </div>

        <form
          onSubmit={(e) => {
            e.preventDefault();
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
              placeholder="Recherche (n° dossier, n° membre, nom)"
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
          Aucun crédit ne correspond à ces filtres.
        </p>
      ) : (
        <div className="overflow-hidden rounded-md border border-line-200 bg-paper">
          <table className="table-admin">
            <thead>
              <tr>
                <th>Dossier</th>
                <th>Membre</th>
                <th className="text-right">Montant</th>
                <th className="text-right">Solde restant</th>
                <th>Échéances</th>
                <th>Décaissement</th>
                <th>Statut</th>
              </tr>
            </thead>
            <tbody>
              {items.map((l) => {
                const tauxPct = (Number(l.taux_interet) * 100).toFixed(2);
                const progression = l.installments_total
                  ? Math.round((l.installments_payees / l.installments_total) * 100)
                  : 0;
                return (
                  <tr key={l.id}>
                    <td>
                      <p className="font-mono text-sm font-medium text-ink-900">
                        {l.numero_dossier}
                      </p>
                      <p className="text-xs text-ink-500">
                        {l.duree_mois} mois · {tauxPct} %/an
                      </p>
                    </td>
                    <td>
                      <p className="font-medium text-ink-900">
                        {l.member.prenom} {l.member.nom}
                      </p>
                      <p className="font-mono text-xs text-ink-500">
                        {l.member.numero_membre}
                      </p>
                    </td>
                    <td className="text-right font-mono text-sm text-ink-900">
                      {Number(l.montant).toLocaleString("fr-FR")}
                      <p className="text-xs text-ink-500">
                        total dû {Number(l.montant_total_du).toLocaleString("fr-FR")}
                      </p>
                    </td>
                    <td className="text-right font-mono text-sm font-medium text-ink-900">
                      {Number(l.solde_restant).toLocaleString("fr-FR")}
                      <p className="text-[10px] uppercase tracking-wide text-ink-400">XAF</p>
                    </td>
                    <td className="text-sm">
                      <p className="text-ink-700">
                        {l.installments_payees} / {l.installments_total}
                      </p>
                      <div className="mt-1 h-1.5 w-24 overflow-hidden rounded-full bg-line-100">
                        <div
                          className="h-full bg-emerald"
                          style={{ width: `${progression}%` }}
                        />
                      </div>
                    </td>
                    <td className="whitespace-nowrap text-sm text-ink-600">
                      {new Date(l.date_decaissement).toLocaleDateString("fr-FR", {
                        day: "2-digit",
                        month: "short",
                        year: "2-digit",
                      })}
                    </td>
                    <td>
                      <span
                        className={
                          "pill " +
                          (l.statut === "actif"
                            ? "pill-success"
                            : l.statut === "en_retard"
                              ? "pill-warning"
                              : l.statut === "contentieux"
                                ? "pill-danger"
                                : "pill-muted")
                        }
                      >
                        {l.statut_display}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {!loading && count > items.length ? (
        <p className="mt-4 text-xs text-ink-500">
          Vue limitée aux {items.length} entrées les plus récentes sur {count}.
          Affine via les filtres ou la recherche.
        </p>
      ) : null}
    </div>
  );
}
