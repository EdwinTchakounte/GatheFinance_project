"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { FileText } from "lucide-react";

import { Container, buttonClasses, EmptyState, Skeleton, SkeletonList } from "@gathe/ui";

import {
  portalApi,
  type ApiError,
  type FormSchemaPublic,
  type Loan,
  type LoanRequest,
} from "@/lib/api";
import {
  DynamicFields,
  validateDynamicFields,
  type FormSchemaPayload,
  type FormValues,
} from "@/components/form-renderer";


// CH-4 — Champs câblés en dur côté UI reconduction. Le service backend les
// gère explicitement ; tout autre champ du schéma loan_renewal actif est
// rendu par <DynamicFields> dans le body de la modale.
const HARDCODED_RENEWAL_FIELDS = new Set([
  "interets_au_comptant", "nouvelle_duree_mois", "motif",
]);


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

// Statuts pour lesquels la demande est encore à l'étude par la commission :
// on affiche l'échéance indicative d'étude (Règlement : 1 semaine à 1 mois).
const STATUTS_SOUS_ETUDE = new Set<LoanRequest["statut"]>([
  "en_attente",
  "en_instruction",
  "en_validation_campagne",
  "en_attente_avaliste",
]);

function statutColor(s: LoanRequest["statut"]): string {
  switch (s) {
    case "en_attente":
      return "text-terra-600";
    case "en_instruction":
      return "text-blue-700";
    case "en_attente_acceptation_membre":
      return "text-terra-700";
    case "en_attente_avaliste":
    case "en_validation_campagne":
      return "text-blue-700";
    case "approuvee":
      return "text-emerald";
    case "rejetee":
    case "rejetee_avaliste":
    case "rejetee_campagne":
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
  const [renewalDone, setRenewalDone] = useState(false);
  // CH-4 — Schéma + valeurs des champs extras pour la modale reconduction.
  const [renewalSchema, setRenewalSchema] = useState<FormSchemaPublic | null>(null);
  const [renewalValues, setRenewalValues] = useState<FormValues>({});
  const [renewalExtraErrors, setRenewalExtraErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const [el, list, active, sc] = await Promise.all([
          portalApi.loans.eligibility(),
          portalApi.loans.listMine(),
          portalApi.loans.activeMine(),
          // FormSchema optionnel : la modale fonctionne aussi en mode legacy.
          portalApi.formSchema("loan_renewal").catch(() => null),
        ]);
        if (cancelled) return;
        setEligibility(el);
        setRequests(list);
        setActiveLoans(active);
        setRenewalSchema(sc);
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
        <Container className="max-w-4xl">
          <Skeleton className="mb-8 h-9 w-48" />
          <SkeletonList count={3} cardClassName="h-28" />
        </Container>
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

        {/* Accès PERMANENT aux mandats d'avaliste (parité mobile — tuile
            toujours visible). Un membre peut être garant d'autrui sans être
            lui-même éligible à un crédit : ce lien ne doit donc PAS dépendre de
            l'état d'éligibilité (bug corrigé — il était auparavant enfoui dans
            la branche « éligible » et disparaissait sinon). */}
        <button
          type="button"
          onClick={() => router.push("/credit/mandats-avaliste")}
          className="mt-8 flex w-full items-center justify-between gap-4 rounded-md border border-line-200 bg-paper p-5 text-left transition-colors hover:border-blue-700/40"
        >
          <div className="flex items-center gap-3">
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-blue-50 text-lg">
              🤝
            </span>
            <div>
              <p className="text-sm font-semibold text-ink-900">
                Mes mandats d'avaliste
              </p>
              <p className="mt-0.5 text-xs text-ink-600">
                Réponds aux demandes où tu es désigné(e) comme garant et consulte
                ton historique.
              </p>
            </div>
          </div>
          <span className="shrink-0 text-blue-700">→</span>
        </button>

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
                <p className="mt-4 text-xs text-ink-600">
                  Pas d'ancienneté suffisante ? Une campagne micro-crédit peut
                  te concerner —{" "}
                  <button
                    type="button"
                    onClick={() => router.push("/credit/campagnes")}
                    className="font-medium text-blue-700 underline-offset-2 hover:underline"
                  >
                    Voir les campagnes ouvertes →
                  </button>
                </p>
                <p className="mt-2 text-xs text-ink-600">
                  Tu veux prêter ton épargne pour financer d'autres crédits ?{" "}
                  <button
                    type="button"
                    onClick={() => router.push("/preteur")}
                    className="font-medium text-blue-700 underline-offset-2 hover:underline"
                  >
                    Accéder à mon espace prêteur →
                  </button>
                </p>
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
            <div className="flex items-end justify-between gap-3">
              <h2 className="font-editorial text-xl font-medium text-ink-900">
                Mes crédits en cours
              </h2>
              <a
                href="/credit/historique"
                className="text-sm font-medium text-blue-700 hover:underline"
              >
                Crédits clôturés →
              </a>
            </div>
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

                  {/* Art. 12 — Penalite de retard (50% du capital restant du) */}
                  {loan.statut === "en_retard" ? (
                    <div className="mt-4 rounded-lg border border-terra-400/40 bg-terra-50/60 p-4">
                      <div className="flex items-start gap-3">
                        <span className="inline-flex size-8 items-center justify-center rounded-full bg-terra-100 text-terra-700">!</span>
                        <div className="min-w-0 flex-1">
                          <p className="text-sm font-semibold text-terra-700">
                            Pénalité Art. 12 active
                          </p>
                          <p className="mt-1 text-xs leading-relaxed text-terra-700/80">
                            Crédit en retard. Une pénalité de{" "}
                            <strong>50 % du capital restant dû</strong> est
                            appliquée selon le Règlement Intérieur (Art. 12).
                            Régularise dès que possible pour éviter le passage
                            en contentieux.
                          </p>
                          <p className="mt-1.5 font-editorial text-base font-semibold text-terra-700">
                            Pénalité estimée : {formatXAF(String(Number(loan.solde_restant) * 0.5))}
                          </p>
                        </div>
                      </div>
                    </div>
                  ) : null}

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
                        <p className="font-display text-[0.7rem] font-medium uppercase tracking-[0.14em] text-ink-600">À rembourser avant</p>
                        <p className="mt-1 font-editorial text-xl font-medium text-ink-900">{formatXAF(nextDue.montant_total)}</p>
                        <p className="text-xs text-ink-600">date butoir : {formatDate(nextDue.date_echeance)}</p>
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
                        Rembourser mon crédit
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
                      Voir le détail du remboursement
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
            <EmptyState
              icon={FileText}
              title="Aucune demande de crédit"
              message="Tes demandes de crédit apparaîtront ici une fois soumises."
              className="mt-5"
            />
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
                    {STATUTS_SOUS_ETUDE.has(r.statut) && r.date_limite_etude ? (
                      <p className="mt-1.5 text-xs text-ink-600">
                        Étude sous 1 semaine à 1 mois — échéance le{" "}
                        {formatDate(r.date_limite_etude)}
                      </p>
                    ) : null}
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
                  {/* CH-9 — Téléchargement de la note PDF, disponible à tout
                      moment après création (la note reflète l'état courant). */}
                  <div className="mt-3">
                    <a
                      href={portalApi.loans.noteUrl(r.id)}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1.5 text-xs font-medium text-blue-700 hover:underline"
                    >
                      📄 Télécharger ma note de demande (PDF)
                    </a>
                  </div>
                  {(r.statut === "rejetee" ||
                    r.statut === "rejetee_avaliste" ||
                    r.statut === "rejetee_campagne") &&
                  r.motif_rejet ? (
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
          setRenewalValues({});
          setRenewalExtraErrors({});
        }}
        schema={renewalSchema}
        values={renewalValues}
        onValuesChange={setRenewalValues}
        extraErrors={renewalExtraErrors}
        onSubmit={async () => {
          if (!renewalTarget) return;
          // CH-4 — Valide les champs extras avant POST.
          if (renewalSchema) {
            const errs = validateDynamicFields(
              renewalSchema as FormSchemaPayload,
              renewalValues,
              HARDCODED_RENEWAL_FIELDS,
            );
            if (Object.keys(errs).length > 0) {
              setRenewalExtraErrors(errs);
              return;
            }
            setRenewalExtraErrors({});
          }
          setRenewalSubmitting(true);
          setRenewalError(null);
          try {
            // Reconduction +1 mois, sans frais : la demande part directement
            // en décision du comité, aucun paiement à régler.
            await portalApi.loans.requestRenewal(
              renewalTarget.id,
              renewalValues,
            );
            setRenewalTarget(null);
            setRenewalValues({});
            setRenewalDone(true);
          } catch (err) {
            const apiErr = err as ApiError;
            setRenewalError(apiErr.detail ?? "Demande impossible.");
          } finally {
            setRenewalSubmitting(false);
          }
        }}
      />
      {renewalDone ? (
        <div
          role="presentation"
          onClick={() => setRenewalDone(false)}
          className="fixed inset-0 z-50 flex items-center justify-center bg-ink-900/50 px-4 py-8 backdrop-blur-sm"
        >
          <div
            role="dialog"
            aria-modal="true"
            onClick={(e) => e.stopPropagation()}
            className="w-full max-w-md overflow-hidden rounded-md border-l-4 border-l-blue-700 bg-paper p-6 shadow-xl"
          >
            <h2 className="font-editorial text-xl font-medium text-ink-900">
              Demande de reconduction envoyée
            </h2>
            <p className="mt-2 text-sm text-ink-600">
              Ta demande de reconduction (+1 mois) a bien été enregistrée.
              Aucun frais n&apos;est dû — seul le taux d&apos;intérêt est majoré.
              Elle est désormais en attente de décision du comité.
            </p>
            <div className="mt-5 flex justify-end">
              <button
                type="button"
                onClick={() => setRenewalDone(false)}
                className={buttonClasses({ variant: "primary", size: "sm" })}
              >
                Compris
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </main>
  );
}


function RenewalModal({
  target,
  submitting,
  error,
  onClose,
  onSubmit,
  schema,
  values,
  onValuesChange,
  extraErrors,
}: {
  target: Loan | null;
  submitting: boolean;
  error: string | null;
  onClose: () => void;
  onSubmit: () => void;
  // CH-4 — Champs supplémentaires saisis via le schéma loan_renewal actif.
  schema?: FormSchemaPublic | null;
  values?: FormValues;
  onValuesChange?: (v: FormValues) => void;
  extraErrors?: Record<string, string>;
}) {
  if (!target) return null;

  const canSubmit = !submitting;

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
          <p className="rounded-md border border-blue-700/20 bg-blue-100/40 px-3 py-2 text-xs text-blue-900">
            La reconduction prolonge ton crédit d&apos;<strong>un mois</strong>.
            <strong> Aucun frais</strong> n&apos;est dû : seul le taux
            d&apos;intérêt est majoré. Ta demande sera soumise au comité pour
            validation.
          </p>
          {error ? (
            <p className="rounded-md border border-terra-400/40 bg-terra-50/60 px-3 py-2 text-xs text-terra-700">
              {error}
            </p>
          ) : null}

          {/* CH-4 — Champs supplémentaires éventuels (FormSchema 'loan_renewal'). */}
          {schema && values && onValuesChange ? (
            <DynamicFields
              schema={schema as FormSchemaPayload}
              values={values}
              onChange={onValuesChange}
              excludeFieldIds={HARDCODED_RENEWAL_FIELDS}
              errors={extraErrors}
            />
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
            onClick={() => canSubmit && onSubmit()}
            disabled={!canSubmit}
            className={buttonClasses({ variant: "primary", size: "sm" })}
          >
            {submitting ? "Envoi…" : "Demander la reconduction"}
          </button>
        </footer>
      </div>
    </div>
  );
}
