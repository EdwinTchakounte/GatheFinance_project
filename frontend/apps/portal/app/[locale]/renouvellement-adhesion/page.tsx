"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { Container, buttonClasses } from "@gathe/ui";

import { portalApi, type ApiError } from "@/lib/api";


type RenewalStatus = Awaited<ReturnType<typeof portalApi.renewalStatus>>;


function fmtAmount(value: string | null): string {
  if (!value) return "—";
  const n = Number(value);
  if (!Number.isFinite(n)) return value;
  return n.toLocaleString("fr-FR");
}


function fmtDate(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleDateString("fr-FR", {
      day: "2-digit",
      month: "long",
      year: "numeric",
    });
  } catch {
    return iso;
  }
}


export default function MembershipRenewalPage() {
  const router = useRouter();
  const [status, setStatus] = useState<RenewalStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    portalApi
      .renewalStatus()
      .then((res) => {
        if (!cancelled) setStatus(res);
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

  const isSuspended = status?.statut === "suspendu";
  const tone = isSuspended
    ? "border-rose-300 bg-rose-50/60"
    : status?.in_warning_window
      ? "border-amber-300 bg-amber-50/60"
      : "border-blue-200 bg-blue-50/40";

  return (
    <Container>
      <header className="border-b border-line-200 pb-6 pt-10">
        <button
          type="button"
          onClick={() => router.push("/")}
          className="text-sm text-ink-600 hover:text-blue-700"
        >
          ← Retour au tableau de bord
        </button>
        <h1 className="mt-3 font-editorial text-3xl font-medium text-ink-900">
          Renouveler mon adhésion
        </h1>
        <p className="mt-2 text-sm text-ink-600">
          Chaque année, le règlement intérieur (Art. 3) prévoit le
          renouvellement de l'adhésion par le paiement du nouveau carnet.
          Ton numéro, ton solde épargne et ton historique restent
          identiques.
        </p>
      </header>

      <section className="mt-8 space-y-6">
        {loading ? (
          <p className="rounded-md border border-dashed border-line-200 bg-paper/70 p-8 text-center text-sm text-ink-600">
            Chargement…
          </p>
        ) : error ? (
          <div className="rounded-md border border-rose-300 bg-rose-50/60 px-4 py-2.5 text-sm text-rose-700">
            {error}
          </div>
        ) : status ? (
          <>
            <div className={`rounded-lg border ${tone} p-5`}>
              <h2 className="font-display text-sm font-semibold uppercase tracking-wider text-ink-700">
                {isSuspended
                  ? "Ton compte est suspendu"
                  : status.needs_renewal
                    ? "Renouvellement à effectuer"
                    : "Adhésion à jour"}
              </h2>
              <p className="mt-2 text-sm text-ink-700">
                {isSuspended ? (
                  <>
                    Ton compte est <strong>suspendu</strong> car la période
                    annuelle est dépassée de plus de {status.grace_days}{" "}
                    jours. Paie ton carnet pour réactiver immédiatement
                    tes accès.
                  </>
                ) : status.days_until_expiry !== null &&
                  status.days_until_expiry < 0 ? (
                  <>
                    Ton anniversaire annuel était le{" "}
                    <strong>{fmtDate(status.prochaine_echeance_iso)}</strong>.
                    Tu disposes encore de {status.grace_days +
                      status.days_until_expiry}{" "}
                    jour(s) de grâce pour régulariser sans suspension.
                  </>
                ) : status.days_until_expiry !== null &&
                  status.days_until_expiry === 0 ? (
                  <>
                    Aujourd'hui est ton <strong>anniversaire annuel</strong>.
                    Renouvelle ton adhésion dès maintenant pour éviter
                    toute interruption.
                  </>
                ) : status.in_warning_window ? (
                  <>
                    Plus que{" "}
                    <strong>{status.days_until_expiry} jour(s)</strong>{" "}
                    avant ton anniversaire annuel (
                    {fmtDate(status.prochaine_echeance_iso)}).
                  </>
                ) : (
                  <>
                    Prochain renouvellement le{" "}
                    <strong>{fmtDate(status.prochaine_echeance_iso)}</strong>.
                    Tu pourras renouveler à partir de{" "}
                    {status.lead_days} jour(s) avant cette date.
                  </>
                )}
              </p>
            </div>

            <div className="rounded-lg border border-line-200 bg-paper p-6 shadow-sm">
              <h3 className="font-display text-xs font-semibold uppercase tracking-wider text-ink-500">
                Détails du paiement
              </h3>
              <dl className="mt-4 grid grid-cols-2 gap-4 text-sm">
                <div>
                  <dt className="text-xs text-ink-500">Frais carnet annuel</dt>
                  <dd className="mt-1 font-mono text-lg font-semibold text-ink-900">
                    {fmtAmount(status.carnet_fee_xaf)} XAF
                  </dd>
                </div>
                <div>
                  <dt className="text-xs text-ink-500">Canal</dt>
                  <dd className="mt-1 text-base text-ink-900">
                    Mobile Money (Tara)
                  </dd>
                </div>
              </dl>

              <p className="mt-5 text-xs text-ink-500">
                Le paiement met à jour ta date d'anniversaire annuel. Si
                ton compte était suspendu pour non-renouvellement, il
                redevient actif immédiatement après validation Tara.
              </p>

              {status.needs_renewal || isSuspended ? (
                <button
                  type="button"
                  onClick={() =>
                    router.push("/epargne/depot?context=renewal-carnet")
                  }
                  className={`mt-6 ${buttonClasses({ variant: "success", size: "md" })}`}
                >
                  Payer mon carnet annuel
                </button>
              ) : (
                <p className="mt-6 text-sm text-ink-600">
                  Tu pourras initier le paiement quand la fenêtre de
                  renouvellement s'ouvrira (
                  {status.lead_days} jour(s) avant l'anniversaire).
                </p>
              )}
            </div>

            <details className="rounded-md border border-line-200 bg-paper/70 p-4 text-xs text-ink-600">
              <summary className="cursor-pointer font-medium text-ink-800">
                Comment fonctionne le renouvellement ?
              </summary>
              <ul className="mt-3 list-disc space-y-1 pl-5">
                <li>Numéro membre, solde épargne et historique inchangés.</li>
                <li>
                  Le carnet en cours reste utilisé jusqu'à épuisement.
                </li>
                <li>
                  Suspension automatique après{" "}
                  {status.grace_days} jour(s) sans paiement.
                </li>
                <li>
                  Réactivation instantanée au paiement (si compte
                  suspendu).
                </li>
              </ul>
            </details>
          </>
        ) : null}
      </section>
    </Container>
  );
}
