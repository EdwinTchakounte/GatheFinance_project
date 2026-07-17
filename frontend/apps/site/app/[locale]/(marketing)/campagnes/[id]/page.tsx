import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { setRequestLocale } from "next-intl/server";

import { Container } from "@gathe/ui";
import { PageHeader } from "@/components/page-shell";
import {
  ApplyForm,
  fmtDate,
  fmtXAF,
  type Campaign,
} from "@/components/campaigns-public";

const BACKEND = (process.env.CMS_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

type Params = { params: Promise<{ locale: string; id: string }> };

async function getCampaign(id: string): Promise<Campaign | null> {
  try {
    const res = await fetch(`${BACKEND}/api/v1/loans/campaigns/${encodeURIComponent(id)}/`, {
      cache: "no-store",
      headers: { Accept: "application/json" },
    });
    if (!res.ok) return null;
    return (await res.json()) as Campaign;
  } catch {
    return null;
  }
}

export async function generateMetadata({ params }: Params): Promise<Metadata> {
  const { id } = await params;
  const c = await getCampaign(id);
  if (!c) return { title: "Campagne micro-crédit" };
  return {
    title: `${c.nom} — Campagne micro-crédit`,
    description: `Micro-crédit GATHE Finance pour « ${c.profil_cible} » : de ${fmtXAF(
      c.montant_min,
    )} à ${fmtXAF(c.montant_max)}. Postule en ligne.`,
    openGraph: {
      title: c.nom,
      description: `Micro-crédit pour « ${c.profil_cible} »`,
      images: c.flyer_url ? [{ url: c.flyer_url }] : undefined,
    },
  };
}

export default async function CampaignDetailPage({ params }: Params) {
  const { locale, id } = await params;
  setRequestLocale(locale);
  const c = await getCampaign(id);
  if (!c) notFound();

  const open = c.is_open !== false;

  return (
    <>
      <PageHeader
        eyebrow="Micro-crédit"
        title={c.nom}
        lead={`Campagne ciblée « ${c.profil_cible} » — de ${fmtXAF(
          c.montant_min,
        )} à ${fmtXAF(c.montant_max)}, taux ${(Number(c.taux_interet) * 100).toFixed(
          0,
        )} %.`}
        homeLabel="Accueil"
        image={c.flyer_url}
      />

      <section className="section-pad bg-cream">
        <Container>
          <div className="grid gap-8 md:grid-cols-[1.1fr_1fr]">
            {/* Visuel + infos */}
            <div>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={c.flyer_url}
                alt={c.nom}
                className="w-full rounded-2xl object-cover shadow-sm"
              />
              <dl className="mt-6 grid grid-cols-2 gap-4 text-sm">
                <div>
                  <dt className="text-ink-500">Montant</dt>
                  <dd className="font-semibold text-ink-900">
                    {fmtXAF(c.montant_min)} → {fmtXAF(c.montant_max)}
                  </dd>
                </div>
                <div>
                  <dt className="text-ink-500">Taux</dt>
                  <dd className="font-semibold text-ink-900">
                    {(Number(c.taux_interet) * 100).toFixed(0)} %
                  </dd>
                </div>
                <div>
                  <dt className="text-ink-500">Clôture</dt>
                  <dd className="font-semibold text-ink-900">{fmtDate(c.date_fin)}</dd>
                </div>
                <div>
                  <dt className="text-ink-500">Profil ciblé</dt>
                  <dd className="font-semibold text-ink-900">{c.profil_cible}</dd>
                </div>
              </dl>
            </div>

            {/* Candidature */}
            <div>
              {open ? (
                <ApplyForm campaign={c} />
              ) : (
                <div className="rounded-2xl border border-line-200 bg-paper p-6">
                  <p className="font-display text-lg text-ink-900">
                    Campagne clôturée
                  </p>
                  <p className="mt-1 text-sm text-ink-600">
                    Les candidatures pour cette campagne sont fermées. Découvre les
                    campagnes ouvertes.
                  </p>
                  <a
                    href={locale === "fr" ? "/campagnes" : `/${locale}/campagnes`}
                    className="mt-4 inline-flex text-sm font-semibold text-emerald hover:underline"
                  >
                    Voir les campagnes ouvertes →
                  </a>
                </div>
              )}
            </div>
          </div>
        </Container>
      </section>
    </>
  );
}
