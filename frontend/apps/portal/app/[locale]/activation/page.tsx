"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { Container, buttonClasses } from "@gathe/ui";

import {
  portalApi,
  type ApiError,
  type Identity,
  type PaymentRead,
  type PaymentInitInput,
} from "@/lib/api";


type FormState = {
  phone: string;
};

// Sélecteur d'opérateur retiré : on déduit le réseau du préfixe du numéro
// camerounais (Orange : 69X / 655–659 · MTN : le reste). Tara route le STK
// push vers le bon opérateur à partir de cette valeur.
function inferNetwork(phone: string): PaymentInitInput["network"] {
  const local = phone.replace(/\D/g, "").slice(-9);
  if (/^69/.test(local) || /^65[5-9]/.test(local)) return "ORANGE";
  return "MTN";
}

const IS_DEV = process.env.NODE_ENV !== "production";

/**
 * CH-2 (chantier juin 2026) — Activation conditionnée au paiement des **3** frais.
 *
 * Le membre doit régler successivement (dans n'importe quel ordre) :
 *  1. Frais d'adhésion        (FeeType code ``ADHESION``, défaut 10 000 FCFA)
 *  2. Frais d'inscription     (``INSCRIPTION``, défaut 2 000 FCFA)
 *  3. Frais de carnet         (``CARNET``, défaut 1 000 FCFA)
 *
 * Le hook backend ``_activate_member_if_fees_settled`` ne bascule le Member
 * à ``ACTIF`` que lorsque les 3 paiements sont validés ; tant qu'il en
 * manque un, ``identity.member.statut`` reste ``SUSPENDU``.
 */
const FEE_STEPS = [
  {
    code: "ADHESION",
    paymentType: "frais_adhesion" as const,
    label: "Frais d'adhésion",
    description: "Droit d'entrée dans la coopérative.",
  },
  {
    code: "INSCRIPTION",
    paymentType: "frais_inscription" as const,
    label: "Frais d'inscription",
    description: "Ouverture de votre dossier membre.",
  },
  {
    code: "CARNET",
    paymentType: "frais_carnet" as const,
    label: "Frais de carnet",
    description: "Édition de votre carnet de collecte.",
  },
];

type FeeStatus = "paid" | "pending" | "unpaid";

type FeeRow = {
  code: string;
  paymentType: PaymentInitInput["type"];
  label: string;
  description: string;
  montant: number;
  status: FeeStatus;
  payment?: PaymentRead;
};


