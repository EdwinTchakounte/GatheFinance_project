"use client";

import { useEffect, useState } from "react";
import { ArrowUpRight } from "lucide-react";

import { Container } from "@gathe/ui";
import { Link } from "@/i18n/navigation";
import { fmtXAF, type Campaign } from "@/lib/campaign-format";

/**
 * Section « Campagnes en cours » de la home vitrine. Les campagnes sont
 * pré-chargées côté serveur (SSR/ISR) et passées en `initialItems` → rendu
 * immédiat, sans pop-in. Fallback client si le SSR est vide (snapshot ISR
 * généré à froid, backend injoignable au build) pour rester résilient. Le bloc
 * disparaît proprement s'il n'y a aucune campagne ouverte.
 */
export function CampaignsTeaser({
  initialItems,
}: {
  initialItems?: Campaign[];
}) {
  const preloaded = Array.isArray(initialItems) && initialItems.length > 0;
  const [items, setItems] = useState<Campaign[]>(
    preloaded ? initialItems.slice(0, 3) : [],
  );
  const [loaded, setLoaded] = useState(preloaded);

  useEffect(() => {
    if (preloaded) return;
    fetch("/api/campaigns")
      .then((r) => r.json())
      .then((d) =>
        setItems(Array.isArray(d?.results) ? d.results.slice(0, 3) : []),
      )
      .catch(() => setItems([]))
      .finally(() => setLoaded(true));
  }, [preloaded]);

  if (!loaded || items.length === 0) return null;

  return (
    <section className="relative isolate overflow-hidden section-pad bg-cream">
      <Container className="relative">
        <div className="flex flex-wrap items-end justify-between gap-6 pb-2">
          <div>
            <span className="font-display text-[0.72rem] font-semibold uppercase tracking-[0.18em] text-emerald">
              Micro-crédit
            </span>
            <h2 className="mt-3 font-editorial text-section font-medium text-ink-900">
              Campagnes en cours
            </h2>
            <p className="mt-2 max-w-2xl text-sm text-ink-600">
              Des campagnes ciblées pour obtenir un micro-crédit — pour
              certaines, même sans être membre.
            </p>
          </div>
          <Link
            href="/campagnes"
            className="group/lnk inline-flex items-center gap-1.5 pb-1 text-sm font-semibold text-emerald transition-colors hover:text-emerald/80"
          >
            Voir toutes les campagnes
            <ArrowUpRight
              aria-hidden="true"
              className="size-4 transition-transform group-hover/lnk:translate-x-0.5 group-hover/lnk:-translate-y-0.5"
            />
          </Link>
        </div>

        <div className="mt-12 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {items.map((c) => (
            <Link
              key={c.id}
              href="/campagnes"
              className="group flex flex-col overflow-hidden rounded-lg border border-line-200 bg-paper transition-shadow hover:shadow-md"
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={c.flyer_url}
                alt={c.nom}
                loading="lazy"
                decoding="async"
                className="h-40 w-full object-cover"
              />
              <div className="flex flex-1 flex-col p-5">
                <span className="inline-block w-fit rounded-full bg-emerald/15 px-2.5 py-0.5 text-[11px] font-semibold uppercase tracking-wide text-emerald">
                  {c.profil_cible || "Tous profils"}
                </span>
                <h3 className="mt-2 font-editorial text-lg font-medium text-ink-900">
                  {c.nom}
                </h3>
                <p className="mt-1 text-sm text-ink-600">
                  {fmtXAF(c.montant_min)} – {fmtXAF(c.montant_max)}
                </p>
                <span className="mt-3 inline-flex items-center gap-1 text-sm font-semibold text-emerald">
                  Postuler
                  <ArrowUpRight className="size-4 transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5" />
                </span>
              </div>
            </Link>
          ))}
        </div>
      </Container>
    </section>
  );
}
