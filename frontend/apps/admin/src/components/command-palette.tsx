"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  LayoutDashboard,
  UserPlus,
  HandCoins,
  Wallet,
  Receipt,
  Users,
  SlidersHorizontal,
  Search,
  CornerDownLeft,
  ArrowUp,
  ArrowDown,
  Loader2,
  type LucideIcon,
} from "lucide-react";

import { adminApi, type ApiError } from "@/lib/api";


// --- Types --------------------------------------------------------------

type ItemKind = "page" | "member" | "loan";

type CommandItem = {
  kind: ItemKind;
  id: string;
  label: string;
  sublabel?: string;
  icon: LucideIcon;
  href: string;
};


// --- Static "quick actions" — always there ------------------------------

const PAGES: CommandItem[] = [
  {
    kind: "page",
    id: "p:dashboard",
    label: "Vue d'ensemble",
    sublabel: "KPIs et derniers paiements",
    icon: LayoutDashboard,
    href: "/dashboard",
  },
  {
    kind: "page",
    id: "p:membership-requests",
    label: "Adhésions",
    sublabel: "Demandes en attente d'instruction",
    icon: UserPlus,
    href: "/membership-requests",
  },
  {
    kind: "page",
    id: "p:loan-requests",
    label: "Demandes de crédit",
    sublabel: "Comité crédit",
    icon: HandCoins,
    href: "/loan-requests",
  },
  {
    kind: "page",
    id: "p:loans",
    label: "Crédits",
    sublabel: "Portefeuille complet",
    icon: Wallet,
    href: "/loans",
  },
  {
    kind: "page",
    id: "p:payments",
    label: "Paiements",
    sublabel: "Historique des transactions",
    icon: Receipt,
    href: "/payments",
  },
  {
    kind: "page",
    id: "p:members",
    label: "Membres",
    sublabel: "Annuaire complet",
    icon: Users,
    href: "/members",
  },
  {
    kind: "page",
    id: "p:costs",
    label: "Coûts",
    sublabel: "Frais & taux modifiables",
    icon: SlidersHorizontal,
    href: "/costs",
  },
];


// --- Component -----------------------------------------------------------

