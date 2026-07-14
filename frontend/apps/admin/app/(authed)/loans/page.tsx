"use client";

import { useEffect, useMemo, useState } from "react";
import { SkeletonList } from "@gathe/ui";
import { Search, Wallet, Loader2, CheckCircle2, Coins } from "lucide-react";

import { DataTable, type DataColumn } from "@/components/data-table";
import { Pagination } from "@/components/pagination";
import {
  ComposeFundingModal,
  type ComposeFundingTarget,
} from "@/components/compose-funding-modal";
import { LoanDetailModal } from "@/components/loan-detail-modal";
import { CashInModal } from "@/components/cash-in-modal";
import { adminApi, type AdminLoanRow, type ApiError } from "@/lib/api";


const MOYEN_LABEL: Record<string, string> = {
  tara_om: "Orange Money",
  tara_momo: "MTN MoMo",
  agence_especes: "Espèces (agence)",
};


type StatutFilter = "" | "actif" | "en_retard" | "cloture" | "contentieux";


export default function LoansPage() {
  return <Inner />;
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
  // Cash-in remboursement : encaisser un versement crédit en agence.
  const [cashInLoan, setCashInLoan] = useState<AdminLoanRow | null>(null);
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

  const columns: DataColumn<AdminLoanRow>[] = [
    {
      key: "dossier",
      label: "Dossier",
      locked: true,
      text: (l) => l.numero_dossier,
      render: (l) => {
        const tauxPct = (Number(l.taux_interet) * 100).toFixed(2);
        return (
          <div>
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
          </div>
        );
      },
    },
    {
      key: "membre",
      label: "Membre",
      text: (l) => `${l.member.prenom} ${l.member.nom} ${l.member.numero_membre}`,
      render: (l) => (
        <div>
          <p className="font-medium text-ink-900">
            {l.member.prenom} {l.member.nom}
          </p>
          <p className="font-mono text-xs text-ink-500">{l.member.numero_membre}</p>
        </div>
      ),
    },
    {
      key: "montant",
      label: "Montant",
      numeric: true,
      align: "right",
      text: (l) => l.montant,
      render: (l) => (
        <span className="font-mono text-sm text-ink-900">
          {Number(l.montant).toLocaleString("fr-FR")}
          {l.mode_retenue_interets === "source" && l.montant_decaisse_net ? (
            <p className="text-xs text-emerald-700">
              net versé {Number(l.montant_decaisse_net).toLocaleString("fr-FR")}
            </p>
          ) : null}
          <p className="text-xs text-ink-500">
            total dû {Number(l.montant_total_du).toLocaleString("fr-FR")}
          </p>
        </span>
      ),
    },
    {
      key: "solde",
      label: "Solde restant",
      numeric: true,
      align: "right",
      text: (l) => l.solde_restant,
      render: (l) => (
        <span className="font-mono text-sm font-medium text-ink-900">
          {Number(l.solde_restant).toLocaleString("fr-FR")}
          <p className="text-[10px] uppercase tracking-wide text-ink-400">XAF</p>
        </span>
      ),
    },
    {
      key: "echeances",
      label: "Échéances",
      filterable: false,
      text: (l) => `${l.installments_payees}/${l.installments_total}`,
      render: (l) => {
        const progression = l.installments_total
          ? Math.round((l.installments_payees / l.installments_total) * 100)
          : 0;
        return (
          <div className="text-sm">
            <p className="text-ink-700">
              {l.installments_payees} / {l.installments_total}
            </p>
            <div className="mt-1 h-1.5 w-24 overflow-hidden rounded-full bg-line-100">
              <div className="h-full bg-emerald" style={{ width: `${progression}%` }} />
            </div>
          </div>
        );
      },
    },
    {
      key: "decais",
      label: "Décaissement",
      defaultVisible: false,
      text: (l) =>
        new Date(l.date_decaissement).toLocaleDateString("fr-FR", {
          day: "2-digit",
          month: "short",
          year: "2-digit",
        }),
    },
    {
      key: "statut",
      label: "Statut",
      text: (l) => l.statut_display,
      render: (l) => (
        <div>
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
        </div>
      ),
    },
  ];

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
        <SkeletonList count={6} cardClassName="h-14" />
      ) : (
        <DataTable
          columns={columns}
          rows={items}
          rowKey={(l) => l.id}
          actionsLabel="Mise à dispo."
          emptyLabel="Aucun crédit ne correspond à ces filtres."
          exportFilename="credits"
          exportTitle="Portefeuille des crédits — GATHE Finance"
          exportSubtitle={`Filtre : ${statut || "tous"}${q ? ` · recherche : ${q}` : ""}`}
          actions={(l) => (
            <div className="flex items-center justify-end gap-2">
              <DisbursementCell row={l} onAction={reload} />
              {l.statut === "actif" || l.statut === "en_retard" ? (
                <button
                  type="button"
                  onClick={() => setCashInLoan(l)}
                  title="Enregistrer un remboursement encaissé en agence (cash-in)"
                  className="inline-flex items-center gap-1 rounded-md border border-line-200 bg-paper px-2 py-1 text-[0.7rem] font-medium text-ink-700 hover:border-emerald/40 hover:text-emerald"
                >
                  <Wallet className="size-3.5" aria-hidden="true" />
                  Remboursement
                </button>
              ) : null}
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
          )}
        />
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

      <CashInModal
        open={cashInLoan !== null}
        onClose={() => setCashInLoan(null)}
        onSuccess={(text) => {
          setFlash(text);
          setTimeout(() => setFlash(null), 4500);
          setCashInLoan(null);
          reload();
        }}
        prefill={
          cashInLoan
            ? {
                member: {
                  id: cashInLoan.member.id,
                  numero_membre: cashInLoan.member.numero_membre,
                  nom: cashInLoan.member.nom,
                  prenom: cashInLoan.member.prenom,
                },
                type: "remboursement",
                loanId: String(cashInLoan.id),
                montant: cashInLoan.solde_restant,
                note: `Remboursement crédit ${cashInLoan.numero_dossier}`,
              }
            : undefined
        }
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
      } else {
        // Mobile Money : argent réel envoyé au membre → confirmation explicite
        // (le canal espèces a déjà son prompt de référence ci-dessus).
        const montant = Number(row.montant_decaisse_net ?? row.montant);
        const ok = window.confirm(
          `Décaisser ${montant.toLocaleString("fr-FR")} XAF à ` +
            `${row.member.prenom} ${row.member.nom} (${row.member.numero_membre}) ` +
            `via ${MOYEN_LABEL[moyen] ?? moyen} ?\n\n` +
            `L'argent part immédiatement sur le téléphone du membre — action irréversible.`,
        );
        if (!ok) {
          setBusy(false);
          return;
        }
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
