"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { Container } from "@gathe/ui";

import { portalApi, type ApiError, type Loan } from "@/lib/api";
import { renewalInterest, RENEWAL_EXTRA_MONTHS } from "@/lib/loan-terms";


export default function ReconductionPage() {
  const router = useRouter();
  const [loans, setLoans] = useState<Loan[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Form
  const [loanId, setLoanId] = useState<number | null>(null);
  const [modalite, setModalite] = useState<"comptant" | "reporte">("comptant");
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    portalApi.loans.activeMine()
      .then((data) => {
        if (cancelled) return;
        setLoans(data);
        const first = data[0];
        if (first) setLoanId(first.id);
      })
      .catch((err: ApiError) => {
        if (err.status === 401 || err.status === 403) router.replace("/connexion");
        else setError(err.detail ?? "Impossible de charger tes crédits.");
      })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [router]);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!loanId) return;
    setSubmitting(true);
    setSubmitError(null);
    try {
      // Le backend (LoanRenewalRequestSerializer) attend
      // `interets_au_comptant: bool`, pas `modalite`. Mobile envoie le bon
      // champ ; on s'aligne. Sinon le backend tombait sur le defaut false
      // (taux 15 % systematique) peu importe le choix membre.
      const res = await portalApi.loans.requestRenewal(loanId, {
        interets_au_comptant: modalite === "comptant",
      });
      const paymentId = res.renewal.frais_reconduction_payment_id;
      if (paymentId) {
        router.push(`/epargne/depot?context=credit-fees&payment_id=${paymentId}`);
      } else {
        router.push("/credit");
      }
    } catch (err) {
      const apiErr = err as ApiError;
      setSubmitError(apiErr.detail ?? "Échec de la demande de reconduction.");
    } finally {
      setSubmitting(false);
    }
  }

  const currentLoan = loans.find((l) => l.id === loanId);

  // Recap interets calcules live (parite mobile). Utilise le solde restant
  // du credit selectionne et le taux de la modalite choisie.
  const renewalRecap = useMemo(() => {
    if (!currentLoan) return null;
    const capitalRestant = Number(currentLoan.solde_restant ?? 0);
    if (!Number.isFinite(capitalRestant) || capitalRestant <= 0) return null;
    const interets = renewalInterest(capitalRestant, modalite);
    return {
      capitalRestant,
      interets,
      totalAPayer: modalite === "comptant" ? interets : 0,
      capitalReportable: modalite === "reporte" ? capitalRestant + interets : 0,
    };
  }, [currentLoan, modalite]);

  return (
    <main className="min-h-svh bg-cream py-10">
      <Container className="max-w-3xl">
        <header className="mb-8">
          <p className="font-display text-[0.7rem] font-semibold uppercase tracking-[0.18em] text-blue-700">
            Crédit · Reconduction
          </p>
          <h1 className="mt-2 font-editorial text-3xl font-medium text-ink-900 sm:text-4xl">
            Demander une reconduction.
          </h1>
          <p className="mt-2 text-sm leading-relaxed text-ink-600">
            Art. 10/11 du Règlement Intérieur — la reconduction prolonge ton
            crédit d'un mois sans frais. Tu choisis le mode de paiement des
            intérêts (10 % comptant, 15 % reporté).
          </p>
        </header>

        {loading ? (
          <p className="text-sm text-ink-600">Chargement…</p>
        ) : error ? (
          <p className="rounded-lg border border-terra-400/40 bg-terra-50/60 p-4 text-sm text-terra-700">{error}</p>
        ) : loans.length === 0 ? (
          <div className="rounded-xl border border-line-200 bg-paper p-8 text-center">
            <p className="text-sm text-ink-700">Aucun crédit actif à reconduire.</p>
          </div>
        ) : (
          <form onSubmit={onSubmit} className="rounded-xl border border-line-200 bg-paper p-6 shadow-sm">
            {/* Crédit ciblé */}
            <div>
              <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-700">
                Crédit concerné
              </label>
              <select
                value={loanId ?? ""}
                onChange={(e) => setLoanId(Number(e.target.value))}
                className="block w-full rounded-lg border border-line-200 bg-paper px-3.5 py-2.5 text-ink-900 outline-none transition-all focus:border-blue-700 focus:ring-2 focus:ring-blue-700/15"
              >
                {loans.map((l) => (
                  <option key={l.id} value={l.id}>
                    {(l.numero_dossier ?? `Crédit #${l.id}`)} — solde {Number(l.solde_restant ?? 0).toLocaleString("fr-FR")} XAF
                  </option>
                ))}
              </select>
            </div>

            {currentLoan ? (
              <div className="mt-5 rounded-lg bg-cream/60 p-4 text-sm text-ink-700">
                <p>Solde restant : <span className="font-mono font-semibold text-ink-900">{Number(currentLoan.solde_restant ?? 0).toLocaleString("fr-FR")} XAF</span></p>
              </div>
            ) : null}

            {/* Modalité paiement intérêts */}
            <div className="mt-6">
              <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-ink-700">
                Modalité de paiement des intérêts
              </p>
              <div className="grid gap-3 sm:grid-cols-2">
                <label className={`cursor-pointer rounded-lg border p-4 transition-all ${
                  modalite === "comptant" ? "border-blue-700 bg-blue-50/40 ring-2 ring-blue-700/15" : "border-line-200 bg-paper hover:border-blue-300"
                }`}>
                  <input
                    type="radio"
                    name="modalite"
                    value="comptant"
                    checked={modalite === "comptant"}
                    onChange={() => setModalite("comptant")}
                    className="sr-only"
                  />
                  <p className="font-semibold text-ink-900">Comptant · 10 %</p>
                  <p className="mt-1 text-xs text-ink-600">
                    Intérêts payés immédiatement sur le capital restant dû.
                  </p>
                </label>
                <label className={`cursor-pointer rounded-lg border p-4 transition-all ${
                  modalite === "reporte" ? "border-blue-700 bg-blue-50/40 ring-2 ring-blue-700/15" : "border-line-200 bg-paper hover:border-blue-300"
                }`}>
                  <input
                    type="radio"
                    name="modalite"
                    value="reporte"
                    checked={modalite === "reporte"}
                    onChange={() => setModalite("reporte")}
                    className="sr-only"
                  />
                  <p className="font-semibold text-ink-900">Reporté · 15 %</p>
                  <p className="mt-1 text-xs text-ink-600">
                    Intérêts ajoutés au capital remboursable au mois suivant.
                  </p>
                </label>
              </div>
            </div>

            {/* Recap interets live (parite mobile renewal_sheet.dart). */}
            {renewalRecap ? (
              <div className="mt-5 rounded-lg border border-blue-200 bg-blue-50/40 p-4">
                <p className="text-xs font-semibold uppercase tracking-wide text-blue-700">
                  Recap interets (Article 11)
                </p>
                <div className="mt-2 grid grid-cols-1 gap-2 text-sm sm:grid-cols-2">
                  <div>
                    <p className="text-xs text-ink-500">Capital restant</p>
                    <p className="font-mono font-semibold text-ink-900">
                      {renewalRecap.capitalRestant.toLocaleString("fr-FR")} XAF
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-ink-500">
                      Interets a {modalite === "comptant" ? "regler comptant" : "reporter"}
                    </p>
                    <p className="font-mono font-semibold text-blue-800">
                      {renewalRecap.interets.toLocaleString("fr-FR")} XAF
                    </p>
                  </div>
                  {modalite === "reporte" && renewalRecap.capitalReportable > 0 ? (
                    <div className="sm:col-span-2">
                      <p className="text-xs text-ink-500">Nouveau capital a rembourser (mois suivant)</p>
                      <p className="font-mono font-semibold text-ink-900">
                        {renewalRecap.capitalReportable.toLocaleString("fr-FR")} XAF
                      </p>
                    </div>
                  ) : null}
                </div>
                <p className="mt-2 text-[11px] text-ink-500">
                  Duree prolongee : +{RENEWAL_EXTRA_MONTHS} mois (Article 10, fixe).
                </p>
              </div>
            ) : null}

            {submitError ? (
              <p className="mt-4 rounded-lg border border-terra-400/40 bg-terra-50/60 px-3 py-2.5 text-sm text-terra-700">{submitError}</p>
            ) : null}

            <div className="mt-6 flex flex-wrap items-center justify-between gap-3">
              <p className="text-xs text-ink-500">
                La reconduction n'est autorisée qu'une seule fois par crédit (Art. 10).
              </p>
              <button
                type="submit"
                disabled={submitting}
                className="inline-flex items-center justify-center rounded-lg bg-blue-700 px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition-all hover:bg-blue-800 disabled:opacity-60"
              >
                {submitting ? "Envoi…" : "Soumettre la demande"}
              </button>
            </div>
          </form>
        )}
      </Container>
    </main>
  );
}