export default function PortalActivationPage() {
  const router = useRouter();
  const [form, setForm] = useState<FormState>({ phone: "" });
  const [identity, setIdentity] = useState<Identity | null>(null);
  const [feesByCode, setFeesByCode] = useState<Record<string, { montant: string }>>({});
  const [memberPayments, setMemberPayments] = useState<PaymentRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [submittingCode, setSubmittingCode] = useState<string | null>(null);
  const [activePayment, setActivePayment] = useState<PaymentRead | null>(null);
  const [activeStepCode, setActiveStepCode] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [simulating, setSimulating] = useState(false);

  // Chargement initial : identité + barème frais + historique paiements du membre.
  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const [me, fees, payments] = await Promise.all([
          portalApi.me(),
          portalApi.payments.fees().catch(() => ({}) as Record<string, { libelle: string; montant: string }>),
          portalApi.payments.me().catch(() => ({ results: [] as PaymentRead[] })),
        ]);
        if (cancelled) return;
        setIdentity(me);
        setFeesByCode(fees as Record<string, { montant: string }>);
        setMemberPayments(payments.results || []);
        if (me.member && me.member.statut === "actif") {
          router.replace("/");
          return;
        }
        if (!me.member) {
          router.replace("/");
          return;
        }
        portalApi.primeCsrf().catch(() => undefined);
      } catch (err) {
        const apiErr = err as ApiError;
        if (apiErr.status === 401 || apiErr.status === 403) {
          router.replace("/connexion");
          return;
        }
        setError(apiErr.detail ?? "Impossible de charger l'écran d'activation.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [router]);

  // Polling sur le paiement en cours — toutes les 2s tant qu'il est en_attente.
  // Au passage à `valide`, on rafraîchit l'identité (le hook backend a peut-être
  // basculé le Member à ACTIF si c'était le 3e frais) et la liste des paiements.
  useEffect(() => {
    if (!activePayment || activePayment.statut !== "en_attente") return;
    const id = activePayment.id;
    const timer = window.setInterval(async () => {
      try {
        const updated = await portalApi.payments.detail(id);
        setActivePayment(updated);
        if (updated.statut !== "en_attente") {
          window.clearInterval(timer);
          // Resync : nouveau statut Member + nouvelle liste de payments validés.
          const [me, payments] = await Promise.all([
            portalApi.me(),
            portalApi.payments.me().catch(() => ({ results: [] as PaymentRead[] })),
          ]);
          setIdentity(me);
          setMemberPayments(payments.results || []);
          if (me.member?.statut === "actif") {
            // Les 3 frais sont payés → le hook backend nous a activés.
            // On affiche la confirmation puis on redirige (cf. ci-dessous).
          }
        }
      } catch {
        /* swallow */
      }
    }, 2000);
    return () => window.clearInterval(timer);
  }, [activePayment]);

  function getStatusForCode(code: string): { status: FeeStatus; payment?: PaymentRead } {
    const targetType = FEE_STEPS.find((s) => s.code === code)?.paymentType;
    if (!targetType) return { status: "unpaid" };
    const valid = memberPayments.find(
      (p) => p.type === targetType && p.statut === "valide",
    );
    if (valid) return { status: "paid", payment: valid };
    const pending = memberPayments.find(
      (p) => p.type === targetType && p.statut === "en_attente",
    );
    if (pending) return { status: "pending", payment: pending };
    return { status: "unpaid" };
  }

  const rows: FeeRow[] = FEE_STEPS.map((step) => {
    const { status, payment } = getStatusForCode(step.code);
    const montantStr = feesByCode[step.code]?.montant ?? "0";
    return {
      ...step,
      montant: Number(montantStr),
      status,
      payment,
    };
  });

  const totalAmount = rows.reduce((sum, r) => sum + r.montant, 0);
  const paidCount = rows.filter((r) => r.status === "paid").length;
  const allPaid = paidCount === rows.length;
  const isActivated = identity?.member?.statut === "actif";

  async function onSubmitFee(e: React.FormEvent, row: FeeRow) {
    e.preventDefault();
    if (submittingCode) return;
    if (!form.phone) {
      setError("Indique ton numéro de téléphone Mobile Money.");
      return;
    }
    setError(null);
    setSubmittingCode(row.code);
    setActiveStepCode(row.code);
    try {
      const result = await portalApi.payments.init({
        type: row.paymentType,
        montant: row.montant,
        phone: form.phone,
        // Réseau déduit du préfixe — plus de sélecteur manuel côté membre.
        network: inferNetwork(form.phone),
      });
      setActivePayment(result.payment);
      // Marque le payment en attente côté local pour rendu immédiat
      setMemberPayments((prev) => [result.payment, ...prev]);
    } catch (err) {
      const apiErr = err as ApiError;
      setError(apiErr.detail ?? `Impossible d'initier le paiement (${row.label}).`);
      setActiveStepCode(null);
    } finally {
      setSubmittingCode(null);
    }
  }

  async function onSimulate() {
    if (!activePayment || simulating) return;
    setSimulating(true);
    setError(null);
    try {
      const updated = await portalApi.payments.devConfirm(activePayment.id);
      setActivePayment(updated);
    } catch (err) {
      const apiErr = err as ApiError;
      setError(apiErr.detail ?? "Échec de la simulation.");
    } finally {
      setSimulating(false);
    }
  }

  function resetActivePayment() {
    setActivePayment(null);
    setActiveStepCode(null);
  }

  if (loading) {
    return (
      <main className="py-16">
        <Container><p className="text-center text-ink-600">Chargement…</p></Container>
      </main>
    );
  }

  const memberName = identity?.member
    ? `${identity.member.prenom} ${identity.member.nom}`.trim()
    : "";

  return (
    <main className="py-12 lg:py-16">
      <Container className="max-w-2xl">
        <header className="mb-8 text-center">
          <span className="label-num">Activer ton compte</span>
          <h1 className="mt-3 font-editorial text-3xl font-medium text-ink-900">
            Bienvenue{memberName ? `, ${memberName}` : ""} !
          </h1>
          <p className="mt-3 text-sm text-ink-600">
            Ta demande d'adhésion a été approuvée. Pour activer ton compte,
            règle les <strong>3 frais d'adhésion</strong> ci-dessous (dans
            n'importe quel ordre).
          </p>
        </header>

        {/* Bandeau de progression */}
        <div className="mb-6 rounded-md border border-line-200 bg-paper px-5 py-4">
          <div className="flex items-center justify-between">
            <p className="text-sm text-ink-700">
              <strong>{paidCount}</strong> sur <strong>{rows.length}</strong> frais réglés
            </p>
            <p className="font-editorial text-lg text-ink-900">
              {totalAmount.toLocaleString("fr-FR")} XAF au total
            </p>
          </div>
          <div className="mt-3 h-1.5 w-full overflow-hidden rounded-full bg-line-200">
            <div
              className="h-full bg-emerald transition-all"
              style={{ width: `${(paidCount / rows.length) * 100}%` }}
            />
          </div>
        </div>

        {/* Confirmation — Membre activé */}
        {isActivated && (
          <div className="mb-6 rounded-md border border-emerald/40 bg-emerald/5 p-7 text-center">
            <p className="font-editorial text-2xl font-medium text-emerald">
              ✓ Compte activé
            </p>
            <p className="mt-3 text-sm text-ink-700">
              Les 3 frais d'adhésion ont été reçus. Tu peux maintenant utiliser
              tous les services de la coopérative — épargne, crédit, transferts.
            </p>
            <button
              onClick={() => router.replace("/")}
              className={buttonClasses({ variant: "success", size: "md" }) + " mt-6"}
            >
              Accéder à mon espace
            </button>
          </div>
        )}

        {/* Coordonnées Mobile Money — saisies une seule fois pour tous les frais */}
        {!isActivated && !allPaid && (
          <div className="mb-6 rounded-md border border-line-200 bg-paper p-5">
            <p className="font-display text-[0.72rem] font-medium uppercase tracking-[0.14em] text-ink-600">
              Tes coordonnées Mobile Money
            </p>
            <div className="mt-3">
              <label className="block text-sm font-medium text-ink-900" htmlFor="phone">
                Numéro Mobile Money
              </label>
              <input
                id="phone"
                name="phone"
                type="tel"
                inputMode="tel"
                value={form.phone}
                onChange={(e) => setForm({ ...form, phone: e.target.value })}
                placeholder="6XX XX XX XX"
                className="mt-2 block w-full rounded-md border border-line-200 bg-paper px-3 py-2 text-ink-900 outline-none transition-colors focus:border-blue-700 focus:ring-1 focus:ring-blue-700"
              />
              <p className="mt-1 text-xs text-ink-600">
                MTN ou Orange — l&apos;opérateur est détecté automatiquement.
              </p>
            </div>
          </div>
        )}

        {error && (
          <p
            role="alert"
            className="mb-4 rounded-md border border-terra-400/40 bg-terra-50/60 px-3 py-2 text-sm text-terra-700"
          >
            {error}
          </p>
        )}

        {/* Liste des 3 frais */}
        {!isActivated && (
          <ul className="space-y-3">
            {rows.map((row) => {
              const isActiveStep =
                activeStepCode === row.code &&
                activePayment &&
                activePayment.statut === "en_attente";

              return (
                <li
                  key={row.code}
                  className={`rounded-md border bg-paper p-5 transition-all ${
                    row.status === "paid"
                      ? "border-emerald/40 bg-emerald/5"
                      : isActiveStep
                      ? "border-blue-700/40 bg-blue-50/40"
                      : "border-line-200"
                  }`}
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <span
                          className={`flex h-6 w-6 items-center justify-center rounded-full text-xs font-semibold ${
                            row.status === "paid"
                              ? "bg-emerald text-white"
                              : isActiveStep
                              ? "bg-blue-700 text-white"
                              : "bg-line-200 text-ink-700"
                          }`}
                        >
                          {row.status === "paid" ? "✓" : ""}
                        </span>
                        <p className="font-editorial text-lg text-ink-900">
                          {row.label}
                        </p>
                      </div>
                      <p className="mt-1 text-xs text-ink-600">
                        {row.description}
                      </p>
                    </div>
                    <div className="text-right">
                      <p className="font-editorial text-lg text-ink-900">
                        {row.montant.toLocaleString("fr-FR")} XAF
                      </p>
                      {row.status === "paid" && (
                        <p className="mt-0.5 text-[11px] font-medium uppercase tracking-wide text-emerald">
                          Payé
                        </p>
                      )}
                      {isActiveStep && (
                        <p className="mt-0.5 text-[11px] font-medium uppercase tracking-wide text-blue-700">
                          En attente PIN
                        </p>
                      )}
                    </div>
                  </div>

                  {/* Action : bouton pour payer ce frais */}
                  {row.status === "unpaid" && !isActiveStep && (
                    <form onSubmit={(e) => onSubmitFee(e, row)} className="mt-4">
                      <button
                        type="submit"
                        disabled={!!submittingCode || !form.phone}
                        className={buttonClasses({
                          variant: "success",
                          size: "sm",
                          fullWidth: true,
                        })}
                      >
                        {submittingCode === row.code
                          ? "Initialisation…"
                          : `Payer ${row.montant.toLocaleString("fr-FR")} XAF`}
                      </button>
                    </form>
                  )}

                  {/* Action : retry si rejeté */}
                  {row.status === "pending" &&
                    row.payment &&
                    row.payment.id !== activePayment?.id && (
                      <p className="mt-3 text-xs text-ink-500">
                        Paiement déjà initié — vérifie ton téléphone.
                      </p>
                    )}

                  {/* Sous-bloc « en attente PIN » + simulateur dev */}
                  {isActiveStep && activePayment && (
                    <div className="mt-4 space-y-3 border-t border-line-200 pt-4">
                      <p className="text-xs text-ink-600">
                        Un code USSD vient d'être poussé sur ton téléphone{" "}
                        <span className="font-mono">{form.phone}</span>. Saisis
                        ton code PIN MoMo pour valider.
                      </p>
                      <p className="text-[11px] text-ink-500">
                        Référence :{" "}
                        <span className="font-mono">
                          {activePayment.reference_externe || activePayment.id}
                        </span>
                      </p>
                      {IS_DEV && (
                        <div className="rounded-md border-2 border-dashed border-terra-500/60 bg-terra-50/30 p-3">
                          <p className="font-display text-[0.7rem] font-semibold uppercase tracking-[0.14em] text-terra-700">
                            🛠️ Mode dev
                          </p>
                          <button
                            type="button"
                            onClick={onSimulate}
                            disabled={simulating}
                            className={
                              buttonClasses({
                                variant: "secondary",
                                size: "sm",
                                fullWidth: true,
                              }) + " mt-2"
                            }
                          >
                            {simulating ? "Simulation…" : "Simuler la confirmation Tara"}
                          </button>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Sous-bloc « rejeté » */}
                  {isActiveStep === false &&
                    activeStepCode === row.code &&
                    activePayment &&
                    activePayment.statut === "rejete" && (
                      <div className="mt-4 rounded-md border border-terra-400/40 bg-terra-50/60 p-3">
                        <p className="text-sm font-medium text-terra-700">
                          Paiement rejeté
                        </p>
                        <p className="mt-1 text-xs text-ink-600">
                          Motif : {activePayment.motif_rejet || "inconnu."}
                        </p>
                        <button
                          onClick={resetActivePayment}
                          className={
                            buttonClasses({ variant: "secondary", size: "sm" }) +
                            " mt-3"
                          }
                        >
                          Réessayer
                        </button>
                      </div>
                    )}
                </li>
              );
            })}
          </ul>
        )}
      </Container>
    </main>
  );
}
