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
  //   "savings"             → collecte journalière (défaut)
  //   "epargne-classique"   → dépôt sur l'épargne classique (CH-3)
  //   "credit-fees"         → frais de dossier crédit (montant depuis FeeType)
  //   "loan-repayment"      → remboursement d'une échéance (loan_id obligatoire)
  //   "carnet"              → commande d'un carnet (1er ou supplémentaire) — CH-2
  //   "renewal-carnet"      → renouvellement annuel adhésion via FRAIS_CARNET — D6
  // NB : la reconduction crédit est SANS frais → plus de contexte "loan-renewal".
  const context = searchParams.get("context") ?? "savings";
  const loanIdParam = searchParams.get("loan");
  const isCreditFees = context === "credit-fees";
  const isLoanRepayment = context === "loan-repayment";
  const isEpargneClassique = context === "epargne-classique";
  const isCarnet = context === "carnet";
  const isRenewalCarnet = context === "renewal-carnet";
  const isCarnetContext = isCarnet || isRenewalCarnet;
  const loanId = loanIdParam ? Number(loanIdParam) : null;
  // Helper: la page renvoie vers /credit pour tout ce qui touche au crédit.
  const isCreditContext = isCreditFees || isLoanRepayment;
  // Le choix de canal (Tara vs agence) ne concerne que la collecte journalière.
  const offerChannelChoice = context === "savings";

  const [form, setForm] = useState<FormState>(INITIAL);
  const [channel, setChannel] = useState<Channel>("mobile");
  const [submitting, setSubmitting] = useState(false);
  const [payment, setPayment] = useState<PaymentRead | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [simulating, setSimulating] = useState(false);
  // CH-3 — Sous-canal placement : "libre" = retrait à tout moment,
  // "placement" = crée une tranche prêteur (admin l'allouera à un crédit).
  const [placementMode, setPlacementMode] = useState<"libre" | "placement">(
    "libre",
  );
  // LOT 6 — Multi-jours pré-payé sur la cotisation journalière (context savings).
  // 1 = mode normal (montant libre, min 100). > 1 = montant verrouille a
  // nbJours x kCollecteMinPerDay (1000 par defaut, ajustable backend).
  const [nbJours, setNbJours] = useState<number>(1);
  const COLLECTE_MIN_PER_DAY = 1000;
  // Pas du montant : la collecte se verse par multiples de 50 FCFA (aligné
  // backend `collecte.amount_step`). En multi-jours le montant est LIBRE tant
  // qu'il respecte ce pas ET le minimum de 1 000/jour (≥ N × 1 000).
  const COLLECTE_AMOUNT_STEP = 50;
  const isCollecte = context === "savings";
  const isMultiJour = isCollecte && nbJours > 1;
  // Minimum applicable selon le contexte (aligné backend) :
  //   collecte journalière → N × 1 000 (1 000/jour) ; épargne classique → 1 000 ;
  //   frais / remboursement / carnet → montant prérempli, garde-fou 100.
  const minAmount = isCollecte
    ? nbJours * COLLECTE_MIN_PER_DAY
    : isEpargneClassique
      ? COLLECTE_MIN_PER_DAY
      : 100;
  const amountHelp = isCollecte
    ? `Minimum ${(nbJours * COLLECTE_MIN_PER_DAY).toLocaleString("fr-FR")} XAF${
        nbJours > 1 ? ` (${nbJours} j × 1 000)` : ""
      }, multiple de 50.`
    : isEpargneClassique
      ? "Minimum 1 000 XAF."
      : "Minimum 100 XAF.";

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
    } else if (isCarnetContext) {
      // CH-2 + D6 . Frais carnet (premiere activation OU renouvellement annuel)
      // . montant verrouille au tarif officiel (CARNET FeeType).
      portalApi.payments
        .fees()
        .then((fees) => {
          const fee = fees["CARNET"];
          if (fee) setForm((f) => ({ ...f, montant: fee.montant }));
        })
        .catch(() => undefined);
    }
  }, [isCreditFees, isLoanRepayment, loanId, isCarnetContext]);

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

    // Validation montant (alignée backend) — AVANT l'appel API pour éviter
    // un 400 et donner un message clair. Scopée aux contextes épargne :
    // les frais / remboursement / carnet ont un montant prérempli.
    const amount = Number(form.montant);
    if (!Number.isFinite(amount) || amount <= 0) {
      setError("Saisis un montant valide.");
      return;
    }
    if (isCollecte) {
      if (amount % COLLECTE_AMOUNT_STEP !== 0) {
        setError("Le montant doit être un multiple de 50 XAF.");
        return;
      }
      if (amount < nbJours * COLLECTE_MIN_PER_DAY) {
        setError(
          `Minimum ${(nbJours * COLLECTE_MIN_PER_DAY).toLocaleString("fr-FR")} XAF` +
            (nbJours > 1 ? ` (${nbJours} jour(s) × 1 000).` : " (1 000/jour)."),
        );
        return;
      }
    } else if (isEpargneClassique && amount < COLLECTE_MIN_PER_DAY) {
      setError("Minimum 1 000 XAF.");
      return;
    }

    setSubmitting(true);
    try {
      const result = await portalApi.payments.init({
        type: isCreditFees
          ? "frais_demande_credit"
          : isLoanRepayment
            ? "remboursement"
            : isEpargneClassique
              ? "epargne_classique"
              : isCarnetContext
                ? "frais_carnet"
                : "epargne",
        // Montant LIBRE (≥ N × 1 000, multiple de 50 pour la collecte) —
        // plus de verrouillage : le membre peut verser davantage.
        montant: amount,
        phone: form.phone,
        network: form.network,
        loan_id: isLoanRepayment ? loanId : null,
        is_placement: isEpargneClassique && placementMode === "placement",
        nb_jours_couverts: isMultiJour ? nbJours : undefined,
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
              router.push(
                isCreditContext
                  ? "/credit"
                  : isCarnet
                    ? "/carnet"
                    : isRenewalCarnet
                      ? "/renouvellement-adhesion"
                      : "/",
              )
            }
            className="text-sm text-ink-600 transition-colors hover:text-blue-700"
          >
            ← {isCreditContext
              ? "Retour à mes crédits"
              : isCarnet
                ? "Retour au carnet"
                : isRenewalCarnet
                  ? "Retour au renouvellement"
                  : "Retour au tableau de bord"}
          </button>
          <h1 className="mt-3 font-editorial text-3xl font-medium text-ink-900">
            {isCreditFees
              ? "Payer les frais de dossier"
              : isLoanRepayment
                ? "Rembourser mon crédit"
                : isEpargneClassique
                  ? "Verser sur mon épargne classique"
                  : isCarnet
                    ? "Commander mon carnet"
                    : isRenewalCarnet
                      ? "Renouveler mon adhésion"
                      : "Verser mon épargne"}
          </h1>
          <p className="mt-2 text-sm text-ink-600">
            {isCreditFees
              ? "Règle les frais de demande de crédit pour que ta demande passe en instruction."
              : isLoanRepayment
                ? "Le montant sera imputé en FIFO sur tes échéances (plus anciennes d'abord)."
                : isEpargneClassique
                  ? "Tu peux verser librement (retrait à tout moment) ou choisir de placer ce dépôt (financement de crédit + part des intérêts)."
                  : isCarnet
                    ? "Frais de carnet : tarif officiel verrouillé. Une commande sera créée automatiquement pour impression à l'agence."
                    : isRenewalCarnet
                      ? "Frais de carnet annuels — ton anniversaire d'adhésion est échu (ou bientôt). Le paiement met à jour ta date et réactive ton compte s'il était suspendu."
                      : "Épargne journalière suggérée : 1 000 FCFA. Tu restes libre de modifier."}
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

        {/* CH-3 — choix libre/placement (épargne classique uniquement) */}
        {isEpargneClassique && !payment ? (
          <section className="mb-6 rounded-md border border-line-200 bg-paper p-6">
            <h2 className="font-display text-xs font-semibold uppercase tracking-[0.14em] text-ink-600">
              Que veux-tu faire de cet argent ?
            </h2>
            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              <button
                type="button"
                onClick={() => setPlacementMode("libre")}
                aria-pressed={placementMode === "libre"}
                className={
                  "rounded-md border p-4 text-left transition-colors " +
                  (placementMode === "libre"
                    ? "border-blue-700 bg-blue-50 ring-2 ring-blue-700/20"
                    : "border-line-200 bg-paper hover:border-line-400")
                }
              >
                <p className="text-sm font-semibold text-ink-900">Libre</p>
                <p className="mt-1 text-xs text-ink-600">
                  Retrait à tout moment. Pas d&apos;intérêt généré.
                </p>
              </button>
              <button
                type="button"
                onClick={() => setPlacementMode("placement")}
                aria-pressed={placementMode === "placement"}
                className={
                  "rounded-md border p-4 text-left transition-colors " +
                  (placementMode === "placement"
                    ? "border-emerald bg-emerald/10 ring-2 ring-emerald/20"
                    : "border-line-200 bg-paper hover:border-line-400")
                }
              >
                <p className="text-sm font-semibold text-ink-900">Placement</p>
                <p className="mt-1 text-xs text-ink-600">
                  La coop peut financer un crédit avec ce dépôt. Tu touches une
                  part des intérêts au remboursement.
                </p>
              </button>
            </div>
            {placementMode === "placement" ? (
              <p className="mt-3 text-xs text-ink-500">
                Le dépôt sera bloqué tant qu&apos;il finance un crédit, puis
                redeviendra retirable à la clôture du crédit. Le taux de
                partage est fixé par l&apos;administration.
              </p>
            ) : null}
          </section>
        ) : null}

        {/* LOT 6 — Multi-jours pré-payé (cotisation journalière uniquement) */}
        {context === "savings" && !payment && (!offerChannelChoice || channel === "mobile") ? (
          <section className="mb-6 rounded-md border border-line-200 bg-paper p-6">
            <h2 className="font-display text-xs font-semibold uppercase tracking-[0.14em] text-ink-600">
              Couvrir combien de jours ?
            </h2>
            <p className="mt-1 text-xs text-ink-500">
              Pré-paye plusieurs jours d&apos;avance. Montant libre : minimum{" "}
              {COLLECTE_MIN_PER_DAY.toLocaleString("fr-FR")} XAF/jour, par
              multiples de 50.
            </p>
            <div className="mt-4 flex flex-wrap items-center gap-3">
              <label className="text-sm text-ink-700" htmlFor="nb-jours">Jours :</label>
              <input
                id="nb-jours"
                type="number"
                min={1}
                max={30}
                step={1}
                value={nbJours}
                onChange={(e) => {
                  const n = Math.max(1, Math.min(30, Number(e.target.value) || 1));
                  setNbJours(n);
                  // Pré-remplit le minimum (N × 1 000) ; le montant reste éditable.
                  setForm((f) => ({ ...f, montant: String(n * COLLECTE_MIN_PER_DAY) }));
                }}
                className="w-24 rounded-md border border-line-200 bg-paper px-3 py-2 text-ink-900 outline-none focus:border-blue-700 focus:ring-1 focus:ring-blue-700"
              />
              {isMultiJour ? (
                <span className="inline-flex items-center rounded-full bg-blue-50 px-3 py-1 text-xs font-medium text-blue-700 ring-1 ring-blue-200">
                  Minimum {(nbJours * COLLECTE_MIN_PER_DAY).toLocaleString("fr-FR")} XAF
                </span>
              ) : null}
            </div>
          </section>
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
              min={minAmount}
              step={isLoanRepayment ? "0.01" : isCollecte ? COLLECTE_AMOUNT_STEP : 100}
              required
              value={form.montant}
              onChange={(e) => setForm({ ...form, montant: e.target.value })}
              className="mt-2 block w-full rounded-md border border-line-200 bg-paper px-3 py-2 text-ink-900 outline-none transition-colors focus:border-blue-700 focus:ring-1 focus:ring-blue-700"
            />
            <p className="mt-1 text-xs text-ink-600">{amountHelp}</p>

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
