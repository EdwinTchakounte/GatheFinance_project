"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";

import { Container, buttonClasses } from "@gathe/ui";

import { LikeButton } from "@/components/social/like-button";
import { CommentsSection } from "@/components/social/comments-section";
import { portalApi, type Campaign } from "@/lib/api";

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
 * Détail d'une campagne micro-crédit + interactions sociales (like +
 * commentaires) — parité avec l'écran détail campagne du mobile.
 */
export default function CampagneDetailPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const id = Number(params?.id);

  const [campaign, setCampaign] = useState<Campaign | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!Number.isFinite(id)) return;
    let cancelled = false;
    portalApi.loans
      .activeCampaigns({ limit: 50 })
      .then((res) => {
        if (!cancelled) setCampaign(res.results.find((c) => c.id === id) ?? null);
      })
      .catch(() => undefined)
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [id]);

  return (
    <main className="min-h-svh bg-cream py-12 lg:py-16">
      <Container className="max-w-3xl">
        <button
          type="button"
          onClick={() => router.push("/credit/campagnes")}
          className="text-sm text-ink-600 transition-colors hover:text-blue-700"
        >
          ← Retour aux campagnes
        </button>

        {loading ? (
          <p className="mt-10 text-center text-sm text-ink-600">Chargement…</p>
        ) : !campaign ? (
          <p className="mt-10 mx-auto max-w-md rounded-md border border-line-200 bg-paper p-6 text-center text-sm text-ink-600">
            Campagne introuvable ou clôturée.
          </p>
        ) : (
          <div className="mt-6 space-y-6">
            <article className="overflow-hidden rounded-md border border-line-200 bg-paper">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={campaign.flyer_url}
                alt={campaign.nom}
                className="h-52 w-full object-cover"
              />
              <div className="p-6">
                <span className="inline-block w-fit rounded-full bg-emerald/15 px-2.5 py-0.5 text-[11px] font-semibold uppercase tracking-wide text-emerald">
                  {campaign.profil_cible || "Tous profils"}
                </span>
                <h1 className="mt-2 font-editorial text-2xl font-medium text-ink-900">
                  {campaign.nom}
                </h1>
                <dl className="mt-4 grid grid-cols-2 gap-3 text-sm text-ink-600">
                  <div>
                    <dt className="text-ink-500">Montant</dt>
                    <dd className="font-mono text-ink-900">
                      {formatXAF(campaign.montant_min)} –{" "}
                      {formatXAF(campaign.montant_max)}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-ink-500">Taux</dt>
                    <dd className="font-mono text-ink-900">
                      {(Number(campaign.taux_interet) * 100).toFixed(0)} %
                    </dd>
                  </div>
                  <div>
                    <dt className="text-ink-500">Recouvrement</dt>
                    <dd className="font-mono text-ink-900">
                      {campaign.nb_jours_recouvrement} j
                    </dd>
                  </div>
                  <div>
                    <dt className="text-ink-500">Clôture</dt>
                    <dd className="text-ink-900">{formatDate(campaign.date_fin)}</dd>
                  </div>
                </dl>

                <div className="mt-5 flex flex-wrap items-center gap-3">
                  <LikeButton kind="campaigns" id={campaign.id} />
                  <button
                    type="button"
                    onClick={() =>
                      router.push(
                        `/credit/demande?voie=campaign&campaign=${campaign.id}`,
                      )
                    }
                    className={buttonClasses({ variant: "success", size: "md" })}
                  >
                    Postuler à cette campagne
                  </button>
                </div>
              </div>
            </article>

            <CommentsSection kind="campaigns" id={campaign.id} />
          </div>
        )}
      </Container>
    </main>
  );
}