export function CommandPalette({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const [query, setQuery] = useState("");
  const [serverResults, setServerResults] = useState<CommandItem[]>([]);
  const [searching, setSearching] = useState(false);
  const [selectedIdx, setSelectedIdx] = useState(0);

  // Reset à l'ouverture
  useEffect(() => {
    if (open) {
      setQuery("");
      setServerResults([]);
      setSelectedIdx(0);
      // Petit délai pour laisser la modale se monter avant de focuser
      requestAnimationFrame(() => inputRef.current?.focus());
    }
  }, [open]);

  // Filtre client-side sur les pages
  const filteredPages = useMemo<CommandItem[]>(() => {
    if (!query.trim()) return PAGES;
    const q = query.trim().toLowerCase();
    return PAGES.filter(
      (p) =>
        p.label.toLowerCase().includes(q) ||
        (p.sublabel ?? "").toLowerCase().includes(q),
    );
  }, [query]);

  // Recherche serveur debounce sur membres + crédits
  useEffect(() => {
    const q = query.trim();
    if (q.length < 2) {
      setServerResults([]);
      setSearching(false);
      return;
    }
    setSearching(true);
    const handle = window.setTimeout(async () => {
      try {
        const [members, loans] = await Promise.all([
          adminApi.members.list({ q }).catch(() => ({ count: 0, results: [] })),
          adminApi.loans.list({ q }).catch(() => ({ count: 0, results: [] })),
        ]);
        const items: CommandItem[] = [];
        for (const m of members.results.slice(0, 5)) {
          items.push({
            kind: "member",
            id: `m:${m.id}`,
            label: `${m.prenom} ${m.nom}`,
            sublabel: `${m.numero_membre} · ${m.statut_display}`,
            icon: Users,
            href: `/members?q=${encodeURIComponent(m.numero_membre)}`,
          });
        }
        for (const l of loans.results.slice(0, 5)) {
          items.push({
            kind: "loan",
            id: `l:${l.id}`,
            label: l.numero_dossier,
            sublabel: `${l.member.prenom} ${l.member.nom} · ${l.statut_display}`,
            icon: Wallet,
            href: `/loans?q=${encodeURIComponent(l.numero_dossier)}`,
          });
        }
        setServerResults(items);
      } catch (err) {
        const apiErr = err as ApiError;
        if (apiErr.status === 401 || apiErr.status === 403) {
          // session expirée — laisse le layout rediriger
        }
        setServerResults([]);
      } finally {
        setSearching(false);
      }
    }, 280);
    return () => window.clearTimeout(handle);
  }, [query]);

  // Liste plate utilisée pour la nav clavier
  const allItems = useMemo<CommandItem[]>(
    () => [...filteredPages, ...serverResults],
    [filteredPages, serverResults],
  );

  // Reset l'index sélectionné quand la liste change
  useEffect(() => {
    setSelectedIdx(0);
  }, [allItems.length]);

  // Raccourcis clavier dans la palette
  useEffect(() => {
    if (!open) return;
    function handle(e: KeyboardEvent) {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
        return;
      }
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setSelectedIdx((i) => Math.min(i + 1, allItems.length - 1));
        return;
      }
      if (e.key === "ArrowUp") {
        e.preventDefault();
        setSelectedIdx((i) => Math.max(i - 1, 0));
        return;
      }
      if (e.key === "Enter") {
        e.preventDefault();
        const item = allItems[selectedIdx];
        if (item) navigate(item);
      }
    }
    window.addEventListener("keydown", handle);
    return () => window.removeEventListener("keydown", handle);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, allItems, selectedIdx]);

  function navigate(item: CommandItem) {
    onClose();
    router.push(item.href);
  }

  if (!open) return null;

  // Trouve l'index pour décider quels groupes afficher
  const hasPages = filteredPages.length > 0;
  const hasServer = serverResults.length > 0;
  const pageStartIdx = 0;
  const serverStartIdx = filteredPages.length;

  return (
    <div
      role="presentation"
      onClick={onClose}
      className="fixed inset-0 z-[60] flex justify-center bg-ink-900/45 px-4 pt-[12vh] backdrop-blur-sm"
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Recherche globale"
        onClick={(e) => e.stopPropagation()}
        className="relative h-fit w-full max-w-2xl overflow-hidden rounded-xl bg-paper shadow-[0_24px_64px_-12px_rgba(14,77,146,0.32)] ring-1 ring-line-200"
      >
        {/* Input */}
        <div className="flex items-center gap-3 border-b border-line-200 px-5 py-4">
          <Search className="size-5 shrink-0 text-ink-500" />
          <input
            ref={inputRef}
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Rechercher un membre, un crédit, ou naviguer…"
            className="flex-1 bg-transparent text-[15px] text-ink-900 placeholder:text-ink-400 outline-none"
          />
          {searching ? (
            <Loader2 className="size-4 animate-spin text-ink-400" />
          ) : (
            <kbd className="hidden rounded border border-line-200 bg-cream px-2 py-0.5 text-[10px] font-medium text-ink-600 sm:inline">
              esc
            </kbd>
          )}
        </div>

        {/* Résultats */}
        <div className="max-h-[60vh] overflow-y-auto">
          {/* Groupe Pages / Actions */}
          {hasPages && (
            <Section title={query.trim() === "" ? "Navigation rapide" : "Actions"}>
              {filteredPages.map((item, i) => (
                <Row
                  key={item.id}
                  item={item}
                  selected={selectedIdx === pageStartIdx + i}
                  onHover={() => setSelectedIdx(pageStartIdx + i)}
                  onClick={() => navigate(item)}
                />
              ))}
            </Section>
          )}

          {/* Groupe résultats serveur */}
          {hasServer && (
            <Section title="Résultats">
              {serverResults.map((item, i) => (
                <Row
                  key={item.id}
                  item={item}
                  selected={selectedIdx === serverStartIdx + i}
                  onHover={() => setSelectedIdx(serverStartIdx + i)}
                  onClick={() => navigate(item)}
                />
              ))}
            </Section>
          )}

          {/* Empty state */}
          {!hasPages && !hasServer && (
            <div className="px-5 py-12 text-center">
              <p className="text-sm text-ink-600">
                {searching ? "Recherche…" : "Aucun résultat."}
              </p>
              {query.trim().length === 1 && (
                <p className="mt-1 text-xs text-ink-400">
                  Tape au moins 2 caractères pour la recherche serveur.
                </p>
              )}
            </div>
          )}
        </div>

        {/* Footer raccourcis */}
        <div className="flex items-center justify-between border-t border-line-200 bg-cream/60 px-5 py-2.5 text-[11px] text-ink-600">
          <div className="flex items-center gap-3">
            <KbdHint icon={ArrowUp} label="navigation" />
            <KbdHint icon={ArrowDown} label="" />
            <KbdHint icon={CornerDownLeft} label="ouvrir" />
          </div>
          <span className="hidden sm:inline">
            <strong className="font-mono text-ink-700">⌘K</strong> pour ouvrir
          </span>
        </div>
      </div>
    </div>
  );
}


function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="py-2">
      <p className="px-5 pb-1 pt-2 text-[10px] font-semibold uppercase tracking-[0.15em] text-ink-500">
        {title}
      </p>
      <div>{children}</div>
    </div>
  );
}


function Row({
  item,
  selected,
  onHover,
  onClick,
}: {
  item: CommandItem;
  selected: boolean;
  onHover: () => void;
  onClick: () => void;
}) {
  const Icon = item.icon;
  return (
    <button
      type="button"
      onMouseEnter={onHover}
      onClick={onClick}
      className={[
        "flex w-full items-center gap-3 px-5 py-2.5 text-left transition-colors",
        selected ? "bg-blue-700 text-white" : "text-ink-800 hover:bg-cream",
      ].join(" ")}
    >
      <div
        className={[
          "flex size-8 shrink-0 items-center justify-center rounded-md",
          selected ? "bg-white/15" : "bg-cream",
        ].join(" ")}
      >
        <Icon
          className={["size-4", selected ? "text-white" : "text-ink-700"].join(" ")}
        />
      </div>
      <div className="min-w-0 flex-1">
        <p
          className={[
            "truncate text-sm font-medium",
            selected ? "text-white" : "text-ink-900",
          ].join(" ")}
        >
          {item.label}
        </p>
        {item.sublabel && (
          <p
            className={[
              "truncate text-xs",
              selected ? "text-white/80" : "text-ink-500",
            ].join(" ")}
          >
            {item.sublabel}
          </p>
        )}
      </div>
      {selected && (
        <CornerDownLeft className="size-3.5 shrink-0 text-white/85" aria-hidden="true" />
      )}
    </button>
  );
}


function KbdHint({ icon: Icon, label }: { icon: LucideIcon; label: string }) {
  return (
    <span className="inline-flex items-center gap-1">
      <kbd className="inline-flex size-5 items-center justify-center rounded border border-line-200 bg-paper">
        <Icon className="size-3 text-ink-700" aria-hidden="true" />
      </kbd>
      {label && <span className="text-ink-600">{label}</span>}
    </span>
  );
}
