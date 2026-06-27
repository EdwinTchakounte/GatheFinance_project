"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { Container, buttonClasses } from "@gathe/ui";

import {
  portalApi,
  type ApiError,
  type SavingsSnapshot,
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


/**
 * Page index de la section Épargne (CH-3 + collecte).
 *
 * Évite le 404 sur `/<locale>/epargne` et regroupe les 4 portes d'entrée
 * disponibles pour le membre actif :
 *  - Verser sur épargne (cotisation collecte ou épargne classique libre)
 *  - Placer sur épargne classique 12 mois (CH-3 placement)
 *  - Demander un retrait (Tara MoMo ou en agence)
 *  - Voir l'historique des opérations
 */
export default function EpargneIndexPage() {
  const router = useRouter();
  const [savings, setSavings] = useState<SavingsSnapshot | null>(null);
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
        const snap = await portalApi.savings();
        if (!cancelled) setSavings(snap);
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
            Cotisation journalière, épargne classique 12 mois et retraits.
          </p>
        </header>

        {/* Solde */}
        <section className="mt-8 rounded-md border border-line-200 bg-paper p-7">
          <h2 className="font-editorial text-sm font-medium uppercase tracking-[0.14em] text-ink-600">
            Solde d'épargne
          </h2>
          <p className="mt-3 font-editorial text-5xl font-medium leading-none text-ink-900">
            {savings ? formatXAF(savings.solde) : "—"}
          </p>
          {savings ? (
            <p className="mt-3 text-sm text-ink-600">
              Taux annuel appliqué :{" "}
              <span className="font-medium text-ink-900">
                {(Number(savings.taux_interet_applique) * 100).toFixed(2)} %
              </span>
              {" · "}Compte ouvert le {formatDate(savings.date_ouverture)}
            </p>
          ) : null}
        </section>

        {/* 3 actions principales */}
        <section className="mt-8 grid gap-5 md:grid-cols-3">
          <article className="rounded-md border border-line-200 bg-paper p-6">
            <h3 className="font-editorial text-lg font-medium text-ink-900">
              Verser sur épargne
            </h3>
            <p className="mt-2 text-sm text-ink-600">
              Cotisation collecte journalière ou épargne classique libre.
              Paiement Mobile Money ou en agence (Akwa Bercy, avant 17h).
            </p>
            <button
              type="button"
              onClick={() => router.push("/epargne/depot")}
              className={
                buttonClasses({ variant: "success", size: "md", fullWidth: true }) +
                " mt-5"
              }
            >
              Verser
            </button>
          </article>

          <article className="rounded-md border border-line-200 bg-paper p-6">
            <h3 className="font-editorial text-lg font-medium text-ink-900">
              Placer sur 12 mois
            </h3>
            <p className="mt-2 text-sm text-ink-600">
              Bloquer une partie de ton épargne en placement classique pour
              12 mois. Restitution automatique à la maturité (CH-3).
            </p>
            <button
              type="button"
              onClick={() =>
                router.push("/epargne/depot?context=epargne-classique&mode=placement")
              }
              className={
                buttonClasses({ variant: "secondary", size: "md", fullWidth: true }) +
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

        {/* Transactions récentes */}
        <section className="mt-12">
          <div className="flex items-center justify-between">
            <h2 className="font-editorial text-xl font-medium text-ink-900">
              Opérations récentes
            </h2>
            {savings && savings.transactions_recentes.length > 0 ? (
              <Link
                href="/epargne/historique"
                className="text-sm font-medium text-blue-700 hover:underline"
              >
                Voir tout l'historique →
              </Link>
            ) : null}
          </div>
          {savings && savings.transactions_recentes.length > 0 ? (
            <ul className="mt-5 divide-y divide-line-200 rounded-md border border-line-200 bg-paper">
              {savings.transactions_recentes.map((tx) => (
                <li
                  key={tx.id}
                  className="flex items-center justify-between px-5 py-3.5"
                >
                  <div>
                    <p className="font-medium text-ink-900">{tx.type_display}</p>
                    <p className="text-xs text-ink-600">{formatDate(tx.date)}</p>
                  </div>
                  <p
                    className={
                      tx.type_op === "retrait"
                        ? "font-mono text-terra-700"
                        : "font-mono text-emerald"
                    }
                  >
                    {tx.type_op === "retrait" ? "−" : "+"}
                    {formatXAF(tx.montant)}
                  </p>
                </li>
              ))}
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
