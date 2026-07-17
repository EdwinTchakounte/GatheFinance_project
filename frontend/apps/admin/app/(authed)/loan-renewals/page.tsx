"use client";

import { useEffect, useState } from "react";
import { CheckCircle2, RefreshCw, XCircle } from "lucide-react";

import { buttonClasses } from "@gathe/ui";

import { Modal } from "@/components/modal";
import { DataTable, type DataColumn } from "@/components/data-table";
import {
  adminApi,
  type ApiError,
  type LoanRenewalRow,
  type LoanRenewalStatut,
} from "@/lib/api";


/**
 * Reconductions de crédit (Règlement Art.10/11).
 *
 * Le membre demande la reconduction depuis le mobile ou le portail
 * (POST /loans/{id}/renewal/) → crée une `LoanRenewal(statut=demandee)`.
 * Le comité tranche ici :
 *   • Approuver → clôture l'ancien crédit + crée le nouveau (solde repris +
 *     nouvel échéancier). Requiert un taux annuel + la 1re échéance.
 *   • Rejeter → statut `rejetee` + motif (visible du membre).
 */
export default function LoanRenewalsPage() {
  return <Inner />;
}


function Inner() {
  const [filter, setFilter] = useState<LoanRenewalStatut | "all">("demandee");
  const [items, setItems] = useState<LoanRenewalRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [actingId, setActingId] = useState<number | null>(null);
  const [message, setMessage] = useState<{ tone: "ok" | "err"; text: string } | null>(null);

  const [approveTarget, setApproveTarget] = useState<LoanRenewalRow | null>(null);
  const [rejectTarget, setRejectTarget] = useState<LoanRenewalRow | null>(null);

  async function reload() {
    setLoading(true);
    try {
      adminApi.primeCsrf().catch(() => undefined);
      const data = await adminApi.loanRenewals.list(
        filter === "all" ? undefined : filter,
      );
      setItems(data.results);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    reload();
    /* eslint-disable-next-line react-hooks/exhaustive-deps */
  }, [filter]);

  async function onApprove(
    row: LoanRenewalRow,
    tauxPct: number,
    datePremiereEcheance: string,
  ) {
    setActingId(row.id);
    try {
      const r = await adminApi.loanRenewals.decide(row.id, {
        decision: "approuvee",
        taux_annuel: tauxPct / 100,
        date_premiere_echeance: datePremiereEcheance,
      });
      const nouveau = (r as { nouveau_dossier?: string }).nouveau_dossier;
      setMessage({
        tone: "ok",
        text: nouveau
          ? `Reconduction approuvée — nouveau dossier ${nouveau} créé.`
          : "Reconduction approuvée.",
      });
      setApproveTarget(null);
      await reload();
    } catch (err) {
      const apiErr = err as ApiError;
      setMessage({ tone: "err", text: apiErr.detail ?? "Approbation impossible." });
    } finally {
      setActingId(null);
    }
  }

  async function onReject(row: LoanRenewalRow, motif: string) {
    setActingId(row.id);
    try {
      await adminApi.loanRenewals.decide(row.id, {
        decision: "rejetee",
        motif_rejet: motif,
      });
      setMessage({ tone: "ok", text: `Reconduction #${row.id} rejetée.` });
      setRejectTarget(null);
      await reload();
    } catch (err) {
      const apiErr = err as ApiError;
      setMessage({ tone: "err", text: apiErr.detail ?? "Rejet impossible." });
    } finally {
      setActingId(null);
    }
  }

  const columns: DataColumn<LoanRenewalRow>[] = [
    {
      key: "membre",
      label: "Membre",
      locked: true,
      text: (r) => `${r.member_nom} ${r.numero_membre}`,
      render: (r) => (
        <div>
          <div className="font-medium text-ink-900">{r.member_nom}</div>
          <div className="text-xs text-ink-500">{r.numero_membre}</div>
        </div>
      ),
    },
    {
      key: "dossier",
      label: "Dossier",
      text: (r) => r.numero_dossier,
      render: (r) => (
        <div>
          <div className="font-mono text-xs">{r.numero_dossier}</div>
          <div className="text-xs text-ink-500">+{r.nouvelle_duree_mois} mois</div>
        </div>
      ),
    },
    {
      key: "solde",
      label: "Solde restant",
      numeric: true,
      align: "right",
      text: (r) => r.solde_restant,
      render: (r) => (
        <span className="font-semibold tabular-nums">{fmtMoney(r.solde_restant)} FCFA</span>
      ),
    },
    {
      key: "interets",
      label: "Intérêts",
      text: (r) => (r.interets_au_comptant ? "Comptant" : "Reportés"),
      render: (r) => (
        <span
          className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${
            r.interets_au_comptant ? "bg-blue-50 text-blue-700" : "bg-amber-50 text-amber-800"
          }`}
        >
          {r.interets_au_comptant ? "Comptant (10 %)" : "Reportés (15 %)"}
        </span>
      ),
    },
    {
      key: "statut",
      label: "Statut",
      text: (r) => r.statut_display,
      render: (r) => <StatusBadge statut={r.statut} label={r.statut_display} />,
    },
  ];

  return (
    <main className="space-y-6 p-8">
      <header>
        <h1 className="font-editorial text-3xl font-medium tracking-tight text-ink-900">
          Reconductions de crédit
        </h1>
        <p className="text-sm text-ink-500">
          Le membre demande la reconduction (Art.10/11) depuis l&apos;app ou le
          portail. Le comité approuve (taux + 1re échéance → nouveau dossier) ou
          rejette avec motif.
        </p>
      </header>

      <FilterTabs value={filter} onChange={setFilter} />

      {message && (
        <div
          className={`rounded-md px-4 py-3 text-sm ${
            message.tone === "ok"
              ? "border border-emerald-300 bg-emerald-50 text-emerald-800"
              : "border border-red-300 bg-red-50 text-red-800"
          }`}
        >
          {message.text}
        </div>
      )}

      {loading ? (
        <p className="text-ink-600">Chargement…</p>
      ) : (
        <DataTable
          columns={columns}
          rows={items}
          rowKey={(r) => r.id}
          emptyLabel="Aucune reconduction pour ce filtre."
          leftMeta={
            <>
              <span className="font-mono font-medium text-ink-900">{items.length}</span>
              <span>reconduction{items.length > 1 ? "s" : ""}</span>
            </>
          }
          exportFilename="reconductions-credit"
          exportTitle="Reconductions de crédit — GATHE Finance"
          exportSubtitle={`Filtre : ${filter === "all" ? "tous" : filter}`}
          actions={(r) =>
            r.statut === "demandee" ? (
              <div className="flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setApproveTarget(r)}
                  disabled={actingId === r.id}
                  className={buttonClasses({ variant: "primary", size: "sm" })}
                >
                  <CheckCircle2 className="h-4 w-4" />
                  Approuver
                </button>
                <button
                  type="button"
                  onClick={() => setRejectTarget(r)}
                  disabled={actingId === r.id}
                  className={buttonClasses({ variant: "secondary", size: "sm" })}
                >
                  <XCircle className="h-4 w-4" />
                  Rejeter
                </button>
              </div>
            ) : (
              <span className="text-xs text-ink-400"></span>
            )
          }
        />
      )}

      <Modal
        open={!!approveTarget}
        onClose={() => setApproveTarget(null)}
        title={approveTarget ? `Approuver la reconduction de ${approveTarget.member_nom}` : ""}
      >
        {approveTarget && (
          <ApproveForm
            row={approveTarget}
            onSubmit={(taux, date) => onApprove(approveTarget, taux, date)}
            onCancel={() => setApproveTarget(null)}
            disabled={actingId === approveTarget.id}
          />
        )}
      </Modal>

      <Modal
        open={!!rejectTarget}
        onClose={() => setRejectTarget(null)}
        title={rejectTarget ? `Rejeter la reconduction de ${rejectTarget.member_nom}` : ""}
      >
        {rejectTarget && (
          <RejectForm
            onSubmit={(motif) => onReject(rejectTarget, motif)}
            onCancel={() => setRejectTarget(null)}
            disabled={actingId === rejectTarget.id}
          />
        )}
      </Modal>
    </main>
  );
}


function FilterTabs({
  value,
  onChange,
}: {
  value: LoanRenewalStatut | "all";
  onChange: (v: LoanRenewalStatut | "all") => void;
}) {
  const tabs: Array<{ key: LoanRenewalStatut | "all"; label: string }> = [
    { key: "demandee", label: "À décider" },
    { key: "approuvee", label: "Approuvées" },
    { key: "rejetee", label: "Rejetées" },
    { key: "all", label: "Toutes" },
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
        </button>
      ))}
    </div>
  );
}


function StatusBadge({ statut, label }: { statut: LoanRenewalStatut; label: string }) {
  const map: Record<LoanRenewalStatut, string> = {
    demandee: "bg-ink-100 text-ink-700",
    approuvee: "bg-emerald-100 text-emerald-800",
    rejetee: "bg-red-100 text-red-700",
  };
  return (
    <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${map[statut]}`}>
      {label}
    </span>
  );
}


function ApproveForm({
  row,
  onSubmit,
  onCancel,
  disabled,
}: {
  row: LoanRenewalRow;
  onSubmit: (tauxPct: number, datePremiereEcheance: string) => void;
  onCancel: () => void;
  disabled: boolean;
}) {
  const [taux, setTaux] = useState(row.interets_au_comptant ? "10" : "15");
  const [date, setDate] = useState("");
  const valid = Number(taux) > 0 && !!date;
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        if (!valid) return;
        onSubmit(Number(taux), date);
      }}
      className="space-y-3"
    >
      <p className="text-sm text-ink-700">
        Crédit <strong>{row.numero_dossier}</strong> · solde repris{" "}
        <strong>{fmtMoney(row.solde_restant)} FCFA</strong> · +{row.nouvelle_duree_mois} mois.
      </p>
      <label className="block text-sm font-medium text-ink-700">
        Taux annuel (%)
        <input
          type="number"
          min={0}
          max={100}
          step="0.01"
          value={taux}
          onChange={(e) => setTaux(e.target.value)}
          className="mt-1 w-full rounded-md border border-line-200 px-3 py-2 text-sm focus:border-emerald focus:outline-none focus:ring-1 focus:ring-emerald"
          required
        />
      </label>
      <label className="block text-sm font-medium text-ink-700">
        Date de la 1re échéance
        <input
          type="date"
          value={date}
          onChange={(e) => setDate(e.target.value)}
          className="mt-1 w-full rounded-md border border-line-200 px-3 py-2 text-sm focus:border-emerald focus:outline-none focus:ring-1 focus:ring-emerald"
          required
        />
      </label>
      <div className="flex justify-end gap-2">
        <button
          type="button"
          onClick={onCancel}
          className={buttonClasses({ variant: "ghost", size: "sm" })}
        >
          Annuler
        </button>
        <button
          type="submit"
          disabled={disabled || !valid}
          className={buttonClasses({ variant: "primary", size: "sm" })}
        >
          <RefreshCw className="h-4 w-4" />
          Créer le nouveau crédit
        </button>
      </div>
    </form>
  );
}


