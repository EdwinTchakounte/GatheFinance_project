"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { Container } from "@gathe/ui";

import { portalApi, type ApiError, type Loan } from "@/lib/api";


function fmtAmount(value: string): string {
  const n = Number(value);
  if (!Number.isFinite(n)) return value;
  return n.toLocaleString("fr-FR");
}


function fmtDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString("fr-FR", {
      day: "2-digit",
      month: "short",
      year: "numeric",
    });
  } catch {
    return iso;
  }
}


export default function LoansHistoryPage() {
  const router = useRouter();
  const [loans, setLoans] = useState<Loan[]>([]);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    portalApi.loans
      .closedMine()
      .then((res) => {
        if (!cancelled) setLoans(res);
      })
      .catch((err) => {
        const apiErr = err as ApiError;
        if (!cancelled) setError(apiErr.detail ?? "Chargement impossible.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <Container>
      <header className="border-b border-line-200 pb-6 pt-10">
        <button
          type="button"
          onClick={() => router.push("/credit")}
          className="text-sm text-ink-600 hover:text-blue-700"
        >
          ← Retour à mes crédits
        </button>
        <h1 className="mt-3 font-editorial text-3xl font-medium text-ink-900">
          Mes crédits clôturés
        </h1>
        <p className="mt-2 text-sm text-ink-600">
          Tous tes crédits passés, avec l'échéancier complet et l'historique
          des remboursements.
        </p>
      </header>

      <section className="mt-8">
        {error ? (
          <div className="mb-5 rounded-md border border-rose-300 bg-rose-50/60 px-4 py-2.5 text-sm text-rose-700">
            {error}
          </div>
        ) : null}

        {loading ? (
          <p className="rounded-md border border-dashed border-line-200 bg-paper/70 p-12 text-center text-sm text-ink-600">
            Chargement…
          </p>
        ) : loans.length === 0 ? (
          <p className="rounded-md border border-dashed border-line-200 bg-paper/70 p-12 text-center text-sm text-ink-600">
            Aucun crédit clôturé pour le moment.
          </p>
        ) : (
          <ul className="space-y-3">
            {loans.map((loan) => {
              const isOpen = expandedId === loan.id;
              return (
                <li
                  key={loan.id}
                  className="overflow-hidden rounded-md border border-line-200 bg-paper"
                >
                  <button
                    type="button"
                    onClick={() => setExpandedId(isOpen ? null : loan.id)}
                    className="flex w-full items-center justify-between gap-4 px-5 py-4 text-left hover:bg-line-100/30"
                  >
                    <div className="min-w-0">
                      <p className="font-mono text-sm font-medium text-ink-900">
                        {loan.numero_dossier}
                      </p>
                      <p className="text-xs text-ink-500">
                        {fmtAmount(loan.montant)} XAF · {loan.duree_mois} mois ·
                        Décaissé le {fmtDate(loan.date_decaissement)}
                      </p>
                    </div>
                    <div className="flex shrink-0 items-center gap-3">
                      <span className="inline-block rounded-full bg-emerald-50 px-2.5 py-0.5 text-[10px] font-semibold text-emerald-700">
                        Clôturé
                      </span>
                      <span className="text-ink-400">{isOpen ? "▴" : "▾"}</span>
                    </div>
                  </button>

                  {isOpen ? (
                    <div className="border-t border-line-200 bg-line-100/20 px-5 py-4">
                      <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-ink-500">
                        Échéancier
                      </p>
                      <div className="overflow-x-auto">
                        <table className="w-full text-xs">
                          <thead className="text-ink-600">
                            <tr>
                              <th className="px-2 py-1.5 text-left">#</th>
                              <th className="px-2 py-1.5 text-left">Date</th>
                              <th className="px-2 py-1.5 text-right">Total dû</th>
                              <th className="px-2 py-1.5 text-right">Payé</th>
                              <th className="px-2 py-1.5 text-left">Statut</th>
                            </tr>
                          </thead>
                          <tbody>
                            {loan.installments.map((inst) => (
                              <tr key={inst.id} className="border-t border-line-200">
                                <td className="px-2 py-1.5 font-mono">
                                  {inst.numero_echeance}
                                </td>
                                <td className="px-2 py-1.5">
                                  {fmtDate(inst.date_echeance)}
                                </td>
                                <td className="px-2 py-1.5 text-right font-mono">
                                  {fmtAmount(inst.montant_total)}
                                </td>
                                <td className="px-2 py-1.5 text-right font-mono">
                                  {fmtAmount(inst.montant_paye)}
                                </td>
                                <td className="px-2 py-1.5">
                                  <span
                                    className={
                                      "inline-block rounded-full px-1.5 py-0.5 text-[10px] font-medium " +
                                      (inst.statut === "payee"
                                        ? "bg-emerald-50 text-emerald-700"
                                        : inst.statut === "en_retard"
                                          ? "bg-rose-50 text-rose-700"
                                          : "bg-line-100 text-ink-700")
                                    }
                                  >
                                    {inst.statut_display}
                                  </span>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  ) : null}
                </li>
              );
            })}
          </ul>
        )}
      </section>
    </Container>
  );
}
