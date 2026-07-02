"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { Container, buttonClasses } from "@gathe/ui";

import { portalApi, type ApiError, type Campaign } from "@/lib/api";


function formatXAF(amount: string): string {
  const n = Number(amount);
  if (Number.isNaN(n)) return amount;
  return n.toLocaleString("fr-FR", { maximumFractionDigits: 0 }) + " XAF";
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString("fr-FR", {
      day: "2-digit",
      month: "short",
      year: "numeric",
    });
  } catch {
    return iso;
  }
}


/**
 * Catalogue public des campagnes micro-crédit ouvertes (LOT 11).
 *
 * Miroir de la liste `/campaigns` du mobile : le membre parcourt les
 * campagnes actives, lit le flyer + les conditions, puis « Postule » — ce
 * qui l'envoie sur le formulaire de demande pré-réglé sur la voie campagne
 * avec la bonne campagne sélectionnée.
 */
export default function CampagnesPage() {
  const router = useRouter();
  const [items, setItems] = useState<Campaign[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    portalApi.loans
      .activeCampaigns({ limit: 50 })
      .then((res) => {
        if (!cancelled) setItems(res.results);
      })
      .catch((err) => {
        const apiErr = err as ApiError;
        if (!cancelled)
          setError(apiErr.detail ?? "Impossible de charger les campagnes.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <main className="min-h-svh bg-cream py-12 lg:py-16">
      <Container className="max-w-5xl">
        <button
          type="button"
          onClick={() => router.push("/credit")}
          className="text-sm text-ink-600 transition-colors hover:text-blue-700"
        >
          ← Retour à mes crédits
        </button>

        <header className="mt-4">
          <span className="label-num">Micro-crédit</span>
          <h1 className="mt-3 font-editorial text-3xl font-medium leading-tight text-ink-900">
            Campagnes ouvertes
          </h1>
          <p className="mt-1 text-sm text-ink-600">
            Des campagnes ciblées permettent d'obtenir un micro-crédit même sans
            ancienneté. Choisis une campagne qui correspond à ton profil et
            postule — ta demande passera en validation puis en instruction.
          </p>
        </header>

        {loading ? (
          <p className="mt-10 text-center text-sm text-ink-600">Chargement…</p>
        ) : error ? (
          <p className="mt-10 mx-auto max-w-md rounded-md border border-terra-400/40 bg-terra-50/60 p-5 text-center text-terra-700">
            {error}
          </p>
        ) : items.length === 0 ? (
          <div className="mt-10 rounded-md border border-dashed border-line-200 bg-paper/70 p-10 text-center">
            <p className="font-editorial text-lg font-medium text-ink-900">
              Aucune campagne ouverte pour le moment
            </p>
            <p className="mt-2 text-sm text-ink-600">
              Reviens plus tard — les nouvelles campagnes apparaissent ici dès
              leur ouverture. Tu peux aussi demander un crédit via une autre voie
              depuis la page Crédit.
            </p>
          </div>
        ) : (
          <section className="mt-8 grid gap-6 md:grid-cols-2">
            {items.map((c) => (
              <article
                key={c.id}
                className="flex flex-col overflow-hidden rounded-md border border-line-200 bg-paper"
              >
                {/* Flyer */}
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={c.flyer_url}
                  alt={c.nom}
                  className="h-40 w-full object-cover"
                />
                <div className="flex flex-1 flex-col p-5">
                  <span className="inline-block w-fit rounded-full bg-emerald/15 px-2.5 py-0.5 text-[11px] font-semibold uppercase tracking-wide text-emerald">
                    {c.profil_cible || "Tous profils"}
                  </span>
                  <h2 className="mt-2 font-editorial text-lg font-medium text-ink-900">
                    {c.nom}
                  </h2>
                  <dl className="mt-3 space-y-1 text-sm text-ink-600">
                    <div className="flex justify-between gap-3">
                      <dt>Montant</dt>
                      <dd className="font-mono text-ink-900">
                        {formatXAF(c.montant_min)} – {formatXAF(c.montant_max)}
                      </dd>
                    </div>
                    <div className="flex justify-between gap-3">
                      <dt>Taux</dt>
                      <dd className="font-mono text-ink-900">
                        {(Number(c.taux_interet) * 100).toFixed(0)} %
                      </dd>
                    </div>
                    <div className="flex justify-between gap-3">
                      <dt>Recouvrement</dt>
                      <dd className="font-mono text-ink-900">
                        {c.nb_jours_recouvrement} j
                      </dd>
                    </div>
                    <div className="flex justify-between gap-3">
                      <dt>Clôture</dt>
                      <dd className="text-ink-900">{formatDate(c.date_fin)}</dd>
                    </div>
                  </dl>
                  <button
                    type="button"
                    onClick={() =>
                      router.push(
                        `/credit/demande?voie=campaign&campaign=${c.id}`,
                      )
                    }
                    className={
                      buttonClasses({
                        variant: "success",
                        size: "md",
                        fullWidth: true,
                      }) + " mt-5"
                    }
                  >
                    Postuler à cette campagne
                  </button>
                </div>
              </article>
            ))}
          </section>
        )}
      </Container>
    </main>
  );
}
