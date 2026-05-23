"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { Container, buttonClasses } from "@gathe/ui";

import {
  portalApi,
  type ApiError,
  type PaymentRead,
  type PaymentInitInput,
} from "@/lib/api";


type FormState = {
  montant: string;
  network: PaymentInitInput["network"];
  phone: string;
};

// Montant par défaut = 1 000 FCFA — cotisation journalière suggérée (Article 4
// du Règlement amendé). Le membre reste libre de modifier.
const INITIAL: FormState = { montant: "1000", network: "MTN", phone: "" };

const IS_DEV = process.env.NODE_ENV !== "production";

// Article 4 (amendé) : 2 canaux disponibles pour la cotisation.
type Channel = "mobile" | "agency";


function DepositForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  // Context :
  //   "savings"          → standard savings deposit (default)
  //   "credit-fees"      → frais de dossier crédit (montant depuis FeeType)
  //   "loan-repayment"   → remboursement d'une échéance (loan_id obligatoire)
  // NB : la reconduction est SANS frais → plus de contexte "loan-renewal".
  const context = searchParams.get("context") ?? "savings";
  const loanIdParam = searchParams.get("loan");
  const isCreditFees = context === "credit-fees";
  const isLoanRepayment = context === "loan-repayment";
  const loanId = loanIdParam ? Number(loanIdParam) : null;
  // Helper: la page renvoie vers /credit pour tout ce qui touche au crédit.
  const isCreditContext = isCreditFees || isLoanRepayment;
  // Le choix de canal (Tara vs agence) ne concerne que le dépôt épargne.
  const offerChannelChoice = context === "savings";

  const [form, setForm] = useState<FormState>(INITIAL);
  const [channel, setChannel] = useState<Channel>("mobile");
  const [submitting, setSubmitting] = useState(false);
  const [payment, setPayment] = useState<PaymentRead | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [simulating, setSimulating] = useState(false);

  // Prime CSRF + pre-fill amount according to context.
  useEffect(() => {
    portalApi.primeCsrf().catch(() => undefined);
    if (isCreditFees) {
      portalApi.payments
        .fees()
        .then((fees) => {
          const fee = fees["DEMANDE_CREDIT"];
          if (fee) setForm((f) => ({ ...f, montant: fee.montant }));
        })
        .catch(() => undefined);
    } else if (isLoanRepayment && loanId !== null) {
      // Pre-fill the form with the next due installment's amount.
      portalApi.loans
        .activeMine()
        .then((loans) => {
          const loan = loans.find((l) => l.id === loanId);
          if (!loan) return;
          const next = loan.installments.find((i) => i.statut !== "payee");
          if (next) {
            const remaining = Number(next.montant_total) - Number(next.montant_paye);
            setForm((f) => ({ ...f, montant: String(remaining > 0 ? remaining : next.montant_total) }));
          }
        })
        .catch(() => undefined);
    }
  }, [isCreditFees, isLoanRepayment, loanId]);

  // Auto-poll the payment status every 2 s while it's `en_attente`.
  useEffect(() => {
    if (!payment || payment.statut !== "en_attente") return;
    const id = payment.id;
    const timer = window.setInterval(async () => {
      try {
        const updated = await portalApi.payments.detail(id);
        setPayment(updated);
        if (updated.statut !== "en_attente") window.clearInterval(timer);
      } catch {
        /* swallow — keep polling on next tick */
      }
    }, 2000);
    return () => window.clearInterval(timer);
  }, [payment]);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (submitting) return;
    setError(null);
    setSubmitting(true);
    try {
      const result = await portalApi.payments.init({
        type: isCreditFees
          ? "frais_demande_credit"
          : isLoanRepayment
            ? "remboursement"
            : "epargne",
        montant: Number(form.montant),
        phone: form.phone,
        network: form.network,
        loan_id: isLoanRepayment ? loanId : null,
      });
      setPayment(result.payment);
    } catch (err) {
      const apiErr = err as ApiError;
      setError(apiErr.detail ?? "Impossible d'initier le paiement.");
    } finally {
      setSubmitting(false);
    }
  }

  async function onSimulate() {
    if (!payment || simulating) return;
    setSimulating(true);
    setError(null);
    try {
      const updated = await portalApi.payments.devConfirm(payment.id);
      setPayment(updated);
    } catch (err) {
      const apiErr = err as ApiError;
      setError(apiErr.detail ?? "Échec de la simulation.");
    } finally {
      setSimulating(false);
    }
  }

  return (
    <main className="py-12 lg:py-16">
      <Container className="max-w-2xl">
        <header className="mb-8">
          <button
            type="button"
            onClick={() =>
              router.push(isCreditContext ? "/credit" : "/")
            }
            className="text-sm text-ink-600 transition-colors hover:text-blue-700"
          >
            ← {isCreditContext ? "Retour à mes crédits" : "Retour au tableau de bord"}
          </button>
          <h1 className="mt-3 font-editorial text-3xl font-medium text-ink-900">
            {isCreditFees
              ? "Payer les frais de dossier"
              : isLoanRepayment
                ? "Rembourser mon crédit"
                : "Verser ma cotisation"}
          </h1>
          <p className="mt-2 text-sm text-ink-600">
            {isCreditFees
              ? "Règle les frais de demande de crédit pour que ta demande passe en instruction."
              : isLoanRepayment
                ? "Le montant sera imputé en FIFO sur tes échéances (plus anciennes d'abord)."
                : "Cotisation journalière suggérée : 1 000 FCFA. Tu restes libre de modifier."}
          </p>
        </header>

        {/* Article 4 amendé — choix du canal (mobile/agence) pour l'épargne */}
        {offerChannelChoice && !payment ? (
          <section className="mb-6 rounded-md border border-line-200 bg-paper p-6">
            <h2 className="font-display text-xs font-semibold uppercase tracking-[0.14em] text-ink-600">
              Comment veux-tu verser ?
            </h2>
            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              <button
                type="button"
                onClick={() => setChannel("mobile")}
                aria-pressed={channel === "mobile"}
                className={
                  "rounded-md border p-4 text-left transition-colors " +
                  (channel === "mobile"
                    ? "border-blue-700 bg-blue-50 ring-2 ring-blue-700/20"
                    : "border-line-200 bg-paper hover:border-line-400")
                }
              >
                <p className="text-sm font-semibold text-ink-900">
                  Mobile Money
                </p>
                <p className="mt-1 text-xs text-ink-600">
                  Paiement immédiat via Tara · disponible 24h/24
                </p>
              </button>
              <button
                type="button"
                onClick={() => setChannel("agency")}
                aria-pressed={channel === "agency"}
                className={
                  "rounded-md border p-4 text-left transition-colors " +
                  (channel === "agency"
                    ? "border-blue-700 bg-blue-50 ring-2 ring-blue-700/20"
                    : "border-line-200 bg-paper hover:border-line-400")
                }
              >
                <p className="text-sm font-semibold text-ink-900">À l&apos;agence</p>
                <p className="mt-1 text-xs text-ink-600">
                  Akwa, Douala (Bercy) · Lun–Ven · 08h00 – 17h00
                </p>
              </button>
            </div>
            <p className="mt-3 text-xs text-ink-500">
              Heure limite quotidienne : <strong>17h00</strong>. Après cette
              heure (ou un week-end), le versement est porté au prochain jour
              ouvré.
            </p>
          </section>
        ) : null}

        {/* Branche "agence" — pas de formulaire, juste un rappel */}
        {offerChannelChoice && channel === "agency" && !payment ? (
          <div className="rounded-md border border-line-200 bg-cream p-7">
            <h2 className="font-editorial text-xl font-medium text-ink-900">
              On te garde une place à l&apos;agence
            </h2>
            <p className="mt-3 text-sm text-ink-700">
              Présente-toi à <strong>Akwa, Douala (Bercy)</strong> du lundi au
              vendredi entre <strong>08h00 et 17h00</strong> avec ton numéro
              de membre. L&apos;agent enregistre ton versement et le crédit
              apparaît immédiatement sur ton solde.
            </p>
            <p className="mt-3 text-xs text-ink-600">
              Ton numéro de membre est visible dans ton profil. Si tu préfères
              finalement payer en ligne, repasse en Mobile Money ci-dessus.
            </p>
            <button
              type="button"
              onClick={() => router.push("/")}
              className={buttonClasses({ variant: "secondary", size: "md" }) + " mt-5"}
            >
              Retour au tableau de bord
            </button>
          </div>
        ) : null}

        {/* Form Mobile Money — visible until a Payment is created
            (et masqué si le membre a choisi le canal "agence") */}
        {!payment && (!offerChannelChoice || channel === "mobile") ? (
          <form
            onSubmit={onSubmit}
            className="rounded-md border border-line-200 bg-paper p-7"
          >
            <label className="block text-sm font-medium text-ink-900" htmlFor="montant">
              Montant (XAF)
            </label>
            <input
              id="montant"
              name="montant"
              type="number"
              min={100}
              step={isLoanRepayment ? "0.01" : 100}
              required
              value={form.montant}
              onChange={(e) => setForm({ ...form, montant: e.target.value })}
              className="mt-2 block w-full rounded-md border border-line-200 bg-paper px-3 py-2 text-ink-900 outline-none transition-colors focus:border-blue-700 focus:ring-1 focus:ring-blue-700"
            />
            <p className="mt-1 text-xs text-ink-600">Minimum 100 XAF.</p>

            <div className="mt-5 grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-ink-900" htmlFor="network">
                  Réseau Mobile Money
                </label>
                <select
                  id="network"
                  name="network"
                  required
                  value={form.network}
                  onChange={(e) => setForm({ ...form, network: e.target.value as FormState["network"] })}
                  className="mt-2 block w-full rounded-md border border-line-200 bg-paper px-3 py-2 text-ink-900 outline-none transition-colors focus:border-blue-700 focus:ring-1 focus:ring-blue-700"
                >
                  <option value="MTN">MTN Mobile Money</option>
                  <option value="ORANGE">Orange Money</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-ink-900" htmlFor="phone">
                  Numéro de téléphone
                </label>
                <input
                  id="phone"
                  name="phone"
                  type="tel"
                  required
                  inputMode="tel"
                  value={form.phone}
                  onChange={(e) => setForm({ ...form, phone: e.target.value })}
                  placeholder="6XX XX XX XX"
                  className="mt-2 block w-full rounded-md border border-line-200 bg-paper px-3 py-2 text-ink-900 outline-none transition-colors focus:border-blue-700 focus:ring-1 focus:ring-blue-700"
                />
              </div>
            </div>

            {error ? (
              <p
                role="alert"
                className="mt-4 rounded-md border border-terra-400/40 bg-terra-50/60 px-3 py-2 text-sm text-terra-700"
              >
                {error}
              </p>
            ) : null}

            <button
              type="submit"
              disabled={submitting}
              className={buttonClasses({ variant: "success", size: "lg", fullWidth: true }) + " mt-7"}
            >
              {submitting ? "Initialisation…" : "Payer maintenant"}
            </button>
          </form>
        ) : null}

        {/* Pending state — payment created, awaiting confirmation */}
        {payment && payment.statut === "en_attente" ? (
          <div className="rounded-md border border-line-200 bg-paper p-7">
            <p className="font-editorial text-xl font-medium text-ink-900">
              En attente de confirmation
            </p>
            <p className="mt-3 text-sm text-ink-600">
              Un code USSD vient d'être poussé sur ton téléphone{" "}
              <span className="font-mono">{form.phone}</span>. Saisis ton code
              PIN MoMo pour valider le paiement de{" "}
              <strong>{Number(payment.montant).toLocaleString("fr-FR")} XAF</strong>.
            </p>
            <p className="mt-2 text-xs text-ink-600">
              Référence : <span className="font-mono">{payment.reference_externe || payment.id}</span>
            </p>

            {error ? (
              <p
                role="alert"
                className="mt-4 rounded-md border border-terra-400/40 bg-terra-50/60 px-3 py-2 text-sm text-terra-700"
              >
                {error}
              </p>
            ) : null}

            {/* DEV-ONLY simulator — hidden in production builds */}
            {IS_DEV ? (
              <div className="mt-7 rounded-md border-2 border-dashed border-terra-500/60 bg-terra-50/30 p-4">
                <p className="font-display text-[0.7rem] font-semibold uppercase tracking-[0.14em] text-terra-700">
                  🛠️ Mode dev — sans clés Tara
                </p>
                <p className="mt-1 text-xs text-ink-600">
                  En production avec Tara configuré, tu validerais avec ton PIN
                  MoMo et un webhook signé arriverait ici. En attendant, simule
                  la confirmation :
                </p>
                <button
                  type="button"
                  onClick={onSimulate}
                  disabled={simulating}
                  className={buttonClasses({ variant: "secondary", size: "sm", fullWidth: true }) + " mt-3"}
                >
                  {simulating ? "Simulation en cours…" : "Simuler la confirmation Tara"}
                </button>
              </div>
            ) : null}
          </div>
        ) : null}

        {/* Success state */}
        {payment && payment.statut === "valide" ? (
          <div className="rounded-md border border-emerald/40 bg-emerald/5 p-7 text-center">
            <p className="font-editorial text-2xl font-medium text-emerald">
              ✓ Paiement confirmé
            </p>
            <p className="mt-3 text-sm text-ink-700">
              Ton dépôt de{" "}
              <strong>{Number(payment.montant).toLocaleString("fr-FR")} XAF</strong>{" "}
              a bien été crédité sur ton compte d'épargne.
            </p>
            <button
              onClick={() =>
                router.push(isCreditContext ? "/credit" : "/")
              }
              className={buttonClasses({ variant: "success", size: "md" }) + " mt-6"}
            >
              {isLoanRepayment
                ? "Voir mon crédit mis à jour"
                : isCreditFees
                  ? "Voir l'état de ma demande"
                  : "Retour au tableau de bord"}
            </button>
          </div>
        ) : null}

        {/* Rejected state */}
        {payment && payment.statut === "rejete" ? (
          <div className="rounded-md border border-terra-400/40 bg-terra-50/60 p-7">
            <p className="font-editorial text-xl font-medium text-terra-700">
              Paiement rejeté
            </p>
            <p className="mt-3 text-sm text-ink-700">
              Motif : {payment.motif_rejet || "Inconnu."}
            </p>
            <button
              onClick={() => {
                setPayment(null);
                setForm(INITIAL);
              }}
              className={buttonClasses({ variant: "secondary", size: "md" }) + " mt-5"}
            >
              Réessayer
            </button>
          </div>
        ) : null}
      </Container>
    </main>
  );
}


// Wrapper Suspense — requis par Next 15 : useSearchParams() doit être sous une
// frontière Suspense pour ne pas casser le prérendu statique au build.
export default function PortalDepositPage() {
  return (
    <Suspense fallback={null}>
      <DepositForm />
    </Suspense>
  );
}
