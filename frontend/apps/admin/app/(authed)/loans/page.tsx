"use client";

import { useEffect, useMemo, useState } from "react";
import { Search, Wallet, Loader2, CheckCircle2, Coins } from "lucide-react";

import { ExportMenu } from "@/components/export-menu";
import { Pagination } from "@/components/pagination";
import {
  ComposeFundingModal,
  type ComposeFundingTarget,
} from "@/components/compose-funding-modal";
import { LoanDetailModal } from "@/components/loan-detail-modal";
import type { ExportColumn } from "@/lib/export";
import { adminApi, type AdminLoanRow, type ApiError } from "@/lib/api";


const MOYEN_LABEL: Record<string, string> = {
  tara_om: "Orange Money",
  tara_momo: "MTN MoMo",
  agence_especes: "Espèces (agence)",
};


type StatutFilter = "" | "actif" | "en_retard" | "cloture" | "contentieux";


const loansExportColumns: ExportColumn<AdminLoanRow>[] = [
  { key: "dossier", label: "N° dossier", value: (r) => r.numero_dossier },
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
  { key: "montant", label: "Montant", value: (r) => r.montant },
  { key: "total_du", label: "Total dû", value: (r) => r.montant_total_du },
  { key: "solde", label: "Solde restant", value: (r) => r.solde_restant },
  { key: "taux", label: "Taux", value: (r) => r.taux_interet },
  { key: "duree", label: "Durée (mois)", value: (r) => r.duree_mois },
  { key: "decais", label: "Décaissement", value: (r) => r.date_decaissement },
  { key: "echeance1", label: "1re échéance", value: (r) => r.date_premiere_echeance },
  { key: "statut", label: "Statut", value: (r) => r.statut_display },
];


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
  const [limit, setLimit] = useState(25);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  // LA-2 . cible du modal "Composer le funding".
  const [fundingTarget, setFundingTarget] = useState<ComposeFundingTarget | null>(null);
  // A1 . cible du modal "Detail credit" (echeances + remboursements).
  const [detailLoanId, setDetailLoanId] = useState<number | null>(null);
  const [flash, setFlash] = useState<string | null>(null);

  async function reload() {
    setLoading(true);
    setError(null);
    try {
      const res = await adminApi.loans.list({
        statut: statut || undefined,
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
  }, [statut, limit, offset]);

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
          <ExportMenu
            filenamePrefix="credits"
            title="Portefeuille des crédits — Gathé Finance"
            subtitle={`Filtre : ${statut || "tous"}${q ? ` · recherche : ${q}` : ""}`}
            columns={loansExportColumns}
            rows={items}
          />
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
                onClick={() => {
                  setStatut(opt.v as StatutFilter);
                  setOffset(0);
                }}
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
                <th>Mise à dispo.</th>
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
                      <button
                        type="button"
                        onClick={() => setDetailLoanId(l.id)}
                        title="Voir le detail (echeances + historique remboursement)"
                        className="font-mono text-sm font-medium text-blue-700 underline-offset-2 hover:underline"
                      >
                        {l.numero_dossier}
                      </button>
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
                      {l.mode_retenue_interets === "source" && l.montant_decaisse_net ? (
                        <p className="text-xs text-emerald-700">
                          net versé {Number(l.montant_decaisse_net).toLocaleString("fr-FR")}
                        </p>
                      ) : null}
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
                      {l.mode_retenue_interets === "source" ? (
                        <p className="mt-1 text-[10px] uppercase tracking-wide text-emerald-700">
                          Intérêts à la source
                        </p>
                      ) : null}
                    </td>
                    <td>
                      <div className="flex items-center gap-2">
                        <DisbursementCell row={l} onAction={reload} />
                        {/* LA-2 . Composer le funding manuellement (visible sur tous statuts). */}
                        <button
                          type="button"
                          onClick={() =>
                            setFundingTarget({
                              id: l.id,
                              numero_dossier: l.numero_dossier,
                              member_label: `${l.member.prenom} ${l.member.nom}`,
                              capital: l.montant,
                            })
                          }
                          title="Composer le funding en selectionnant manuellement les tranches preteur"
                          className="inline-flex items-center gap-1 rounded-md border border-line-200 bg-paper px-2 py-1 text-[0.7rem] font-medium text-ink-700 hover:border-blue-300 hover:text-blue-700"
                        >
                          <Coins className="size-3.5" aria-hidden="true" />
                          Funding
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
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

      {flash ? (
        <div className="fixed bottom-6 left-1/2 z-40 -translate-x-1/2 rounded-md bg-emerald px-4 py-2 text-sm font-medium text-white shadow-lg">
          {flash}
        </div>
      ) : null}

      <ComposeFundingModal
        target={fundingTarget}
        onClose={() => setFundingTarget(null)}
        onSuccess={(msg) => {
          setFlash(msg);
          setTimeout(() => setFlash(null), 4500);
          reload();
        }}
      />

      <LoanDetailModal
        loanId={detailLoanId}
        onClose={() => setDetailLoanId(null)}
      />
    </div>
  );
}


