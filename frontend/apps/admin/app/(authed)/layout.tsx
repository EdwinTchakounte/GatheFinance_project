"use client";

import { useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";

import { CommandPalette } from "@/components/command-palette";
import { Sidebar } from "@/components/sidebar";
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
        if (apiErr.status === 401 || apiErr.status === 403) {
          router.replace("/login");
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
    <div className="flex h-svh bg-cream overflow-hidden">
      {/* Sidebar persistant : monté une seule fois, scroll interne si besoin. */}
      <Sidebar identity={identity} queues={kpis?.queues} />

      {/* Zone de contenu : seule cette partie scroll + change à la nav. */}
      <main className="flex-1 overflow-y-auto overflow-x-hidden">
        {/* Top bar persistante : déclencheur recherche + ⌘K */}
        <SearchTrigger onOpen={() => setPaletteOpen(true)} />

        <div
          key={pathname}
          className="animate-[fadein_180ms_ease-out] motion-reduce:animate-none"
        >
          {children}
        </div>
      </main>

      {/* Palette globale — montée au niveau du layout pour rester accessible
          quel que soit l'écran. */}
      <CommandPalette
        open={paletteOpen}
        onClose={() => setPaletteOpen(false)}
      />
    </div>
  );
}


/**
 * Barre supérieure persistante avec le déclencheur de recherche.
 * Affiche le raccourci clavier `⌘K` (ou `Ctrl K` sous Windows/Linux).
 */
function SearchTrigger({ onOpen }: { onOpen: () => void }) {
  const [isMac, setIsMac] = useState(true);

  useEffect(() => {
    // Détecte la plateforme une fois côté client pour afficher ⌘ vs Ctrl
    setIsMac(/Mac|iPhone|iPod|iPad/i.test(navigator.userAgent));
  }, []);

  return (
    <div className="sticky top-0 z-10 flex items-center justify-end gap-3 border-b border-line-200 bg-paper/85 px-6 py-3 backdrop-blur-md">
      <button
        type="button"
        onClick={onOpen}
        className="group inline-flex items-center gap-3 rounded-md border border-line-200 bg-cream px-3 py-1.5 text-sm text-ink-600 transition-colors hover:border-blue-700 hover:text-blue-700"
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
        <span>Recherche</span>
        <kbd className="ml-2 inline-flex items-center gap-0.5 rounded border border-line-200 bg-paper px-1.5 py-0.5 text-[10px] font-medium tracking-tight text-ink-600">
          {isMac ? "⌘" : "Ctrl"} K
        </kbd>
      </button>
    </div>
  );
}