function RejectForm({
  onSubmit,
  onCancel,
  disabled,
}: {
  onSubmit: (motif: string) => void;
  onCancel: () => void;
  disabled: boolean;
}) {
  const [motif, setMotif] = useState("");
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        if (!motif.trim()) return;
        onSubmit(motif.trim());
      }}
      className="space-y-3"
    >
      <label className="block text-sm font-medium text-ink-700">
        Motif (visible par le membre)
        <textarea
          value={motif}
          onChange={(e) => setMotif(e.target.value)}
          rows={3}
          className="mt-1 w-full rounded-md border border-line-200 px-3 py-2 text-sm focus:border-emerald focus:outline-none focus:ring-1 focus:ring-emerald"
          placeholder="Ex. Pénalités impayées à régulariser avant reconduction."
          required
        />
      </label>
      <div className="flex justify-end gap-2">
        <button
          type="button"
          onClick={onCancel}
          className={buttonClasses({ variant: "ghost", size: "sm" })}
        >
          Annuler
        </button>
        <button
          type="submit"
          disabled={disabled || !motif.trim()}
          className={buttonClasses({ variant: "danger", size: "sm" })}
        >
          Rejeter la reconduction
        </button>
      </div>
    </form>
  );
}


function fmtMoney(s: string | number) {
  const n = typeof s === "string" ? parseFloat(s) : s;
  if (Number.isNaN(n)) return s;
  return Math.round(n).toLocaleString("fr-FR");
}