// ---------------------------------------------------------------------------
// DisbursementCell — CH-9 : bouton « Payer maintenant » + badge statut payout.
// ---------------------------------------------------------------------------
function DisbursementCell({
  row,
  onAction,
}: {
  row: AdminLoanRow;
  onAction: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const dis = row.disbursement;
  // Validé = badge "Versé".
  if (dis && dis.statut === "valide") {
    return (
      <div className="text-xs">
        <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-0.5 font-medium text-emerald-700">
          <CheckCircle2 className="size-3" /> Versé
        </span>
        <p className="mt-1 text-[10px] text-ink-500">
          {dis.source === "mobile_money" ? "Tara MoMo" : "Manuel"}
        </p>
      </div>
    );
  }
  // En cours = badge "En attente Tara".
  if (dis && dis.statut === "en_attente") {
    return (
      <div className="text-xs">
        <span className="inline-flex items-center gap-1 rounded-full bg-amber-50 px-2 py-0.5 font-medium text-amber-700">
          <Loader2 className="size-3 animate-spin" /> Payout en cours
        </span>
        <p className="mt-1 text-[10px] text-ink-500">
          {dis.reference_externe || "—"}
        </p>
      </div>
    );
  }
  // Rejeté = badge "Échec" + bouton retry.
  const rejected = dis && dis.statut === "rejete";

  // Si pas de moyen_reception, on guide l'admin vers /disburse/ classique.
  const moyen = row.moyen_reception;
  if (!moyen) {
    return (
      <span className="text-[10px] text-ink-500">
        Moyen de réception manquant
      </span>
    );
  }

  async function handlePayer() {
    setBusy(true);
    setErr(null);
    try {
      const payload: { reference_externe?: string; note?: string } = {};
      if (moyen === "agence_especes") {
        const ref = window.prompt(
          "Référence du reçu de caisse (numéro de bordereau) :",
        );
        if (!ref || !ref.trim()) {
          setBusy(false);
          return;
        }
        payload.reference_externe = ref.trim();
      }
      await adminApi.loans.disburseNow(row.id, payload);
      onAction();
    } catch (e) {
      const apiErr = e as ApiError;
      setErr(apiErr.detail ?? "Échec du décaissement.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="text-xs">
      <p className="text-ink-500">
        Canal :{" "}
        <span className="font-medium text-ink-700">
          {MOYEN_LABEL[moyen] ?? moyen}
        </span>
      </p>
      <button
        type="button"
        onClick={handlePayer}
        disabled={busy}
        className="mt-1 inline-flex items-center gap-1.5 rounded border border-blue-700/30 bg-blue-50 px-2.5 py-1 text-[11px] font-semibold text-blue-700 transition-colors hover:bg-blue-700 hover:text-white disabled:cursor-not-allowed disabled:opacity-50"
      >
        {busy ? (
          <Loader2 className="size-3 animate-spin" />
        ) : (
          <Wallet className="size-3" />
        )}
        {rejected ? "Re-essayer" : "Payer maintenant"}
      </button>
      {err ? <p className="mt-1 text-[10px] text-terra-700">{err}</p> : null}
    </div>
  );
}
