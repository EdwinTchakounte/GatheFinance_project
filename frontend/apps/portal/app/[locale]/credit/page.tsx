"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { Container, buttonClasses } from "@gathe/ui";

import { portalApi, type ApiError, type Loan, type LoanRequest } from "@/lib/api";


function formatXAF(amount: string): string {
  const n = Number(amount);
  if (Number.isNaN(n)) return amount;
  return n.toLocaleString("fr-FR", { maximumFractionDigits: 0 }) + " XAF";
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString("fr-FR", { day: "2-digit", month: "short", year: "numeric" });
  } catch {
    return iso;
  }
}

function statutColor(s: LoanRequest["statut"]): string {
  switch (s) {
    case "en_attente":
      return "text-terra-600";
    case "en_instruction":
      return "text-blue-700";
    case "en_attente_acceptation_membre":
      return "text-terra-700";
    case "approuvee":
      return "text-emerald";
    case "rejetee":
      return "text-terra-700";
    default:
      return "text-ink-600";
  }
}


export default function PortalCreditPage() {
  const router = useRouter();
  const [eligibility, setEligibility] = useState<{
    eligible: boolean;
    plafond_max: string;
    motifs_ineligibilite: string[];
    solde_epargne: string;
    ratio_garantie: string;
  } | null>(null);
  const [requests, setRequests] = useState<LoanRequest[] | null>(null);
  const [activeLoans, setActiveLoans] = useState<Loan[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [renewalTarget, setRenewalTarget] = useState<Loan | null>(null);
  const [renewalSubmitting, setRenewalSubmitting] = useState(false);
  const [renewalError, setRenewalError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const [el, list, active] = await Promise.all([
          portalApi.loans.eligibility(),
          portalApi.loans.listMine(),
          portalApi.loans.activeMine(),
        ]);
        if (cancelled) return;
        setEligibility(el);
        setRequests(list);
        setActiveLoans(active);
      } catch (err) {
        const apiErr = err as ApiError;
        if (apiErr.status === 401 || apiErr.status === 403) {
          router.replace("/connexion");
          return;
        }
        setError(apiErr.detail ?? "Impossible de charger la page crédits.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [router]);

  if (loading) {
    return (
      <main className="py-16">
        <Container><p className="text-center text-ink-600">Chargement…</p></Container>
      </main>
    );
  }

  if (error) {
    return (
      <main className="py-16">
        <Container>
          <p className="mx-auto max-w-md rounded-md border border-terra-400/40 bg-terra-50/60 p-5 text-center text-terra-700">
            {error}
          </p>
        </Container>
      </main>
    );
  }

  const hasPending = requests?.some(
    (r) =>
      r.statut === "en_attente"
      || r.statut === "en_instruction"
      || r.statut === "en_attente_acceptation_membre",
  );

  return (
    <main className="py-12 lg:py-16">
      <Container className="max-w-4xl">
        <header className="flex flex-wrap items-end justify-between gap-4 border-b border-line-200 pb-6">
          <div>
            <button
              type="button"
              onClick={() => router.push("/")}
              className="text-sm text-ink-600 transition-colors hover:text-blue-700"
            >
              ← Retour au tableau de bord
            </button>
            <h1 className="mt-3 font-editorial text-3xl font-medium text-ink-900">
              Mes crédits
            </h1>
          </div>
        </header>

        {/* Eligibility card */}
        {eligibility ? (
          <section className="mt-8 rounded-md border border-line-200 bg-paper p-7">
            <h2 className="font-editorial text-sm font-medium uppercase tracking-[0.14em] text-ink-600">
              Ton éligibilité
            </h2>
            {eligibility.eligible ? (
              <>
                <p className="mt-3 font-editorial text-2xl font-medium text-ink-900">
                  Tu peux emprunter jusqu'à{" "}
                  <span className="text-emerald">{formatXAF(eligibility.plafond_max)}</span>
                </p>
                <p className="mt-2 text-sm text-ink-600">
                  Calculé sur ton solde d'épargne actuel ({formatXAF(eligibility.solde_epargne)})
                  × {eligibility.ratio_garantie}.
                </p>
                {hasPending ? (
                  <p className="mt-4 rounded-md border border-blue-700/30 bg-cream px-3 py-2 text-sm text-blue-700">
                    Tu as déjà une demande en cours — attends la décision avant
                    d'en soumettre une nouvelle.
                  </p>
                ) : (
                  <button
                    type="button"
                    onClick={() => router.push("/credit/demande")}
                    className={buttonClasses({ variant: "success", size: "lg" }) + " mt-6"}
                  >
                    Demander un crédit
                  </button>
                )}
              </>
            ) : (
              <>
                <p className="mt-3 font-editorial text-xl font-medium text-terra-700">
                  Pas encore éligible
                </p>
                <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-ink-700">
                  {eligibility.motifs_ineligibilite.map((m, i) => (
                    <li key={i}>{m}</li>
                  ))}
                </ul>
              </>
            )}
          </section>
        ) : null}

        {/* Active credits — visible only when there is a Loan */}
        {activeLoans && activeLoans.length > 0 ? (
          <section className="mt-10">
            <h2 className="font-editorial text-xl font-medium text-ink-900">
              Mes crédits en cours
            </h2>
            {activeLoans.map((loan) => {
              const nextDue = loan.installments.find((i) => i.statut !== "payee");
              return (
                <div key={loan.id} className="mt-5 rounded-md border border-line-200 bg-paper p-7">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <p className="font-mono text-xs text-ink-600">{loan.numero_dossier}</p>
                      <p className="mt-1 font-editorial text-2xl font-medium text-ink-900">
                        {formatXAF(loan.montant)} sur {loan.duree_mois} mois
                      </p>
                      <p className="mt-1 text-sm text-ink-600">
                        Taux : <strong>{(Number(loan.taux_interet) * 100).toFixed(2)} %/an</strong>
                        {" · "}Décaissé le {formatDate(loan.date_decaissement)}
                      </p>
                    </div>
                    <span className={`font-medium ${
                      loan.statut === "actif" ? "text-emerald" :
                      loan.statut === "en_retard" ? "text-terra-700" :
                      "text-ink-600"
                    }`}>
                      {loan.statut_display}
                    </span>
                  </div>

                  <div className="mt-5 grid grid-cols-1 gap-4 md:grid-cols-3">
                    <div className="rounded-md bg-cream p-4">
                      <p className="font-display text-[0.7rem] font-medium uppercase tracking-[0.14em] text-ink-600">Solde restant</p>
                      <p className="mt-1 font-editorial text-xl font-medium text-ink-900">{formatXAF(loan.solde_restant)}</p>
                    </div>
                    <div className="rounded-md bg-cream p-4">
                      <p className="font-display text-[0.7rem] font-medium uppercase tracking-[0.14em] text-ink-600">Total dû</p>
                      <p className="mt-1 font-editorial text-xl font-medium text-ink-900">{formatXAF(loan.montant_total_du)}</p>
                    </div>
                    {nextDue ? (
                      <div className="rounded-md bg-cream p-4">
                        <p className="font-display text-[0.7rem] font-medium uppercase tracking-[0.14em] text-ink-600">Prochaine échéance</p>
                        <p className="mt-1 font-editorial text-xl font-medium text-ink-900">{formatXAF(nextDue.montant_total)}</p>
                        <p className="text-xs text-ink-600">due le {formatDate(nextDue.date_echeance)}</p>
                      </div>
                    ) : null}
                  </div>

                  {loan.statut !== "cloture" ? (
                    <div className="mt-5 flex flex-wrap gap-3">
                      <button
                        type="button"
                        onClick={() => router.push(`/epargne/depot?context=loan-repayment&loan=${loan.id}`)}
                        className={buttonClasses({ variant: "success", size: "md" })}
                      >
                        Rembourser ma prochaine échéance
                      </button>
                      <button
                        type="button"
                        onClick={() => setRenewalTarget(loan)}
                        className={buttonClasses({ variant: "secondary", size: "md" })}
                      >
                        Demander une reconduction
                      </button>
                    </div>
                  ) : null}

                  {/* Echeancier — first 6 rows by default */}
                  <details className="mt-5 group">
                    <summary className="cursor-pointer text-sm text-blue-700 hover:underline">
                      Voir l'échéancier complet ({loan.installments.length} échéances)
                    </summary>
                    <div className="mt-3 overflow-x-auto">
                      <table className="w-full border-collapse text-sm">
                        <thead>
                          <tr className="border-b border-line-200 text-left text-xs uppercase tracking-[0.12em] text-ink-600">
                            <th className="py-2 pr-3">#</th>
                            <th className="py-2 pr-3">Échéance</th>
                            <th className="py-2 pr-3 text-right">Capital</th>
                            <th className="py-2 pr-3 text-right">Intérêts</th>
                            <th className="py-2 pr-3 text-right">Total</th>
                            <th className="py-2 pr-3">Statut</th>
                          </tr>
                        </thead>
                        <tbody>
                          {loan.installments.map((inst) => (
                            <tr key={inst.id} className="border-b border-line-100">
                              <td className="py-2 pr-3 font-mono">{inst.numero_echeance}</td>
                              <td className="py-2 pr-3">{formatDate(inst.date_echeance)}</td>
                              <td className="py-2 pr-3 text-right font-mono">{Number(inst.montant_capital).toLocaleString("fr-FR")}</td>
                              <td className="py-2 pr-3 text-right font-mono">{Number(inst.montant_interets).toLocaleString("fr-FR")}</td>
                              <td className="py-2 pr-3 text-right font-mono font-medium">{Number(inst.montant_total).toLocaleString("fr-FR")}</td>
                              <td className="py-2 pr-3">
                                <span className={
                                  inst.statut === "payee" ? "text-emerald" :
                                  inst.statut === "en_retard" ? "text-terra-700" :
                                  inst.statut === "partielle" ? "text-terra-600" :
                                  "text-ink-600"
                                }>{inst.statut_display}</span>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </details>
                </div>
              );
            })}
          </section>
        ) : null}

        {/* Existing requests */}
        <section className="mt-10">
          <h2 className="font-editorial text-xl font-medium text-ink-900">
            Mes demandes de crédit
          </h2>
          {!requests || requests.length === 0 ? (
            <p className="mt-5 rounded-md border border-dashed border-line-200 bg-paper/70 p-8 text-center text-sm text-ink-600">
              Aucune demande pour le moment.
            </p>
          ) : (
            <ul className="mt-5 divide-y divide-line-200 rounded-md border border-line-200 bg-paper">
              {requests.map((r) => (
                <li key={r.id} className="px-5 py-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <p className="font-mono text-xs text-ink-600">#{r.id} · soumise le {formatDate(r.date_soumission)}</p>
                      <p className="mt-1 font-medium text-ink-900">
                        {formatXAF(r.montant_demande)} sur {r.duree_mois} mois
                      </p>
                      <p className="mt-1 line-clamp-2 text-sm text-ink-600">{r.motif}</p>
                    </div>
                    <span className={`font-medium ${statutColor(r.statut)}`}>
                      {r.statut_display}
                    </span>
                  </div>
                  {r.statut === "en_attente" ? (
                    <div className="mt-3">
                      <button
                        type="button"
                        onClick={() => router.push(`/epargne/depot?context=credit-fees&request=${r.id}`)}
                        className={buttonClasses({ variant: "success", size: "sm" })}
                      >
                        Payer les frais de dossier
                      </button>
                    </div>
                  ) : null}
                  {r.statut === "rejetee" && r.motif_rejet ? (
                    <p className="mt-2 text-sm text-terra-700">Motif : {r.motif_rejet}</p>
                  ) : null}
                  {r.statut === "en_attente_acceptation_membre" && r.montant_revise ? (
                    <p className="mt-2 rounded-md bg-cream px-3 py-2 text-sm text-ink-700">
                      Contre-proposition du comité :{" "}
                      <strong>{formatXAF(r.montant_revise)}</strong> sur{" "}
                      <strong>{r.duree_revisee} mois</strong>. (UI d'acceptation à venir.)
                    </p>
                  ) : null}
                </li>
              ))}
            </ul>
          )}
        </section>
      </Container>
      <RenewalModal
        target={renewalTarget}
        submitting={renewalSubmitting}
        error={renewalError}
        onClose={() => {
          setRenewalTarget(null);
          setRenewalError(null);
        }}
        onSubmit={async (nouvelle_duree_mois) => {
          if (!renewalTarget) return;
          setRenewalSubmitting(true);
          setRenewalError(null);
          try {
            const res = await portalApi.loans.requestRenewal(renewalTarget.id, {
              nouvelle_duree_mois,
            });
            // Redirection vers le paiement des frais de reconduction.
            router.push(
              `/epargne/depot?context=loan-renewal&renewal=${res.renewal.id}`,
            );
          } catch (err) {
            const apiErr = err as ApiError;
            setRenewalError(apiErr.detail ?? "Demande impossible.");
          } finally {
            setRenewalSubmitting(false);
          }
        }}
      />
    </main>
  );
}


function RenewalModal({
  target,
  submitting,
  error,
  onClose,
  onSubmit,
}: {
  target: Loan | null;
  submitting: boolean;
  error: string | null;
  onClose: () => void;
  onSubmit: (nouvelle_duree_mois: number) => void;
}) {
  const [dureeStr, setDureeStr] = useState("6");

  useEffect(() => {
    if (target) setDureeStr("6");
  }, [target]);

  if (!target) return null;

  const duree = Number(dureeStr);
  const dureeValid = Number.isInteger(duree) && duree >= 3 && duree <= 36;
  const canSubmit = !submitting && dureeValid;

  return (
    <div
      role="presentation"
      onClick={onClose}
      className="fixed inset-0 z-50 flex items-center justify-center bg-ink-900/50 px-4 py-8 backdrop-blur-sm"
    >
      <div
        role="dialog"
        aria-modal="true"
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-md overflow-hidden rounded-md border-l-4 border-l-blue-700 bg-paper shadow-xl"
      >
        <header className="px-6 pt-5 pb-3">
          <h2 className="font-editorial text-xl font-medium text-ink-900">
            Demander une reconduction
          </h2>
          <p className="mt-1 text-sm text-ink-600">
            Crédit {target.numero_dossier} — solde restant{" "}
            <strong>{formatXAF(target.solde_restant)}</strong>.
          </p>
        </header>
        <div className="px-6 py-4 space-y-4">
          <label className="block">
            <span className="block text-xs font-semibold uppercase tracking-wider text-ink-700">
              Nouvelle durée (mois)
            </span>
            <span className="mt-0.5 block text-xs text-ink-500">
              Entre 3 et 36 mois.
            </span>
            <input
              type="number"
              inputMode="numeric"
              min={3}
              max={36}
              value={dureeStr}
              onChange={(e) => setDureeStr(e.target.value)}
              className="mt-1.5 w-full rounded-md border border-line-200 bg-paper px-3 py-2 text-sm focus:border-blue-700 focus:outline-none focus:ring-1 focus:ring-blue-700"
              autoFocus
            />
          </label>
          <p className="rounded-md border border-blue-700/20 bg-blue-100/40 px-3 py-2 text-xs text-blue-900">
            Une fois la demande créée, tu seras redirigé(e) vers le règlement
            des <strong>frais de reconduction</strong>. Le comité statuera ensuite.
          </p>
          {error ? (
            <p className="rounded-md border border-terra-400/40 bg-terra-50/60 px-3 py-2 text-xs text-terra-700">
              {error}
            </p>
          ) : null}
        </div>
        <footer className="flex items-center justify-end gap-2 border-t border-line-200 bg-line-100/30 px-6 py-3">
          <button
            type="button"
            onClick={onClose}
            className={buttonClasses({ variant: "ghost", size: "sm" })}
          >
            Annuler
          </button>
          <button
            type="button"
            onClick={() => canSubmit && onSubmit(duree)}
            disabled={!canSubmit}
            className={buttonClasses({ variant: "primary", size: "sm" })}
          >
            Continuer
          </button>
        </footer>
      </div>
    </div>
  );
}
