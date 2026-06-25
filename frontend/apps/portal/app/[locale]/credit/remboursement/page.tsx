"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { Container } from "@gathe/ui";

import { portalApi, type ApiError, type Loan } from "@/lib/api";


function RemboursementInner() {
  const router = useRouter();
  const params = useSearchParams();
  const loanIdParam = params.get("loan");
  const [loans, setLoans] = useState<Loan[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    portalApi.loans.activeMine()
      .then((data) => { if (!cancelled) setLoans(data); })
      .catch((err: ApiError) => {
        if (err.status === 401 || err.status === 403) router.replace("/connexion");
        else setError(err.detail ?? "Impossible de charger tes crédits.");
      })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [router]);

  // Si on a un loan_id en query, on redirige direct vers la page de dépôt
  // avec le contexte loan-repayment. Sinon, on liste les crédits actifs.
  useEffect(() => {
    if (loanIdParam) {
      router.replace(`/epargne/depot?context=loan-repayment&loan=${loanIdParam}`);
    }
  }, [loanIdParam, router]);

  return (
    <main className="min-h-svh bg-cream py-10">
      <Container className="max-w-3xl">
        <header className="mb-8">
          <p className="font-display text-[0.7rem] font-semibold uppercase tracking-[0.18em] text-blue-700">
            Crédit · Remboursement
          </p>
          <h1 className="mt-2 font-editorial text-3xl font-medium text-ink-900 sm:text-4xl">
            Régler une échéance.
          </h1>
          <p className="mt-2 text-sm text-ink-600">
            Choisis le crédit concerné, puis valide le montant et le numéro
            Mobile Money à la page suivante.
          </p>
        </header>

        {loading ? (
          <p className="text-sm text-ink-600">Chargement…</p>
        ) : error ? (
          <p className="rounded-lg border border-terra-400/40 bg-terra-50/60 p-4 text-sm text-terra-700">{error}</p>
        ) : loans.length === 0 ? (
          <div className="rounded-xl border border-line-200 bg-paper p-8 text-center">
            <p className="text-sm text-ink-700">Aucun crédit actif à rembourser.</p>
            <a href="/credit" className="mt-3 inline-flex text-sm font-medium text-blue-700 hover:underline">
              Voir mes crédits →
            </a>
          </div>
        ) : (
          <ul className="space-y-3">
            {loans.map((l) => (
              <li key={l.id} className="rounded-xl border border-line-200 bg-paper p-5 shadow-sm transition-all hover:border-blue-700 hover:shadow">
                <div className="flex flex-wrap items-center justify-between gap-4">
                  <div>
                    <p className="text-xs font-mono text-ink-500">
                      {l.numero_dossier ?? `Crédit #${l.id}`}
                    </p>
                    <p className="mt-1 text-base font-semibold text-ink-900">
                      Solde restant {Number(l.solde_restant ?? 0).toLocaleString("fr-FR")} XAF
                    </p>
                    <p className="mt-0.5 text-xs text-ink-500">
                      Statut : {l.statut}
                    </p>
                  </div>
                  <a
                    href={`/epargne/depot?context=loan-repayment&loan=${l.id}`}
                    className="inline-flex items-center gap-2 rounded-lg bg-blue-700 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-blue-800"
                  >
                    Rembourser
                  </a>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Container>
    </main>
  );
}


export default function RemboursementPage() {
  return (
    <Suspense fallback={<main className="min-h-svh bg-cream py-16"><Container><p className="text-center text-ink-600">Chargement…</p></Container></main>}>
      <RemboursementInner />
    </Suspense>
  );
}
