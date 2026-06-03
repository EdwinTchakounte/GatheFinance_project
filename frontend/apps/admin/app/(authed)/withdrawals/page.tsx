"use client";

import { useEffect, useState } from "react";
import {
  Banknote,
  CheckCircle2,
  Phone,
  RefreshCw,
  Smartphone,
  XCircle,
} from "lucide-react";

import { buttonClasses } from "@gathe/ui";

import { Modal } from "@/components/modal";
import { ExportMenu } from "@/components/export-menu";
import type { ExportColumn } from "@/lib/export";
import {
  adminApi,
  type ApiError,
  type WithdrawalRow,
  type WithdrawalStatut,
} from "@/lib/api";


/**
 * Refonte 2026 — Demandes de retrait épargne.
 *
 * Le membre demande un retrait en choisissant un canal :
 *   • MOMO   → payout Tara automatique à l'approbation, statut EN_PAYOUT
 *              puis COMPLETEE (ou PAYOUT_FAILED si Tara KO).
 *   • PRESENTIEL → APPROUVEE en attente de remise espèces ; l'admin clique
 *              « Confirmer remise » → COMPLETEE.
 */
export default function WithdrawalsPage() {
  return <Inner />;
}


function Inner() {
  const [filter, setFilter] = useState<WithdrawalStatut | "all">("all");
  const [items, setItems] = useState<WithdrawalRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [actingId, setActingId] = useState<number | null>(null);
  const [message, setMessage] = useState<{ tone: "ok" | "err"; text: string } | null>(null);

  // Modale rejet (motif requis)
  const [rejectTarget, setRejectTarget] = useState<WithdrawalRow | null>(null);

  async function reload() {
    setLoading(true);
    try {
      adminApi.primeCsrf().catch(() => undefined);
      const data = await adminApi.withdrawals.list(
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

  async function onApprove(row: WithdrawalRow) {
    setActingId(row.id);
    try {
      const r = await adminApi.withdrawals.decide(row.id, { decision: "approuvee" });
      setMessage({
        tone: "ok",
        text:
          r.mode_paiement === "momo"
            ? `Payout Tara initié pour ${row.member_nom}.`
            : `Retrait approuvé. Remettre ${row.montant} FCFA en espèces à ${row.member_nom}.`,
      });
      await reload();
    } catch (err) {
      const apiErr = err as ApiError;
      setMessage({ tone: "err", text: apiErr.detail ?? "Approbation impossible." });
    } finally {
      setActingId(null);
    }
  }

  async function onReject(row: WithdrawalRow, motif: string) {
    setActingId(row.id);
    try {
      await adminApi.withdrawals.decide(row.id, {
        decision: "rejetee",
        motif_rejet: motif,
      });
      setMessage({ tone: "ok", text: `Retrait #${row.id} rejeté.` });
      setRejectTarget(null);
      await reload();
    } catch (err) {
      const apiErr = err as ApiError;
      setMessage({ tone: "err", text: apiErr.detail ?? "Rejet impossible." });
    } finally {
      setActingId(null);
    }
  }

  async function onMarkPaid(row: WithdrawalRow) {
    if (
      !window.confirm(
        `Confirmer que vous avez remis ${row.montant} FCFA en espèces à ${row.member_nom} ?`,
      )
    )
      return;
    setActingId(row.id);
    try {
      await adminApi.withdrawals.markPaid(row.id);
      setMessage({ tone: "ok", text: `Remise espèces confirmée pour ${row.member_nom}.` });
      await reload();
    } catch (err) {
      const apiErr = err as ApiError;
      setMessage({ tone: "err", text: apiErr.detail ?? "Marquage impossible." });
    } finally {
      setActingId(null);
    }
  }

  async function onRetryPayout(row: WithdrawalRow) {
    setActingId(row.id);
    try {
      await adminApi.withdrawals.retryPayout(row.id);
      setMessage({ tone: "ok", text: "Payout Tara relancé." });
      await reload();
    } catch (err) {
      const apiErr = err as ApiError;
      setMessage({ tone: "err", text: apiErr.detail ?? "Relance impossible." });
    } finally {
      setActingId(null);
    }
  }

  const exportColumns: ExportColumn<WithdrawalRow>[] = [
    { key: "id", label: "ID", value: (r) => r.id },
    { key: "numero", label: "N° membre", value: (r) => r.numero_membre },
    { key: "membre", label: "Membre", value: (r) => r.member_nom },
    { key: "montant", label: "Montant (FCFA)", value: (r) => r.montant },
    { key: "motif", label: "Motif", value: (r) => r.motif },
    { key: "canal", label: "Canal", value: (r) => r.mode_paiement_display },
    { key: "phone", label: "Téléphone", value: (r) => r.recipient_phone_masked },
    { key: "network", label: "Réseau", value: (r) => r.network },
    { key: "statut", label: "Statut", value: (r) => r.statut_display },
    { key: "motif_rejet", label: "Motif rejet", value: (r) => r.motif_rejet },
    { key: "demande_at", label: "Demandée le", value: (r) => fmt(r.date_demande) },
    { key: "decision_at", label: "Décidée le", value: (r) => fmt(r.date_decision) },
    { key: "handed_over_at", label: "Remise le", value: (r) => fmt(r.handed_over_at) },
  ];

  return (
    <main className="space-y-6 p-8">
      <header className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight text-ink-900">
            Demandes de retrait
          </h1>
          <p className="text-sm text-ink-500">
            Valide les demandes des membres. MOMO = payout Tara automatique. Présentiel = remise espèces à confirmer.
          </p>
        </div>
        <ExportMenu
          filenamePrefix="retraits-epargne"
          title="Demandes de retrait — Gathé Finance"
          subtitle={`Filtre : ${filter === "all" ? "tous" : filter}`}
          columns={exportColumns}
          rows={items}
        />
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

      <div className="overflow-x-auto rounded-lg border border-line-200 bg-paper">
        <table className="w-full text-sm">
          <thead className="bg-cream text-left text-xs uppercase tracking-wide text-ink-500">
            <tr>
              <th className="px-4 py-2">Membre</th>
              <th className="px-4 py-2">Montant</th>
              <th className="px-4 py-2">Canal</th>
              <th className="px-4 py-2">Statut</th>
              <th className="px-4 py-2">Date</th>
              <th className="px-4 py-2 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line-100">
            {loading ? (
              <tr>
                <td colSpan={6} className="p-8 text-center text-ink-500">
                  Chargement…
                </td>
              </tr>
            ) : items.length === 0 ? (
              <tr>
                <td colSpan={6} className="p-8 text-center text-ink-500">
                  Aucune demande pour ce filtre.
                </td>
              </tr>
            ) : (
              items.map((r) => (
                <tr key={r.id} className="text-ink-700">
                  <td className="px-4 py-3">
                    <div className="font-medium">{r.member_nom}</div>
                    <div className="text-xs text-ink-500">{r.numero_membre}</div>
                    {r.motif ? (
                      <div className="mt-1 text-xs italic text-ink-500">
                        « {r.motif} »
                      </div>
                    ) : null}
                  </td>
                  <td className="px-4 py-3 font-semibold">
                    {fmtMoney(r.montant)} FCFA
                  </td>
                  <td className="px-4 py-3">
                    <ChannelBadge row={r} />
                  </td>
                  <td className="px-4 py-3">
                    <StatusBadge statut={r.statut} label={r.statut_display} />
                    {r.motif_rejet ? (
                      <div className="mt-1 max-w-xs text-xs italic text-red-600">
                        {r.motif_rejet}
                      </div>
                    ) : null}
                  </td>
                  <td className="px-4 py-3 text-xs text-ink-500">
                    {fmt(r.date_demande)}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <Actions
                      row={r}
                      disabled={actingId === r.id}
                      onApprove={() => onApprove(r)}
                      onReject={() => setRejectTarget(r)}
                      onMarkPaid={() => onMarkPaid(r)}
                      onRetry={() => onRetryPayout(r)}
                    />
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <Modal
        open={!!rejectTarget}
        onClose={() => setRejectTarget(null)}
        title={rejectTarget ? `Rejeter le retrait de ${rejectTarget.member_nom}` : ""}
      >
        {rejectTarget && (
          <RejectForm
            row={rejectTarget}
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
  value: WithdrawalStatut | "all";
  onChange: (v: WithdrawalStatut | "all") => void;
}) {
  const tabs: Array<{ key: WithdrawalStatut | "all"; label: string }> = [
    { key: "all", label: "Tous" },
    { key: "en_attente", label: "À traiter" },
    { key: "approuvee", label: "Remise espèces en attente" },
    { key: "en_payout", label: "Payout en cours" },
    { key: "payout_failed", label: "Payout échoué" },
    { key: "completee", label: "Terminés" },
    { key: "rejetee", label: "Rejetés" },
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


function ChannelBadge({ row }: { row: WithdrawalRow }) {
  if (row.mode_paiement === "momo") {
    return (
      <div className="space-y-0.5">
        <div className="inline-flex items-center gap-1 rounded-full bg-blue-50 px-2 py-0.5 text-xs font-medium text-blue-700">
          <Smartphone className="h-3 w-3" /> MOMO
        </div>
        <div className="text-xs text-ink-500">
          {row.network} · {row.recipient_phone_masked}
        </div>
      </div>
    );
  }
  return (
    <div className="inline-flex items-center gap-1 rounded-full bg-amber-50 px-2 py-0.5 text-xs font-medium text-amber-800">
      <Banknote className="h-3 w-3" /> Espèces agence
    </div>
  );
}


function StatusBadge({ statut, label }: { statut: WithdrawalStatut; label: string }) {
  const map: Record<WithdrawalStatut, string> = {
    en_attente: "bg-ink-100 text-ink-700",
    approuvee: "bg-amber-100 text-amber-800",
    en_payout: "bg-blue-100 text-blue-800",
    completee: "bg-emerald-100 text-emerald-800",
    payout_failed: "bg-red-100 text-red-800",
    rejetee: "bg-red-100 text-red-700",
  };
  return (
    <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${map[statut]}`}>
      {label}
    </span>
  );
}


function Actions({
  row,
  disabled,
  onApprove,
  onReject,
  onMarkPaid,
  onRetry,
}: {
  row: WithdrawalRow;
  disabled: boolean;
  onApprove: () => void;
  onReject: () => void;
  onMarkPaid: () => void;
  onRetry: () => void;
}) {
  if (row.statut === "en_attente") {
    return (
      <div className="flex justify-end gap-2">
        <button
          type="button"
          onClick={onApprove}
          disabled={disabled}
          className={buttonClasses({
            variant: "primary",
            size: "sm",
          })}
        >
          <CheckCircle2 className="h-4 w-4" />
          Approuver
        </button>
        <button
          type="button"
          onClick={onReject}
          disabled={disabled}
          className={buttonClasses({
            variant: "secondary",
            size: "sm",
          })}
        >
          <XCircle className="h-4 w-4" />
          Rejeter
        </button>
      </div>
    );
  }
  if (row.can_mark_paid) {
    return (
      <button
        type="button"
        onClick={onMarkPaid}
        disabled={disabled}
        className={buttonClasses({
          variant: "primary",
          size: "sm",
        })}
      >
        <Banknote className="h-4 w-4" />
        Confirmer remise espèces
      </button>
    );
  }
  if (row.can_retry_payout) {
    return (
      <button
        type="button"
        onClick={onRetry}
        disabled={disabled}
        className={buttonClasses({
          variant: "secondary",
          size: "sm",
        })}
      >
        <RefreshCw className="h-4 w-4" />
        Réessayer payout
      </button>
    );
  }
  if (row.statut === "en_payout") {
    return (
      <span className="inline-flex items-center gap-1 text-xs text-ink-500">
        <Phone className="h-3 w-3 animate-pulse" /> En attente webhook Tara
      </span>
    );
  }
  return <span className="text-xs text-ink-400">—</span>;
}


function RejectForm({
  row,
  onSubmit,
  onCancel,
  disabled,
}: {
  row: WithdrawalRow;
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
      <p className="text-sm text-ink-700">
        Montant demandé : <strong>{fmtMoney(row.montant)} FCFA</strong>. Le solde
        du membre <strong>ne sera pas</strong> débité.
      </p>
      <label className="block text-sm font-medium text-ink-700">
        Motif (visible par le membre)
        <textarea
          value={motif}
          onChange={(e) => setMotif(e.target.value)}
          rows={3}
          className="mt-1 w-full rounded-md border border-line-200 px-3 py-2 text-sm focus:border-emerald focus:outline-none focus:ring-1 focus:ring-emerald"
          placeholder="Ex. Solde insuffisant après vérification."
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
          Rejeter la demande
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

function fmt(s: string | null | undefined) {
  if (!s) return "";
  try {
    return new Date(s).toLocaleString("fr-FR", {
      day: "2-digit",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return s;
  }
}
