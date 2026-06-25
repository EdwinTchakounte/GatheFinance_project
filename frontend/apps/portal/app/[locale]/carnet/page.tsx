"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { Container } from "@gathe/ui";

import { portalApi, type ApiError } from "@/lib/api";

type BookletOrder = {
  id: number;
  statut: string;
  created_at: string;
  date_impression?: string;
  date_delivrance?: string;
};

type CoopDocs = {
  reglement_interieur: { url: string | null; label: string };
  carnet_specimen: { url: string | null; label: string };
};

const STATUT_LABEL: Record<string, { label: string; tone: string }> = {
  payee: { label: "Payée — en attente d'impression", tone: "bg-blue-50 text-blue-700 ring-blue-200" },
  en_impression: { label: "En impression", tone: "bg-amber-50 text-amber-700 ring-amber-200" },
  delivree: { label: "Délivrée", tone: "bg-emerald-50 text-emerald-700 ring-emerald-200" },
};


export default function CarnetPage() {
  const router = useRouter();
  const [orders, setOrders] = useState<BookletOrder[]>([]);
  const [docs, setDocs] = useState<CoopDocs | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const [bookletRes, docsRes] = await Promise.all([
          portalApi.booklet.me(),
          portalApi.coopDocuments().catch(() => null),
        ]);
        if (cancelled) return;
        setOrders(bookletRes.results);
        setDocs(docsRes as CoopDocs | null);
      } catch (err) {
        const apiErr = err as ApiError;
        if (apiErr.status === 401 || apiErr.status === 403) {
          router.replace("/connexion");
          return;
        }
        setError(apiErr.detail ?? "Impossible de charger le carnet.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [router]);

  function goPay() {
    router.push("/epargne/depot?context=carnet");
  }

  return (
    <main className="min-h-svh bg-cream py-10">
      <Container>
        <header className="mb-8 max-w-2xl">
          <p className="font-display text-[0.7rem] font-semibold uppercase tracking-[0.18em] text-blue-700">
            Carnet
          </p>
          <h1 className="mt-2 font-editorial text-3xl font-medium text-ink-900 sm:text-4xl">
            Mon carnet de cotisations.
          </h1>
          <p className="mt-2 text-sm text-ink-600">
            Commande ton carnet, consulte le spécimen et le règlement intérieur
            avant de venir le retirer en agence.
          </p>
        </header>

        <div className="grid gap-6 lg:grid-cols-3">
          {/* ─── Section commande (col 2) ─── */}
          <section className="lg:col-span-2">
            <div className="rounded-xl border border-line-200 bg-paper p-6 shadow-sm">
              <div className="mb-5 flex flex-wrap items-start justify-between gap-4">
                <div>
                  <h2 className="font-editorial text-xl text-ink-900">
                    Mes commandes
                  </h2>
                  <p className="mt-1 text-sm text-ink-600">
                    Suivi de l'impression et de la délivrance.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={goPay}
                  className="inline-flex items-center gap-2 rounded-lg bg-blue-700 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition-all hover:bg-blue-800 focus:outline-none focus:ring-2 focus:ring-blue-700/40"
                >
                  Commander un carnet
                </button>
              </div>

              {loading ? (
                <p className="rounded-lg bg-cream/80 p-4 text-sm text-ink-600">
                  Chargement…
                </p>
              ) : error ? (
                <p className="rounded-lg border border-terra-400/40 bg-terra-50/60 p-4 text-sm text-terra-700">
                  {error}
                </p>
              ) : orders.length === 0 ? (
                <div className="rounded-lg border border-dashed border-line-200 bg-cream/50 p-8 text-center">
                  <p className="text-sm text-ink-600">
                    Aucune commande pour l'instant.
                  </p>
                  <p className="mt-1 text-xs text-ink-500">
                    Le paiement des frais de carnet ouvre automatiquement une
                    commande qui sera ensuite imprimée par l'agence.
                  </p>
                </div>
              ) : (
                <ul className="divide-y divide-line-200">
                  {orders.map((o) => {
                    const meta = STATUT_LABEL[o.statut] ?? { label: o.statut, tone: "bg-ink-50 text-ink-700 ring-ink-200" };
                    return (
                      <li key={o.id} className="flex flex-wrap items-center justify-between gap-3 py-4">
                        <div>
                          <p className="text-sm font-medium text-ink-900">
                            Commande #{o.id}
                          </p>
                          <p className="text-xs text-ink-500">
                            Créée le {new Date(o.created_at).toLocaleDateString("fr-CM", { day: "2-digit", month: "long", year: "numeric" })}
                          </p>
                          {o.date_delivrance ? (
                            <p className="text-xs text-emerald-700">
                              Délivrée le {new Date(o.date_delivrance).toLocaleDateString("fr-CM")}
                            </p>
                          ) : null}
                        </div>
                        <span className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium ring-1 ring-inset ${meta.tone}`}>
                          {meta.label}
                        </span>
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>
          </section>

          {/* ─── Section documents (col 1) ─── */}
          <aside className="space-y-4">
            <h2 className="font-display text-[0.7rem] font-semibold uppercase tracking-[0.18em] text-ink-600">
              Documents utiles
            </h2>
            <DocCard
              title="Règlement intérieur"
              hint="Statuts, droits et devoirs du sociétaire."
              url={docs?.reglement_interieur?.url ?? null}
            />
            <DocCard
              title="Spécimen du carnet"
              hint="Aperçu du carnet remis après paiement."
              url={docs?.carnet_specimen?.url ?? null}
            />
            <div className="rounded-xl border border-blue-200 bg-blue-50/50 p-4 text-xs text-blue-900">
              <p className="font-semibold">Bon à savoir</p>
              <p className="mt-1 leading-relaxed">
                Le carnet est imprimé sous 48 h après paiement et retirable en
                agence (Akwa Bercy). Tu seras notifié dès qu'il est prêt.
              </p>
            </div>
          </aside>
        </div>
      </Container>
    </main>
  );
}


function DocCard({ title, hint, url }: { title: string; hint: string; url: string | null }) {
  const available = !!url;
  return (
    <a
      href={url ?? "#"}
      target={available ? "_blank" : undefined}
      rel={available ? "noopener noreferrer" : undefined}
      onClick={(e) => { if (!available) e.preventDefault(); }}
      className={`block rounded-xl border bg-paper p-4 transition-all ${
        available
          ? "border-line-200 hover:border-blue-700 hover:shadow-sm"
          : "border-line-200 opacity-70"
      }`}
    >
      <div className="flex items-start gap-3">
        <span className={`inline-flex size-9 items-center justify-center rounded-lg text-sm font-semibold ${
          available ? "bg-blue-50 text-blue-700" : "bg-ink-50 text-ink-500"
        }`}>
          PDF
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold text-ink-900">{title}</p>
          <p className="mt-0.5 text-xs text-ink-600">
            {available ? hint : "Bientôt disponible."}
          </p>
        </div>
        {available ? (
          <span className="text-xs font-medium text-blue-700">Télécharger →</span>
        ) : null}
      </div>
    </a>
  );
}
