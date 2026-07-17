"use client";

import { useEffect, useState } from "react";

import { Modal } from "./modal";
import { adminApi, type AdminLoanDetail, type ApiError } from "@/lib/api";


function fmtMoney(value: string | number) {
  const n = typeof value === "string" ? Number(value) : value;
  if (!Number.isFinite(n)) return String(value);
  return n.toLocaleString("fr-FR");
}


function statutBadge(statut: string) {
  const map: Record<string, string> = {
    a_venir: "bg-line-100 text-ink-700",
    partielle: "bg-amber-50 text-amber-700",
    en_retard: "bg-rose-50 text-rose-700",
    payee: "bg-emerald-50 text-emerald-700",
  };
  return map[statut] ?? "bg-line-100 text-ink-700";
}


function paymentSourceLabel(src: string) {
  switch (src) {
    case "mobile_money":
      return "Mobile Money";
    case "manuel":
      return "Manuel";
    case "especes":
      return "Espèces (agence)";
    default:
      return src || "";
  }
}


export function LoanDetailModal({
  loanId,
  onClose,
}: {
  loanId: number | null;
  onClose: () => void;
}) {
  const open = loanId !== null;
  const [data, setData] = useState<AdminLoanDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open || loanId === null) return;
    let cancelled = false;
    setLoading(true);
    setData(null);
    setError(null);
    adminApi.loans
      .detail(loanId)
      .then((res) => {
        if (!cancelled) setData(res);
      })
      .catch((err) => {
        const apiErr = err as ApiError;
        if (!cancelled) {
          setError(apiErr.detail ?? "Chargement impossible.");
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [open, loanId]);

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={data ? `Crédit ${data.loan.numero_dossier}` : "Détail crédit"}
      description={
        data
          ? `${data.loan.member.prenom} ${data.loan.member.nom} · ${data.loan.member.numero_membre}`
          : undefined
      }
    >
      {loading ? (
        <p className="py-8 text-center text-sm text-ink-600">Chargement…</p>
      ) : error ? (
        <p className="rounded-md border border-rose-200 bg-rose-50/60 p-3 text-sm text-rose-700">
          {error}
        </p>
      ) : data ? (
        <DetailBody data={data} />
      ) : null}
    </Modal>
  );
}


function DetailBody({ data }: { data: AdminLoanDetail }) {
  return (
    <div className="space-y-6 text-sm">
      <section className="grid grid-cols-2 gap-3 rounded-md border border-line-200 bg-line-100/40 p-3">
        <div>
          <p className="text-[10px] uppercase tracking-wider text-ink-500">Montant</p>
          <p className="font-mono text-base font-semibold text-ink-900">
            {fmtMoney(data.loan.montant)} XAF
          </p>
        </div>
        <div>
          <p className="text-[10px] uppercase tracking-wider text-ink-500">
            Solde restant
          </p>
          <p className="font-mono text-base font-semibold text-ink-900">
            {fmtMoney(data.loan.solde_restant)} XAF
          </p>
        </div>
        <div>
          <p className="text-[10px] uppercase tracking-wider text-ink-500">
            Total remboursé
          </p>
          <p className="font-mono text-base font-semibold text-emerald-700">
            {fmtMoney(data.totaux.rembourse_total)} XAF
          </p>
        </div>
        <div>
          <p className="text-[10px] uppercase tracking-wider text-ink-500">Statut</p>
          <p className="text-base font-medium text-ink-900">
            {data.loan.statut_display}
          </p>
        </div>
      </section>

      <section>
        <header className="mb-2 flex items-center justify-between">
          <h3 className="font-medium text-ink-900">Échéances</h3>
          <p className="text-xs text-ink-500">
            {data.totaux.nb_installments_payees}/
            {data.totaux.nb_installments_total} payées
          </p>
        </header>
        <div className="max-h-[280px] overflow-y-auto rounded-md border border-line-200">
          <table className="w-full text-xs">
            <thead className="bg-line-100/50 text-ink-700">
              <tr>
                <th className="px-2 py-1.5 text-left">#</th>
                <th className="px-2 py-1.5 text-left">Date</th>
                <th className="px-2 py-1.5 text-right">Total dû</th>
                <th className="px-2 py-1.5 text-right">Payé</th>
                <th className="px-2 py-1.5 text-right">Pénalité</th>
                <th className="px-2 py-1.5 text-left">Statut</th>
              </tr>
            </thead>
            <tbody>
              {data.installments.map((i) => (
                <tr key={i.id} className="border-t border-line-200">
                  <td className="px-2 py-1.5 font-mono">{i.numero_echeance}</td>
                  <td className="px-2 py-1.5">
                    {new Date(i.date_echeance).toLocaleDateString("fr-FR", {
                      day: "2-digit",
                      month: "short",
                      year: "2-digit",
                    })}
                  </td>
                  <td className="px-2 py-1.5 text-right font-mono">
                    {fmtMoney(i.montant_total)}
                  </td>
                  <td className="px-2 py-1.5 text-right font-mono">
                    {fmtMoney(i.montant_paye)}
                  </td>
                  <td className="px-2 py-1.5 text-right font-mono">
                    {Number(i.montant_penalite) > 0 ? (
                      <span className="text-rose-700">
                        {fmtMoney(i.montant_penalite)}
                      </span>
                    ) : (
                      ""
                    )}
                  </td>
                  <td className="px-2 py-1.5">
                    <span
                      className={
                        "inline-block rounded-full px-2 py-0.5 text-[10px] font-medium " +
                        statutBadge(i.statut)
                      }
                    >
                      {i.statut_display}
                    </span>
                  </td>
                </tr>
              ))}
              {data.installments.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-2 py-4 text-center text-ink-500">
                    Aucune échéance.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </section>

      <section>
        <header className="mb-2 flex items-center justify-between">
          <h3 className="font-medium text-ink-900">Historique de remboursement</h3>
          <p className="text-xs text-ink-500">{data.totaux.nb_repayments} entrée(s)</p>
        </header>
        <div className="max-h-[280px] overflow-y-auto rounded-md border border-line-200">
          <table className="w-full text-xs">
            <thead className="bg-line-100/50 text-ink-700">
              <tr>
                <th className="px-2 py-1.5 text-left">Date</th>
                <th className="px-2 py-1.5 text-left">Échéance</th>
                <th className="px-2 py-1.5 text-right">Imputé</th>
                <th className="px-2 py-1.5 text-left">Source</th>
                <th className="px-2 py-1.5 text-left">Référence</th>
              </tr>
            </thead>
            <tbody>
              {data.repayments.map((r) => (
                <tr key={r.id} className="border-t border-line-200">
                  <td className="px-2 py-1.5 whitespace-nowrap">
                    {new Date(r.date).toLocaleString("fr-FR", {
                      day: "2-digit",
                      month: "short",
                      year: "2-digit",
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </td>
                  <td className="px-2 py-1.5 font-mono">#{r.installment_numero}</td>
                  <td className="px-2 py-1.5 text-right font-mono text-emerald-700">
                    {fmtMoney(r.montant_impute)}
                  </td>
                  <td className="px-2 py-1.5">
                    {paymentSourceLabel(r.payment_source)}
                  </td>
                  <td className="px-2 py-1.5 font-mono text-[10px] text-ink-500">
                    {r.payment_reference_externe || `Payment #${r.payment_id}`}
                  </td>
                </tr>
              ))}
              {data.repayments.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-2 py-4 text-center text-ink-500">
                    Aucun remboursement enregistré.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
