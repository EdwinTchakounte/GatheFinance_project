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
  network: PaymentInitInput["network"];
  phone: string;
};

const IS_DEV = process.env.NODE_ENV !== "production";


export default function PortalActivationPage() {
  const router = useRouter();
  const [form, setForm] = useState<FormState>({ network: "MTN", phone: "" });
  const [identity, setIdentity] = useState<Identity | null>(null);
  const [feeMontant, setFeeMontant] = useState<string>("5000");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [payment, setPayment] = useState<PaymentRead | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [simulating, setSimulating] = useState(false);

  // Load identity + the ADHESION fee amount from FeeType (admin-editable).
  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const [me, fees] = await Promise.all([
          portalApi.me(),
          portalApi.payments.fees().catch(() => ({}) as Record<string, { montant: string }>),
        ]);
        if (cancelled) return;
        setIdentity(me);
        // ADHESION fee from DB; falls back to 5000 if not seeded.
        if (fees && fees["ADHESION"]?.montant) setFeeMontant(fees["ADHESION"].montant);
        // Already active? → no need to activate. Send to dashboard.
        if (me.member && me.member.statut === "actif") {
          router.replace("/");
          return;
        }
        // No member profile (= staff session)? Send to dashboard, it handles the case.
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

  // Auto-poll the payment status every 2s while `en_attente`. As soon as it
  // turns `valide`, the _hook_adhesion has flipped Member.statut to actif —
  // we then send the user to the dashboard.
  useEffect(() => {
    if (!payment || payment.statut !== "en_attente") return;
    const id = payment.id;
    const timer = window.setInterval(async () => {
      try {
        const updated = await portalApi.payments.detail(id);
        setPayment(updated);
        if (updated.statut !== "en_attente") window.clearInterval(timer);
      } catch {
        /* swallow */
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
        type: "frais_adhesion",
        montant: Number(feeMontant),
        phone: form.phone,
        network: form.network,
      });
      setPayment(result.payment);
    } catch (err) {
      const apiErr = err as ApiError;
      setError(apiErr.detail ?? "Impossible d'initier le paiement des frais d'adhésion.");
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

  if (loading) {
    return (
      <main className="py-16">
        <Container><p className="text-center text-ink-600">Chargement…</p></Container>
      </main>
    );
  }

  const memberName = identity?.member ? `${identity.member.prenom} ${identity.member.nom}`.trim() : "";

  return (
    <main className="py-12 lg:py-16">
      <Container className="max-w-2xl">
        <header className="mb-8 text-center">
          <span className="label-num">Activer ton compte</span>
          <h1 className="mt-3 font-editorial text-3xl font-medium text-ink-900">
            Bienvenue{memberName ? `, ${memberName}` : ""} !
          </h1>
          <p className="mt-3 text-sm text-ink-600">
            Ta demande d'adhésion a été approuvée. Pour activer ton compte
            membre et accéder à tous les services, règle tes frais d'adhésion.
          </p>
        </header>

        {/* Form — visible until a Payment is created */}
        {!payment ? (
          <form
            onSubmit={onSubmit}
            className="rounded-md border border-line-200 bg-paper p-7"
          >
            <div className="rounded-md bg-cream p-5 text-center">
              <p className="font-display text-[0.72rem] font-medium uppercase tracking-[0.14em] text-ink-600">
                Frais d'adhésion
              </p>
              <p className="mt-1 font-editorial text-4xl font-medium leading-none text-ink-900">
                {Number(feeMontant).toLocaleString("fr-FR")} XAF
              </p>
              <p className="mt-2 text-xs text-ink-600">
                Payé une seule fois. Donne accès à l'épargne, au crédit et à
                tous les services de la coopérative.
              </p>
            </div>

            <div className="mt-6 grid grid-cols-2 gap-4">
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
              {submitting ? "Initialisation…" : "Payer mes frais d'adhésion"}
            </button>
          </form>
        ) : null}

        {/* Pending */}
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

            {IS_DEV ? (
              <div className="mt-7 rounded-md border-2 border-dashed border-terra-500/60 bg-terra-50/30 p-4">
                <p className="font-display text-[0.7rem] font-semibold uppercase tracking-[0.14em] text-terra-700">
                  🛠️ Mode dev — sans clés Tara
                </p>
                <p className="mt-1 text-xs text-ink-600">
                  Simule la confirmation Tara comme si tu venais de saisir ton PIN.
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

        {/* Success — Member is now ACTIF */}
        {payment && payment.statut === "valide" ? (
          <div className="rounded-md border border-emerald/40 bg-emerald/5 p-7 text-center">
            <p className="font-editorial text-2xl font-medium text-emerald">
              ✓ Compte activé
            </p>
            <p className="mt-3 text-sm text-ink-700">
              Ton paiement a été reçu. Tu peux maintenant utiliser tous les
              services de la coopérative — épargne, crédit, transferts.
            </p>
            <button
              onClick={() => router.replace("/")}
              className={buttonClasses({ variant: "success", size: "md" }) + " mt-6"}
            >
              Accéder à mon espace
            </button>
          </div>
        ) : null}

        {/* Rejected */}
        {payment && payment.statut === "rejete" ? (
          <div className="rounded-md border border-terra-400/40 bg-terra-50/60 p-7">
            <p className="font-editorial text-xl font-medium text-terra-700">
              Paiement rejeté
            </p>
            <p className="mt-3 text-sm text-ink-700">
              Motif : {payment.motif_rejet || "Inconnu."}
            </p>
            <button
              onClick={() => setPayment(null)}
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
