"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { Container, buttonClasses } from "@gathe/ui";

import {
  portalApi,
  type ApiError,
  type ClassicSavingsSnapshot,
  type SavingsSnapshot,
  type SavingsTransaction,
} from "@/lib/api";


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


// Source d'une opération — sert à dissocier visuellement la cotisation
// (collecte journalière) de l'épargne classique dans un flux unifié.
type Source = "collecte" | "classique";
type RecentEntry = { tx: SavingsTransaction; source: Source };


/**
 * Page index de la section Épargne (CH-3 + collecte).
 *
 * Dissocie explicitement les DEUX produits d'épargne du membre :
 *  - Cotisation collecte journalière (SavingsAccount)
 *  - Épargne classique 12 mois (ClassicSavingsAccount)
 *
 * Deux cartes de solde séparées + un flux d'opérations récentes unifié où
 * chaque ligne porte un badge de source (« Cotisation » vs « Épargne »).
 */
export default function EpargneIndexPage() {
  const router = useRouter();
  const [savings, setSavings] = useState<SavingsSnapshot | null>(null);
  const [classic, setClassic] = useState<ClassicSavingsSnapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const me = await portalApi.me();
        if (cancelled) return;
        if (!me.member) {
          router.replace("/");
          return;
        }
        if (me.member.statut !== "actif") {
          // Membre suspendu / temporaire : on renvoie sur le dashboard qui
          // affiche le bandeau d'activation.
          router.replace("/");
          return;
        }
        // Les deux comptes sont chargés en parallèle. L'épargne classique est
        // créée à la volée côté backend si elle n'existe pas (solde 0).
        const [snap, classicSnap] = await Promise.all([
          portalApi.savings(),
          portalApi.classicSavings().catch(() => null),
        ]);
        if (!cancelled) {
          setSavings(snap);
          setClassic(classicSnap);
        }
      } catch (err) {
        const apiErr = err as ApiError;
        if (apiErr.status === 401 || apiErr.status === 403) {
          router.replace("/connexion");
          return;
        }
        setError(apiErr.detail ?? "Impossible de charger ton épargne.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [router]);

  if (loading) {
    return (
      <main className="min-h-svh bg-cream py-20">
        <Container>
          <p className="text-center text-ink-600">Chargement…</p>
        </Container>
      </main>
    );
  }

  if (error) {
    return (
      <main className="min-h-svh bg-cream py-20">
        <Container>
          <p className="mx-auto max-w-md rounded-md border border-terra-400/40 bg-terra-50/60 p-5 text-center text-terra-700">
            {error}
          </p>
        </Container>
      </main>
    );
  }

  // Flux unifié : on fusionne les 2 ledgers en taguant la source, puis on trie
  // par date décroissante. Chaque produit ne renvoie que ses ~10 dernières.
  const recent: RecentEntry[] = [
    ...(savings?.transactions_recentes ?? []).map(
      (tx): RecentEntry => ({ tx, source: "collecte" }),
    ),
    ...(classic?.transactions_recentes ?? []).map(
      (tx): RecentEntry => ({ tx, source: "classique" }),
    ),
  ]
    .sort((a, b) => new Date(b.tx.date).getTime() - new Date(a.tx.date).getTime())
    .slice(0, 8);

  return (
    <main className="min-h-svh bg-cream py-12 lg:py-16">
      <Container className="max-w-5xl">
        {/* Breadcrumb / retour */}
        <Link
          href="/"
          className="text-sm text-ink-600 hover:text-ink-900 hover:underline"
        >
          ← Retour au tableau de bord
        </Link>

        {/* Header */}
        <header className="mt-4">
          <span className="label-num">Épargne</span>
          <h1 className="mt-3 font-editorial text-3xl font-medium leading-tight text-ink-900">
            Mon épargne
          </h1>
          <p className="mt-1 text-sm text-ink-600">
            Deux produits distincts : la collecte journalière et
            l'épargne classique 12 mois.
          </p>
        </header>

        {/* Deux soldes DISSOCIÉS */}
        <section className="mt-8 grid gap-5 md:grid-cols-2">
          {/* Cotisation collecte */}
          <article className="rounded-md border border-blue-200 bg-blue-50/40 p-7">
            <div className="flex items-center gap-2">
              <span className="inline-block rounded-full bg-blue-100 px-2.5 py-0.5 text-[11px] font-semibold uppercase tracking-wide text-blue-700">
                Collecte
              </span>
              <h2 className="font-editorial text-sm font-medium text-ink-600">
                Collecte journalière
              </h2>
            </div>
            <p className="mt-3 font-editorial text-4xl font-medium leading-none text-ink-900">
              {savings ? formatXAF(savings.solde) : "—"}
            </p>
            {savings ? (
              <p className="mt-3 text-xs text-ink-600">
                Compte ouvert le {formatDate(savings.date_ouverture)}
              </p>
            ) : null}
          </article>

          {/* Épargne classique */}
          <article className="rounded-md border border-emerald/30 bg-emerald/5 p-7">
            <div className="flex items-center gap-2">
              <span className="inline-block rounded-full bg-emerald/15 px-2.5 py-0.5 text-[11px] font-semibold uppercase tracking-wide text-emerald">
                Épargne
              </span>
              <h2 className="font-editorial text-sm font-medium text-ink-600">
                Épargne classique 12 mois
              </h2>
            </div>
            <p className="mt-3 font-editorial text-4xl font-medium leading-none text-ink-900">
              {classic ? formatXAF(classic.solde) : formatXAF("0")}
            </p>
            <p className="mt-3 text-xs text-ink-600">
              {classic
                ? `Compte ouvert le ${formatDate(classic.date_ouverture)}`
                : "Aucun dépôt classique pour le moment."}
            </p>
          </article>
        </section>

        {/* Actions — versements dissociés par type de produit */}
        <section className="mt-8 grid gap-5 md:grid-cols-2">
          <article className="rounded-md border border-line-200 bg-paper p-6">
            <span className="inline-block rounded-full bg-blue-100 px-2.5 py-0.5 text-[11px] font-semibold uppercase tracking-wide text-blue-700">
              Collecte
            </span>
            <h3 className="mt-3 font-editorial text-lg font-medium text-ink-900">
              Verser ma collecte
            </h3>
            <p className="mt-2 text-sm text-ink-600">
              Collecte journalière. Minimum 1 000 XAF/jour, par multiples de 50.
              Mobile Money ou en agence (Akwa Bercy, avant 17h).
            </p>
            <button
              type="button"
              onClick={() => router.push("/epargne/depot?context=savings")}
              className={
                buttonClasses({ variant: "secondary", size: "md", fullWidth: true }) +
                " mt-5"
              }
            >
              Verser une collecte
            </button>
          </article>

          <article className="rounded-md border border-line-200 bg-paper p-6">
            <span className="inline-block rounded-full bg-emerald/15 px-2.5 py-0.5 text-[11px] font-semibold uppercase tracking-wide text-emerald">
              Épargne
            </span>
            <h3 className="mt-3 font-editorial text-lg font-medium text-ink-900">
              Verser sur épargne classique
            </h3>
            <p className="mt-2 text-sm text-ink-600">
              Dépôt libre (retrait à tout moment) ou placement 12 mois.
              Minimum 1 000 XAF.
            </p>
            <button
              type="button"
              onClick={() =>
                router.push("/epargne/depot?context=epargne-classique")
              }
              className={
                buttonClasses({ variant: "success", size: "md", fullWidth: true }) +
                " mt-5"
              }
            >
              Verser sur épargne
            </button>
          </article>
        </section>

        {/* Actions secondaires : placement + retrait */}
        <section className="mt-5 grid gap-5 md:grid-cols-2">
          <article className="rounded-md border border-line-200 bg-paper p-6">
            <h3 className="font-editorial text-lg font-medium text-ink-900">
              Placer sur 12 mois
            </h3>
            <p className="mt-2 text-sm text-ink-600">
              Bloquer une partie de ton épargne classique en placement pour
              12 mois. Restitution automatique à la maturité (CH-3).
            </p>
            <button
              type="button"
              onClick={() =>
                router.push("/epargne/depot?context=epargne-classique&mode=placement")
              }
              className={
                buttonClasses({ variant: "ghost", size: "md", fullWidth: true }) +
                " mt-5"
              }
            >
              Placer
            </button>
          </article>

          <article className="rounded-md border border-line-200 bg-paper p-6">
            <h3 className="font-editorial text-lg font-medium text-ink-900">
              Demander un retrait
            </h3>
            <p className="mt-2 text-sm text-ink-600">
              Sur ton solde libre (placements bloqués exclus). Payout Tara MoMo
              ou retrait en agence après validation.
            </p>
            <button
              type="button"
              onClick={() => router.push("/epargne/retrait")}
              className={
                buttonClasses({ variant: "ghost", size: "md", fullWidth: true }) +
                " mt-5"
              }
            >
              Retirer
            </button>
          </article>
        </section>

        {/* Opérations récentes — flux unifié avec badge de source */}
        <section className="mt-12">
          <div className="flex items-center justify-between">
            <h2 className="font-editorial text-xl font-medium text-ink-900">
              Opérations récentes
            </h2>
            <div className="flex items-center gap-4">
              <Link
                href="/paiements"
                className="text-sm font-medium text-blue-700 hover:underline"
              >
                Mes reçus →
              </Link>
              {recent.length > 0 ? (
                <Link
                  href="/epargne/historique"
                  className="text-sm font-medium text-blue-700 hover:underline"
                >
                  Voir tout l'historique →
                </Link>
              ) : null}
            </div>
          </div>
          {recent.length > 0 ? (
            <ul className="mt-5 divide-y divide-line-200 rounded-md border border-line-200 bg-paper">
              {recent.map((e) => {
                const isCollecte = e.source === "collecte";
                const isRetrait = e.tx.type_op === "retrait";
                return (
                  <li
                    key={`${e.source}-${e.tx.id}`}
                    className="flex items-center justify-between px-5 py-3.5"
                  >
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <span
                          className={
                            "inline-block rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide " +
                            (isCollecte
                              ? "bg-blue-100 text-blue-700"
                              : "bg-emerald/15 text-emerald")
                          }
                        >
                          {isCollecte ? "Collecte" : "Épargne"}
                        </span>
                        <p className="truncate font-medium text-ink-900">
                          {e.tx.type_display}
                        </p>
                      </div>
                      <p className="mt-0.5 text-xs text-ink-600">
                        {formatDate(e.tx.date)}
                      </p>
                    </div>
                    <p
                      className={
                        isRetrait
                          ? "font-mono text-terra-700"
                          : "font-mono text-emerald"
                      }
                    >
                      {isRetrait ? "−" : "+"}
                      {formatXAF(e.tx.montant)}
                    </p>
                  </li>
                );
              })}
            </ul>
          ) : (
            <p className="mt-5 rounded-md border border-dashed border-line-200 bg-paper/70 p-8 text-center text-sm text-ink-600">
              Aucune opération pour le moment. Effectue ton premier versement
              quand tu veux.
            </p>
          )}
        </section>
      </Container>
    </main>
  );
}
