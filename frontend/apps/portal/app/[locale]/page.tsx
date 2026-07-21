"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { Wallet } from "lucide-react";

import { Container, buttonClasses, EmptyState, Skeleton, SkeletonList } from "@gathe/ui";

import {
  portalApi,
  type ApiError,
  type ClassicSavingsSnapshot,
  type Identity,
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


export default function PortalDashboardPage() {
  const router = useRouter();
  const [identity, setIdentity] = useState<Identity | null>(null);
  // PARITE MOBILE . le dashboard mobile affiche 2 soldes (epargne classique
  // + collecte journaliere). On replique cote portail web pour que les
  // chiffres correspondent strictement entre les deux canaux membre.
  const [savings, setSavings] = useState<SavingsSnapshot | null>(null);
  const [classicSavings, setClassicSavings] =
    useState<ClassicSavingsSnapshot | null>(null);
  const [unreadNotifs, setUnreadNotifs] = useState(0);
  // D4 . Statut renouvellement annuel pour banniere.
  const [renewalNeeded, setRenewalNeeded] = useState<{
    days_until_expiry: number | null;
    statut: string;
  } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const me = await portalApi.me();
        if (cancelled) return;
        if (!me.member) {
          // Internal staff without a member profile — they should use the admin instead.
          setIdentity(me);
          setSavings(null);
          setLoading(false);
          return;
        }
        const [snap, classicSnap] = await Promise.all([
          portalApi.savings(),
          portalApi.classicSavings().catch(() => null),
        ]);
        if (cancelled) return;
        setIdentity(me);
        setSavings(snap);
        setClassicSavings(classicSnap);
        // Compteur notifications — best-effort, on n'échoue pas le dashboard.
        portalApi.notifications
          .list(true)
          .then((res) => {
            if (!cancelled) setUnreadNotifs(res.unread_count);
          })
          .catch(() => undefined);
        // D4 . Statut renouvellement annuel . best-effort pour banniere.
        portalApi
          .renewalStatus()
          .then((res) => {
            if (cancelled) return;
            if (res.needs_renewal || res.statut === "suspendu") {
              setRenewalNeeded({
                days_until_expiry: res.days_until_expiry,
                statut: res.statut,
              });
            }
          })
          .catch(() => undefined);
      } catch (err) {
        const apiErr = err as ApiError;
        if (apiErr.status === 401 || apiErr.status === 403) {
          router.replace("/connexion");
          return;
        }
        setError(apiErr.detail ?? "Impossible de charger l'espace membre.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [router]);

  async function onLogout() {
    try {
      await portalApi.logout();
    } finally {
      router.replace("/connexion");
    }
  }

  if (loading) {
    return (
      <main className="min-h-svh bg-cream py-16">
        <Container>
          <Skeleton className="mb-8 h-9 w-56" />
          <SkeletonList count={4} cardClassName="h-24" />
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

  if (!identity?.member) {
    return (
      <main className="min-h-svh bg-cream py-20">
        <Container>
          <div className="mx-auto max-w-md rounded-md border border-line-200 bg-paper p-7 text-center">
            <h2 className="font-editorial text-xl text-ink-900">
              Compte interne
            </h2>
            <p className="mt-3 text-sm text-ink-600">
              Ce compte est rattaché au personnel. Utilise le dashboard
              administrateur ou{" "}
              <a href="/django-admin/" className="font-medium text-blue-700 hover:underline">
                /django-admin/
              </a>
              .
            </p>
            <button onClick={onLogout} className={buttonClasses({ variant: "secondary", size: "md" }) + " mt-6"}>
              Se déconnecter
            </button>
          </div>
        </Container>
      </main>
    );
  }

  const m = identity.member;
  const isSuspended = m.statut === "suspendu";

  return (
    <main className="min-h-svh bg-cream py-12 lg:py-16">
      <Container className="max-w-5xl">
        {/* Header */}
        <header className="flex flex-wrap items-end justify-between gap-4 border-b border-line-200 pb-6">
          <div>
            <span className="label-num">Espace membre</span>
            <h1 className="mt-3 font-editorial text-3xl font-medium leading-tight text-ink-900">
              Bonjour, {m.prenom} {m.nom}
            </h1>
            <p className="mt-1 text-sm text-ink-600">
              Membre n° <span className="font-mono">{m.numero_membre}</span>
              {" · "}
              <span className={
                m.statut === "actif"
                  ? "font-medium text-emerald"
                  : "font-medium text-terra-600"
              }>
                {m.statut === "actif" ? "Compte actif" : `Compte ${m.statut}`}
              </span>
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Link
              href="/notifications"
              className={
                buttonClasses({ variant: "secondary", size: "sm" }) +
                " relative"
              }
            >
              Notifications
              {unreadNotifs > 0 ? (
                <span className="ml-1.5 inline-flex h-5 min-w-[1.25rem] items-center justify-center rounded-full bg-terra-600 px-1.5 text-xs font-semibold text-white">
                  {unreadNotifs > 9 ? "9+" : unreadNotifs}
                </span>
              ) : null}
            </Link>
            <button onClick={onLogout} className={buttonClasses({ variant: "ghost", size: "sm" })}>
              Se déconnecter
            </button>
          </div>
        </header>

        {/* D4 . Banniere renouvellement annuel . visible si needs_renewal */}
        {renewalNeeded && renewalNeeded.statut !== "suspendu" ? (
          <div className="mt-6 rounded-lg border border-amber-300 bg-amber-50/70 p-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="font-display text-xs font-semibold uppercase tracking-wider text-amber-800">
                  Renouvellement à venir
                </p>
                <p className="mt-1 text-sm text-ink-700">
                  {renewalNeeded.days_until_expiry !== null &&
                  renewalNeeded.days_until_expiry < 0
                    ? `Ton anniversaire annuel est dépassé de ${Math.abs(renewalNeeded.days_until_expiry)} jour(s). Régularise vite pour éviter la suspension.`
                    : renewalNeeded.days_until_expiry === 0
                      ? "Aujourd'hui est ton anniversaire annuel. Renouvelle dès maintenant."
                      : `Plus que ${renewalNeeded.days_until_expiry} jour(s) avant ton renouvellement annuel.`}
                </p>
              </div>
              <Link
                href="/renouvellement-adhesion"
                className="rounded-md bg-amber-700 px-3 py-1.5 text-xs font-semibold text-white hover:bg-amber-800"
              >
                Renouveler maintenant →
              </Link>
            </div>
          </div>
        ) : null}

        {/* Suspended members : big activation CTA instead of the savings dashboard */}
        {isSuspended ? (
          <section className="mt-10 rounded-md border border-terra-400/40 bg-terra-50/40 p-8 text-center">
            <span className="label-num mx-auto">Action requise</span>
            <h2 className="mt-3 font-editorial text-2xl font-medium text-ink-900">
              Active ton compte membre
            </h2>
            <p className="mx-auto mt-3 max-w-xl text-sm text-ink-700">
              Ton compte est suspendu tant que tes frais ne sont pas réglés.
              Une fois le paiement validé, tu accèdes à l'épargne, au crédit et à
              tous les services de la coopérative. Ton numéro, ton solde d'épargne
              et ton historique sont conservés.
            </p>
            <button
              onClick={() => router.push("/activation")}
              className={buttonClasses({ variant: "success", size: "lg" }) + " mt-6"}
            >
              Régler mes frais
            </button>
          </section>
        ) : null}

        {/* Below — only for active members */}
        {!isSuspended && (<>
        {/* Soldes — parite mobile (epargne classique + collecte journaliere) */}
        <section className="mt-10 grid gap-6 md:grid-cols-3">
          <div className="md:col-span-2 grid gap-4 sm:grid-cols-2">
            {/* Epargne classique — solde principal du membre (libre + placement) */}
            <div className="rounded-md border border-line-200 bg-paper p-6">
              <h2 className="font-editorial text-xs font-medium uppercase tracking-[0.14em] text-ink-600">
                Mon épargne
              </h2>
              <p className="mt-3 font-editorial text-4xl font-medium leading-none text-ink-900">
                {classicSavings ? formatXAF(classicSavings.solde) : "—"}
              </p>
              {classicSavings ? (
                <p className="mt-2 text-xs text-ink-600">
                  Compte ouvert le {formatDate(classicSavings.date_ouverture)}
                </p>
              ) : null}
            </div>
            {/* Collecte journaliere — cotisation Article 4 */}
            <div className="rounded-md border border-line-200 bg-paper p-6">
              <h2 className="font-editorial text-xs font-medium uppercase tracking-[0.14em] text-ink-600">
                Ma collecte journalière
              </h2>
              <p className="mt-3 font-editorial text-4xl font-medium leading-none text-ink-900">
                {savings ? formatXAF(savings.solde) : "—"}
              </p>
              {savings ? (
                <p className="mt-2 text-xs text-ink-600">
                  Taux annuel :{" "}
                  <span className="font-medium text-ink-900">
                    {(Number(savings.taux_interet_applique) * 100).toFixed(2)} %
                  </span>
                </p>
              ) : null}
            </div>
          </div>

          <div className="rounded-md border border-line-200 bg-cream p-7">
            <h2 className="font-editorial text-sm font-medium uppercase tracking-[0.14em] text-ink-600">
              Actions
            </h2>
            <button
              type="button"
              onClick={() => router.push("/epargne")}
              className={buttonClasses({ variant: "success", size: "md", fullWidth: true }) + " mt-4"}
            >
              Verser mon épargne
            </button>
            <button
              type="button"
              onClick={() => router.push("/credit")}
              className={buttonClasses({ variant: "secondary", size: "md", fullWidth: true }) + " mt-3"}
            >
              Mes crédits
            </button>
            <button
              type="button"
              onClick={() => router.push("/epargne/retrait")}
              className={buttonClasses({ variant: "ghost", size: "md", fullWidth: true }) + " mt-3"}
            >
              Demander un retrait
            </button>
            <button
              type="button"
              onClick={() => router.push("/actualites")}
              className={buttonClasses({ variant: "ghost", size: "md", fullWidth: true }) + " mt-3"}
            >
              Actualités
            </button>
            <p className="mt-3 text-xs text-ink-600">
              Déposer, demander un crédit, retirer ton épargne (Mobile Money ou en agence).
            </p>
          </div>
        </section>

        {/* Transactions récentes — flux unifié, badge de source (cotisation
            collecte vs épargne classique) pour dissocier les deux produits. */}
        {(() => {
          const merged = [
            ...(savings?.transactions_recentes ?? []).map(
              (tx) => ({ tx, source: "collecte" as const }),
            ),
            ...(classicSavings?.transactions_recentes ?? []).map(
              (tx) => ({ tx, source: "classique" as const }),
            ),
          ]
            .sort(
              (a, b) =>
                new Date(b.tx.date).getTime() - new Date(a.tx.date).getTime(),
            )
            .slice(0, 6);
          return (
            <section className="mt-12">
              <h2 className="font-editorial text-xl font-medium text-ink-900">
                Transactions récentes
              </h2>
              {merged.length > 0 ? (
                <ul className="mt-5 divide-y divide-line-200 rounded-md border border-line-200 bg-paper">
                  {merged.map((e) => {
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
                <EmptyState
                  icon={Wallet}
                  title="Aucune transaction"
                  message="Effectue ton premier dépôt quand tu veux, il apparaîtra ici."
                  className="mt-5"
                />
              )}
            </section>
          );
        })()}
        </>)}
      </Container>
    </main>
  );
}
