"use client";

import { useCallback, useEffect, useState } from "react";
import { History, Loader2, RefreshCw } from "lucide-react";

import { adminApi, type ApiError, type ManualDebitRow } from "@/lib/api";

const PAGE = 20;

/**
 * Historique des débits manuels — lecture seule.
 *
 * Le débit manuel n'a pas de table à lui : selon le cas il écrit dans le
 * registre collecte, dans l'épargne classique, dans une collecte particulière,
 * ou crée un Payment pour un frais prélevé. Aucun écran ne les réunissait, et
 * la question « qu'a-t-on sorti de ce compte le mois dernier ? » n'avait pas de
 * réponse directe.
 *
 * Le serveur reconstruit la liste depuis le journal d'audit, ce qui couvre
 * aussi les débits antérieurs à cet écran.
 */
export function ManualDebitHistory({ refreshKey = 0 }: { refreshKey?: number }) {
  const [rows, setRows] = useState<ManualDebitRow[]>([]);
  const [count, setCount] = useState(0);
  const [offset, setOffset] = useState(0);
  const [compte, setCompte] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await adminApi.payments.manualDebitHistory({
        compte: compte || undefined,
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
        limit: PAGE,
        offset,
      });
      setRows(res.results);
      setCount(res.count);
    } catch (e) {
      setError((e as ApiError).detail ?? "Chargement impossible.");
    } finally {
      setLoading(false);
    }
  }, [compte, dateFrom, dateTo, offset]);

  useEffect(() => {
    void load();
  }, [load, refreshKey]);

  const total = rows.reduce((acc, r) => acc + Number(r.montant ?? 0), 0);

  return (
    <section className="rounded-lg border border-line-200 bg-paper p-4">
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h2 className="flex items-center gap-2 text-sm font-semibold text-ink-900">
            <History className="size-4 text-ink-500" aria-hidden="true" />
            Historique des débits
          </h2>
          <p className="text-xs text-ink-500">
            Retraits en agence et frais prélevés sur l&apos;épargne. Lecture seule.
          </p>
        </div>
        <div className="flex flex-wrap items-end gap-2">
          <label className="flex flex-col gap-1 text-[11px] text-ink-500">
            Compte
            <select
              value={compte}
              onChange={(e) => {
                setCompte(e.target.value);
                setOffset(0);
              }}
              className="rounded-md border border-line-300 bg-paper px-2 py-1.5 text-sm text-ink-900"
            >
              <option value="">Tous</option>
              <option value="classique">Épargne classique</option>
              <option value="collecte">Collecte journalière</option>
              <option value="tontine">Tontine alimentaire</option>
              <option value="caisse">Caisse scolaire</option>
            </select>
          </label>
          <label className="flex flex-col gap-1 text-[11px] text-ink-500">
            Du
            <input
              type="date"
              value={dateFrom}
              onChange={(e) => {
                setDateFrom(e.target.value);
                setOffset(0);
              }}
              className="rounded-md border border-line-300 bg-paper px-2 py-1.5 text-sm text-ink-900"
            />
          </label>
          <label className="flex flex-col gap-1 text-[11px] text-ink-500">
            Au
            <input
              type="date"
              value={dateTo}
              onChange={(e) => {
                setDateTo(e.target.value);
                setOffset(0);
              }}
              className="rounded-md border border-line-300 bg-paper px-2 py-1.5 text-sm text-ink-900"
            />
          </label>
          <button
            type="button"
            onClick={() => void load()}
            disabled={loading}
            title="Recharger"
            className="inline-flex items-center gap-1.5 rounded-md border border-line-300 px-3 py-2 text-xs font-medium text-ink-700 hover:bg-ink-50 disabled:opacity-50"
          >
            {loading ? (
              <Loader2 className="size-3.5 animate-spin" />
            ) : (
              <RefreshCw className="size-3.5" />
            )}
            Actualiser
          </button>
        </div>
      </div>

      {error ? (
        <p className="mb-3 text-sm text-terra-700">{error}</p>
      ) : null}

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-line-200 text-left text-[11px] uppercase tracking-wide text-ink-500">
              <th className="py-2 pr-3 font-medium">Date</th>
              <th className="py-2 pr-3 font-medium">Membre</th>
              <th className="py-2 pr-3 font-medium">Nature</th>
              <th className="py-2 pr-3 font-medium">Compte</th>
              <th className="py-2 pr-3 text-right font-medium">Montant</th>
              <th className="py-2 pr-3 text-right font-medium">Solde après</th>
              <th className="py-2 pr-3 font-medium">Motif</th>
              <th className="py-2 font-medium">Par</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 && !loading ? (
              <tr>
                <td colSpan={8} className="py-6 text-center text-sm text-ink-500">
                  Aucun débit sur cette période.
                </td>
              </tr>
            ) : null}
            {rows.map((r) => (
              <tr key={r.id} className="border-b border-line-100 last:border-0">
                <td className="whitespace-nowrap py-2 pr-3 text-ink-700">
                  {new Date(r.date).toLocaleString("fr-FR", {
                    dateStyle: "short",
                    timeStyle: "short",
                  })}
                </td>
                <td className="py-2 pr-3">
                  {r.member ? (
                    <>
                      <span className="text-ink-900">
                        {r.member.prenom} {r.member.nom}
                      </span>
                      <span className="ml-1 font-mono text-[11px] text-ink-500">
                        {r.member.numero_membre}
                      </span>
                    </>
                  ) : (
                    <span className="text-ink-400">—</span>
                  )}
                </td>
                <td className="py-2 pr-3">
                  <span
                    className={
                      r.nature === "frais"
                        ? "rounded-full bg-amber-50 px-2 py-0.5 text-[11px] font-medium text-amber-700"
                        : "rounded-full bg-terra-50 px-2 py-0.5 text-[11px] font-medium text-terra-700"
                    }
                  >
                    {r.nature === "frais" ? `Frais ${r.fee_code ?? ""}`.trim() : "Retrait"}
                  </span>
                </td>
                <td className="py-2 pr-3 text-ink-700">
                  {r.compte_label || <span className="text-ink-400">—</span>}
                  {r.destination === "epargne" ? (
                    <span className="ml-1 text-[11px] text-ink-500">→ épargne</span>
                  ) : null}
                </td>
                <td className="whitespace-nowrap py-2 pr-3 text-right font-mono font-medium text-terra-700">
                  {r.montant != null
                    ? `−${Number(r.montant).toLocaleString("fr-FR")}`
                    : "—"}
                </td>
                <td className="whitespace-nowrap py-2 pr-3 text-right font-mono text-ink-600">
                  {r.solde_apres != null
                    ? Number(r.solde_apres).toLocaleString("fr-FR")
                    : "—"}
                </td>
                <td className="py-2 pr-3 text-ink-600">
                  {r.motif || <span className="text-ink-400">—</span>}
                </td>
                <td className="py-2 text-ink-600">
                  {r.acteur?.nom ?? <span className="text-ink-400">—</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="mt-3 flex items-center justify-between text-xs text-ink-500">
        <span>
          {count} débit{count > 1 ? "s" : ""}
          {rows.length > 0 ? (
            <>
              {" · "}
              <span className="font-mono text-terra-700">
                −{total.toLocaleString("fr-FR")}
              </span>{" "}
              XAF sur cette page
            </>
          ) : null}
        </span>
        <span className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setOffset(Math.max(0, offset - PAGE))}
            disabled={offset === 0 || loading}
            className="rounded-md border border-line-300 px-2 py-1 disabled:opacity-40"
          >
            Précédent
          </button>
          <button
            type="button"
            onClick={() => setOffset(offset + PAGE)}
            disabled={offset + PAGE >= count || loading}
            className="rounded-md border border-line-300 px-2 py-1 disabled:opacity-40"
          >
            Suivant
          </button>
        </span>
      </div>
    </section>
  );
}
