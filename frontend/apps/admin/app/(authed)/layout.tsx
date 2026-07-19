"use client";

import { useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";

import { CommandPalette } from "@/components/command-palette";
import { DocumentPreviewProvider } from "@/components/document-preview";
import { Sidebar, canAccessResource, hrefResource } from "@/components/sidebar";
import {
  adminApi,
  type ApiError,
  type DashboardKpis,
  type Identity,
} from "@/lib/api";


/**
 * Layout authentifié — partagé par toutes les pages staff.
 *
 * Le **sidebar est monté une seule fois** dans cet arbre et ne se re-mount
 * jamais entre les pages : seul `{children}` change quand l'utilisateur
 * navigue de `/dashboard` → `/members` → `/payments` etc. (pattern frame).
 *
 * - Vérifie la session une seule fois au montage
 * - Recharge les KPIs (badges des files d'attente) à chaque changement de
 *   route pour que les chiffres restent à jour après une approbation
 * - Redirige vers `/login` si non-authentifié ou non-staff
 */
export default function AuthedLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const [identity, setIdentity] = useState<Identity | null>(null);
  const [kpis, setKpis] = useState<DashboardKpis | null>(null);
  const [loading, setLoading] = useState(true);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  // Ferme le drawer mobile à chaque navigation (le contenu change).
  useEffect(() => {
    setSidebarOpen(false);
  }, [pathname]);

  // Raccourci global Cmd+K / Ctrl+K — toujours actif tant que le layout est monté.
  useEffect(() => {
    function handle(e: KeyboardEvent) {
      const isMod = e.metaKey || e.ctrlKey;
      if (isMod && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPaletteOpen((v) => !v);
      }
    }
    window.addEventListener("keydown", handle);
    return () => window.removeEventListener("keydown", handle);
  }, []);

  // 1) Identité chargée une seule fois (session check + staff-only)
  useEffect(() => {
    let cancelled = false;
    async function check() {
      try {
        const me = await adminApi.me();
        if (cancelled) return;
        if (!me.is_staff && !me.is_superuser) {
          router.replace("/login?reason=not-staff");
          return;
        }
        setIdentity(me);
      } catch (err) {
        const apiErr = err as ApiError;
        // Toute erreur d'authentification *ou* de transport (proxy en
        // panne, mauvais Host header, CSRF KO, etc.) rejette vers le
        // login. Sans cette garde large, le composant restait sur
        // l'ecran "Chargement..." indefiniment des qu'une 400 remontait
        // du rewrite Next.js.
        if (typeof apiErr?.status === "number") {
          router.replace("/login");
        } else {
          // Erreur reseau brute (fetch a rejete) — on reste prudent.
          router.replace("/login?reason=network");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    check();
    return () => {
      cancelled = true;
    };
  }, [router]);

  // 1bis) Garde RBAC — si la ressource de la route courante n'est pas
  //       autorisée, on renvoie vers la première ressource accessible.
  const currentAllowed = identity
    ? canAccessResource(identity, hrefResource(pathname))
    : true;
  const firstAllowed = identity?.full_access
    ? "dashboard"
    : identity?.resources?.[0];
  useEffect(() => {
    if (!identity || currentAllowed) return;
    if (firstAllowed && `/${firstAllowed}` !== pathname) {
      router.replace(`/${firstAllowed}`);
    }
  }, [identity, currentAllowed, firstAllowed, pathname, router]);

  // 2) KPIs rechargés à chaque changement de route — gardent les badges
  //    à jour après une approbation/un rejet sans recharger toute la page.
  useEffect(() => {
    if (!identity) return;
    let cancelled = false;
    adminApi
      .dashboard()
      .then((k) => {
        if (!cancelled) setKpis(k);
      })
      .catch(() => {
        /* certaines vues n'ont pas besoin des KPIs */
      });
    return () => {
      cancelled = true;
    };
  }, [identity, pathname]);

  if (loading) {
    return (
      <div className="flex min-h-svh items-center justify-center text-ink-600">
        Chargement…
      </div>
    );
  }
  if (!identity) return null;

  return (
    <DocumentPreviewProvider>
    <div className="flex h-svh overflow-hidden bg-cream">
      {/* Sidebar persistant : monté une seule fois (drawer sur mobile). */}
      <Sidebar
        identity={identity}
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        queues={
          kpis
            ? {
                ...kpis.queues,
                escalades_ouvertes: kpis.contentieux.escalades_ouvertes,
              }
            : undefined
        }
      />

      {/* Zone de contenu : seule cette partie scroll + change à la nav. */}
      <main className="flex-1 overflow-y-auto overflow-x-hidden">
        {/* Top bar persistante : hamburger (mobile) + recherche ⌘K */}
        <Topbar
          onMenu={() => setSidebarOpen(true)}
          onOpenSearch={() => setPaletteOpen(true)}
        />

        {/* Conteneur unique : padding responsive cohérent pour TOUTES les vues
            (les pages ne gèrent plus leur propre marge → fini le contenu collé
            au sidebar). Largeur bornée sur très grands écrans, remplie sinon. */}
        <div
          key={pathname}
          className="mx-auto w-full max-w-[112rem] animate-[fadein_180ms_ease-out] px-4 py-6 motion-reduce:animate-none sm:px-6 lg:px-10 lg:py-8"
        >
          {currentAllowed ? (
            children
          ) : (
            <div className="flex min-h-[60vh] flex-col items-center justify-center gap-2 text-center">
              <p className="font-editorial text-xl font-medium text-ink-900">
                Accès non autorisé
              </p>
              <p className="max-w-md text-sm text-ink-600">
                {firstAllowed
                  ? "Redirection vers une section autorisée…"
                  : "Aucune ressource ne t'a été attribuée. Contacte un administrateur."}
              </p>
            </div>
          )}
        </div>
      </main>

      {/* Palette globale — montée au niveau du layout pour rester accessible
          quel que soit l'écran. */}
      <CommandPalette
        open={paletteOpen}
        onClose={() => setPaletteOpen(false)}
      />
    </div>
    </DocumentPreviewProvider>
  );
}


/**
 * Barre supérieure persistante : bouton menu (mobile) à gauche + déclencheur de
 * recherche à droite. Fond translucide « soft » (léger voile + ombre discrète)
 * au lieu d'un filet plein largeur.
 */
function Topbar({
  onMenu,
  onOpenSearch,
}: {
  onMenu: () => void;
  onOpenSearch: () => void;
}) {
  const [isMac, setIsMac] = useState(true);

  useEffect(() => {
    // Détecte la plateforme une fois côté client pour afficher ⌘ vs Ctrl
    setIsMac(/Mac|iPhone|iPod|iPad/i.test(navigator.userAgent));
  }, []);

  return (
    <div className="sticky top-0 z-20 flex items-center justify-between gap-3 bg-cream/80 px-4 py-3 backdrop-blur-md sm:px-6 lg:px-10">
      {/* Menu (mobile uniquement) */}
      <button
        type="button"
        onClick={onMenu}
        aria-label="Ouvrir le menu"
        className="grid size-9 place-items-center rounded-lg border border-line-200 bg-paper text-ink-700 transition-colors hover:border-blue-700 hover:text-blue-700 lg:hidden"
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          className="size-5"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M3 12h18M3 6h18M3 18h18" />
        </svg>
      </button>

      <button
        type="button"
        onClick={onOpenSearch}
        className="group ml-auto inline-flex items-center gap-3 rounded-lg border border-line-200 bg-paper px-3 py-1.5 text-sm text-ink-500 shadow-xs transition-colors hover:border-blue-700 hover:text-blue-700"
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          className="size-4"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <circle cx="11" cy="11" r="8" />
          <path d="m21 21-4.3-4.3" />
        </svg>
        <span className="hidden sm:inline">Recherche</span>
        <kbd className="ml-1 hidden items-center gap-0.5 rounded border border-line-200 bg-cream px-1.5 py-0.5 text-[10px] font-medium tracking-tight text-ink-500 sm:inline-flex">
          {isMac ? "⌘" : "Ctrl"} K
        </kbd>
      </button>
    </div>
  );
}
