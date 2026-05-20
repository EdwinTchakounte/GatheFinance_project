"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { Container, buttonClasses } from "@gathe/ui";

import { portalApi, type ApiError } from "@/lib/api";


type FormState = {
  montant_demande: string;
  duree_mois: string;
  motif: string;
};


export default function PortalLoanRequestPage() {
  const router = useRouter();
  const [eligibility, setEligibility] = useState<{
    eligible: boolean;
    plafond_max: string;
    motifs_ineligibilite: string[];
  } | null>(null);
  const [form, setForm] = useState<FormState>({
    montant_demande: "",
    duree_mois: "12",
    motif: "",
  });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        await portalApi.primeCsrf();
        const el = await portalApi.loans.eligibility();
        if (cancelled) return;
        setEligibility(el);
        if (!el.eligible) {
          // Should not happen if user came from /portal/credit, but stay safe.
          setError("Tu n'es pas éligible pour soumettre une nouvelle demande.");
        }
      } catch (err) {
        const apiErr = err as ApiError;
        if (apiErr.status === 401 || apiErr.status === 403) {
          router.replace("/connexion");
          return;
        }
        setError(apiErr.detail ?? "Impossible de charger l'éligibilité.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [router]);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (submitting) return;
    setError(null);
    setSubmitting(true);
    try {
      const result = await portalApi.loans.create({
        montant_demande: Number(form.montant_demande),
        duree_mois: Number(form.duree_mois),
        motif: form.motif.trim(),
      });
      // Redirect to the deposit flow pre-configured for the fees payment.
      router.push(
        `/epargne/depot?context=credit-fees&request=${result.loan_request.id}`,
      );
    } catch (err) {
      const apiErr = err as ApiError;
      setError(apiErr.detail ?? "Impossible d'envoyer la demande.");
      setSubmitting(false);
    }
  }

  if (loading) {
    return (
      <main className="py-16">
        <Container><p className="text-center text-ink-600">Chargement…</p></Container>
      </main>
    );
  }

  return (
    <main className="py-12 lg:py-16">
      <Container className="max-w-2xl">
        <header className="mb-8">
          <button
            type="button"
            onClick={() => router.push("/credit")}
            className="text-sm text-ink-600 transition-colors hover:text-blue-700"
          >
            ← Retour à mes crédits
          </button>
          <h1 className="mt-3 font-editorial text-3xl font-medium text-ink-900">
            Demande de crédit
          </h1>
          {eligibility?.eligible ? (
            <p className="mt-2 text-sm text-ink-600">
              Plafond éligible :{" "}
              <strong className="text-ink-900">
                {Number(eligibility.plafond_max).toLocaleString("fr-FR")} XAF
              </strong>
            </p>
          ) : null}
        </header>

        {!eligibility?.eligible ? (
          <p className="rounded-md border border-terra-400/40 bg-terra-50/60 p-5 text-center text-terra-700">
            {error ?? "Non éligible."}
          </p>
        ) : (
          <form onSubmit={onSubmit} className="rounded-md border border-line-200 bg-paper p-7">
            <label className="block text-sm font-medium text-ink-900" htmlFor="montant_demande">
              Montant souhaité (XAF)
            </label>
            <input
              id="montant_demande"
              name="montant_demande"
              type="number"
              min={5000}
              max={Number(eligibility.plafond_max)}
              step={1000}
              required
              value={form.montant_demande}
              onChange={(e) => setForm({ ...form, montant_demande: e.target.value })}
              className="mt-2 block w-full rounded-md border border-line-200 bg-paper px-3 py-2 text-ink-900 outline-none transition-colors focus:border-blue-700 focus:ring-1 focus:ring-blue-700"
              placeholder="Ex. 50000"
            />
            <p className="mt-1 text-xs text-ink-600">
              Min. 5 000 XAF · Max. {Number(eligibility.plafond_max).toLocaleString("fr-FR")} XAF
            </p>

            <label className="mt-5 block text-sm font-medium text-ink-900" htmlFor="duree_mois">
              Durée (mois)
            </label>
            <select
              id="duree_mois"
              name="duree_mois"
              required
              value={form.duree_mois}
              onChange={(e) => setForm({ ...form, duree_mois: e.target.value })}
              className="mt-2 block w-full rounded-md border border-line-200 bg-paper px-3 py-2 text-ink-900 outline-none transition-colors focus:border-blue-700 focus:ring-1 focus:ring-blue-700"
            >
              <option value="3">3 mois</option>
              <option value="6">6 mois</option>
              <option value="12">12 mois</option>
              <option value="18">18 mois</option>
              <option value="24">24 mois</option>
              <option value="36">36 mois</option>
            </select>

            <label className="mt-5 block text-sm font-medium text-ink-900" htmlFor="motif">
              Objet de la demande
            </label>
            <textarea
              id="motif"
              name="motif"
              required
              rows={5}
              minLength={20}
              maxLength={2000}
              value={form.motif}
              onChange={(e) => setForm({ ...form, motif: e.target.value })}
              className="mt-2 block w-full rounded-md border border-line-200 bg-paper px-3 py-2 text-ink-900 outline-none transition-colors focus:border-blue-700 focus:ring-1 focus:ring-blue-700"
              placeholder="Explique l'usage prévu du crédit (achat de matériel, fonds de roulement, formation…)."
            />

            {error ? (
              <p
                role="alert"
                className="mt-4 rounded-md border border-terra-400/40 bg-terra-50/60 px-3 py-2 text-sm text-terra-700"
              >
                {error}
              </p>
            ) : null}

            <div className="mt-7 rounded-md bg-cream p-4 text-sm text-ink-700">
              <p>
                <strong>Frais de dossier</strong> : à régler après soumission
                (montant configuré par l'administration). Ta demande passera en
                instruction comité dès le paiement confirmé.
              </p>
            </div>

            <button
              type="submit"
              disabled={submitting}
              className={buttonClasses({ variant: "success", size: "lg", fullWidth: true }) + " mt-6"}
            >
              {submitting ? "Envoi…" : "Soumettre la demande"}
            </button>
          </form>
        )}
      </Container>
    </main>
  );
}
