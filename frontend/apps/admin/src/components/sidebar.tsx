"use client";

import { usePathname, useRouter } from "next/navigation";
import Link from "next/link";
import {
  LayoutDashboard,
  UserPlus,
  HandCoins,
  Wallet,
  Receipt,
  Users,
  SlidersHorizontal,
  LogOut,
  RefreshCw,
  Settings2,
  Megaphone,
  Gavel,
  ArrowDownToLine,
  FileText,
  BellRing,
  FileEdit,
  ScrollText,
  MessageSquareText,
  LifeBuoy,
  Notebook,
  CalendarClock,
  Newspaper,
  GitBranch,
  Coins,
  ShieldCheck,
  Handshake,
  PanelLeftClose,
  PanelLeftOpen,
  Activity,
} from "lucide-react";

import { adminApi, type Identity } from "@/lib/api";


type QueueKey =
  | "adhesions_en_attente"
  | "credits_en_instruction"
  | "credits_a_traiter"
  | "avaliste_pending"
  | "campaign_validation_pending"
  | "escalades_ouvertes";

type NavItem = {
  href: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  queueKey?: QueueKey;
};

type NavSection = {
  title: string;
  items: NavItem[];
};

// Refonte 2026 — la barre latérale passe d'une liste plate de ~29 onglets à des
// SECTIONS thématiques (purement visuel : la logique RBAC filtre toujours item
// par item via `hrefResource`). Aucun onglet n'est retiré ni renommé.
const NAV_SECTIONS: NavSection[] = [
  {
    title: "Pilotage",
    items: [{ href: "/dashboard", label: "Vue d'ensemble", icon: LayoutDashboard }],
  },
  {
    title: "Adhésions & membres",
    items: [
      { href: "/adhesions", label: "Pipeline adhésion", icon: GitBranch },
      { href: "/membership-requests", label: "Adhésions", icon: UserPlus, queueKey: "adhesions_en_attente" },
      { href: "/members", label: "Membres", icon: Users },
      { href: "/access", label: "Utilisateurs & accès", icon: ShieldCheck },
    ],
  },
  {
    title: "Crédit",
    items: [
      { href: "/loan-requests", label: "Demandes de crédit", icon: HandCoins, queueKey: "credits_a_traiter" },
      { href: "/loans", label: "Crédits", icon: Wallet },
      { href: "/loan-renewals", label: "Reconductions", icon: RefreshCw },
      { href: "/avaliste", label: "Avalistes / cautions", icon: Handshake, queueKey: "avaliste_pending" },
      { href: "/lender-tranches", label: "Pool prêteurs", icon: Coins },
      { href: "/escalations", label: "Escalades judiciaires", icon: Gavel, queueKey: "escalades_ouvertes" },
    ],
  },
  {
    title: "Épargne & versements",
    items: [
      { href: "/payments", label: "Paiements", icon: Receipt },
      { href: "/withdrawals", label: "Retraits épargne", icon: ArrowDownToLine },
      { href: "/booklet-orders", label: "Commandes carnet", icon: Notebook },
      { href: "/antidated-entries", label: "Saisies antidatées", icon: CalendarClock },
      { href: "/collecte-preferences", label: "Fin de mois collecte", icon: CalendarClock },
      { href: "/special-collections", label: "Collectes particulières", icon: Coins },
      { href: "/renewals", label: "Renouvellements épargne", icon: RefreshCw },
    ],
  },
  {
    title: "Campagnes & contenu",
    items: [
      { href: "/campaigns", label: "Campagnes micro-crédit", icon: Megaphone, queueKey: "campaign_validation_pending" },
      { href: "/announcements", label: "Annonces", icon: BellRing },
      { href: "/blog", label: "Articles vitrine", icon: Newspaper },
      { href: "/comments", label: "Commentaires", icon: MessageSquareText },
      { href: "/support", label: "Support membres", icon: LifeBuoy },
    ],
  },
  {
    title: "Configuration",
    items: [
      { href: "/costs", label: "Coûts", icon: SlidersHorizontal },
      { href: "/app-settings", label: "Paramètres", icon: Settings2 },
      // Planification (cron) = outil de recette, masqué en production.
      { href: "/cooperative-asset", label: "Documents officiels", icon: FileText },
      { href: "/forms", label: "Formulaires", icon: FileEdit },
      { href: "/audit", label: "Journal d'audit", icon: ScrollText },
      { href: "/supervision", label: "Supervision", icon: Activity },
    ],
  },
];


// Clé de ressource RBAC d'un chemin admin : 1er segment sans le slash.
// Ex. "/booklet-orders" → "booklet-orders", "/forms/12" → "forms".
export function hrefResource(pathname: string): string {
  return pathname.replace(/^\//, "").split("/")[0] || "dashboard";
}

// Un utilisateur voit-il cette ressource ? (accès total → tout ; sinon liste).
export function canAccessResource(identity: Identity | null, key: string): boolean {
  if (!identity) return false;
  if (identity.full_access || !identity.resources) return true;
  return identity.resources.includes(key);
}


export function Sidebar({
  identity,
  queues,
  open = false,
  onClose,
  collapsed = false,
  onToggleCollapse,
}: {
  identity: Identity | null;
  queues?: {
    adhesions_en_attente: number;
    credits_en_instruction: number;
    credits_a_traiter?: number;
    avaliste_pending?: number;
    campaign_validation_pending?: number;
    escalades_ouvertes?: number;
  };
  /** Ouvert en drawer sur mobile (ignoré sur ≥ lg où la barre est statique). */
  open?: boolean;
  onClose?: () => void;
  /**
   * Replié en rail d'icônes sur DESKTOP (≥ lg) uniquement. Sur mobile la barre
   * reste un drawer plein — le repli n'a de sens que quand elle est statique.
   * Toutes les bascules de repli passent donc par des variantes `lg:`.
   */
  collapsed?: boolean;
  onToggleCollapse?: () => void;
}) {
  const pathname = usePathname();
  const router = useRouter();

  async function onLogout() {
    try { await adminApi.logout(); } catch { /* swallow */ }
    router.replace("/login");
  }

  // RBAC — on ne garde que les sections dont au moins un onglet est autorisé.
  const sections = NAV_SECTIONS.map((s) => ({
    ...s,
    items: s.items.filter((item) =>
      canAccessResource(identity, hrefResource(item.href)),
    ),
  })).filter((s) => s.items.length > 0);

  return (
    <>
      {/* Voile mobile — ferme le drawer au tap (invisible ≥ lg). */}
      <div
        aria-hidden={!open}
        onClick={onClose}
        className={[
          "fixed inset-0 z-30 bg-ink-950/40 backdrop-blur-sm transition-opacity duration-300 lg:hidden",
          open ? "opacity-100" : "pointer-events-none opacity-0",
        ].join(" ")}
      />

      <aside
        className={[
          "fixed inset-y-0 left-0 z-40 flex w-[17rem] shrink-0 flex-col border-r border-line-100 bg-paper",
          "transition-[transform,width] duration-300 ease-[cubic-bezier(0.16,1,0.3,1)]",
          "lg:static lg:z-auto lg:translate-x-0",
          collapsed ? "lg:w-[4.75rem]" : "lg:w-64",
          open ? "translate-x-0 shadow-xl" : "-translate-x-full lg:shadow-none",
        ].join(" ")}
      >
        {/* Header — logo officiel (stacké) + bouton de repli à droite */}
        <div
          className={[
            "py-5",
            collapsed ? "px-5 lg:px-2" : "px-5",
          ].join(" ")}
        >
          <div
            className={[
              "flex items-center gap-2",
              collapsed ? "lg:justify-center" : "",
            ].join(" ")}
          >
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src="/images/logo.png"
              alt="GATHE Finance"
              className={["h-8 w-auto", collapsed ? "lg:hidden" : ""].join(" ")}
            />
            {/* Marque compacte (« G ») — visible seulement en rail replié. */}
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src="/images/mark.png"
              alt="GATHE Finance"
              className={[
                "size-8 rounded-md",
                collapsed ? "hidden lg:block" : "hidden",
              ].join(" ")}
            />
            {/* Bascule de repli — DESKTOP uniquement (drawer sur mobile). */}
            {onToggleCollapse ? (
              <button
                type="button"
                onClick={onToggleCollapse}
                aria-label={collapsed ? "Déplier le menu" : "Replier le menu"}
                title={collapsed ? "Déplier le menu" : "Replier le menu"}
                className={[
                  "ml-auto hidden shrink-0 place-items-center rounded-md p-1.5 text-ink-400 transition-colors hover:bg-cream hover:text-ink-700 lg:grid",
                  collapsed ? "lg:hidden" : "",
                ].join(" ")}
              >
                <PanelLeftClose className="size-4" aria-hidden="true" />
              </button>
            ) : null}
          </div>
          <p
            className={[
              "mt-2 text-[0.68rem] font-semibold uppercase tracking-[0.16em] text-terra-600",
              collapsed ? "lg:hidden" : "",
            ].join(" ")}
          >
            Administration
          </p>
        </div>

        {/* En rail replié : un bouton « déplier » sous la marque. */}
        {onToggleCollapse && collapsed ? (
          <button
            type="button"
            onClick={onToggleCollapse}
            aria-label="Déplier le menu"
            title="Déplier le menu"
            className="mx-2 mb-1 hidden place-items-center rounded-md p-1.5 text-ink-400 transition-colors hover:bg-cream hover:text-ink-700 lg:grid"
          >
            <PanelLeftOpen className="size-4" aria-hidden="true" />
          </button>
        ) : null}

        {/* Nav — sections thématiques */}
        <nav className="flex-1 overflow-y-auto px-3 pb-4">
          {sections.map((section) => (
            <div key={section.title} className="mb-4">
              <p
                className={[
                  "px-3 pb-1.5 pt-2 text-[0.64rem] font-semibold uppercase tracking-[0.14em] text-ink-400",
                  collapsed ? "lg:hidden" : "",
                ].join(" ")}
              >
                {section.title}
              </p>
              <ul className="space-y-0.5">
                {section.items.map(({ href, label, icon: Icon, queueKey }) => {
                  // Match exact ou descendance par segment — évite que `/members`
                  // s'active sur `/membership-requests`.
                  const active = pathname === href || pathname.startsWith(href + "/");
                  const count = queueKey && queues ? queues[queueKey] : undefined;
                  return (
                    <li key={href}>
                      <Link
                        href={href}
                        onClick={onClose}
                        aria-current={active ? "page" : undefined}
                        // Rail replié : le libellé passe en infobulle native.
                        title={collapsed ? label : undefined}
                        className={[
                          "group relative flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm transition-colors",
                          collapsed ? "lg:justify-center lg:px-0" : "",
                          active
                            ? "bg-blue-50 font-semibold text-blue-800"
                            : "font-medium text-ink-600 hover:bg-cream hover:text-ink-900",
                        ].join(" ")}
                      >
                        <Icon
                          className={[
                            "size-[1.05rem] shrink-0",
                            active ? "text-blue-700" : "text-ink-400 group-hover:text-ink-600",
                          ].join(" ")}
                          aria-hidden="true"
                        />
                        <span
                          className={[
                            "flex-1 truncate",
                            collapsed ? "lg:hidden" : "",
                          ].join(" ")}
                        >
                          {label}
                        </span>
                        {count && count > 0 ? (
                          <>
                            <span
                              className={[
                                "rounded-full px-1.5 py-0.5 font-mono text-[0.68rem] font-semibold",
                                collapsed ? "lg:hidden" : "",
                                active
                                  ? "bg-blue-700 text-white"
                                  : "bg-terra-500/15 text-terra-700",
                              ].join(" ")}
                            >
                              {count}
                            </span>
                            {/* Rail replié : pastille compacte sur l'icône. */}
                            <span
                              aria-hidden="true"
                              className={[
                                "absolute right-1.5 top-1.5 size-2 rounded-full ring-2 ring-paper",
                                collapsed ? "hidden lg:block" : "hidden",
                                active ? "bg-blue-700" : "bg-terra-500",
                              ].join(" ")}
                            />
                          </>
                        ) : null}
                      </Link>
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
        </nav>

        {/* User */}
        <div className="border-t border-line-100 p-3">
          {identity ? (
            <div
              className={[
                "rounded-xl bg-cream px-3 py-2.5",
                collapsed ? "lg:px-2 lg:py-2" : "",
              ].join(" ")}
            >
              <p
                className={[
                  "truncate text-sm font-medium text-ink-900",
                  collapsed ? "lg:hidden" : "",
                ].join(" ")}
              >
                {identity.email}
              </p>
              <p
                className={[
                  "mt-0.5 text-xs text-ink-500",
                  collapsed ? "lg:hidden" : "",
                ].join(" ")}
              >
                {identity.is_superuser
                  ? "Superuser"
                  : identity.groups.length
                    ? identity.groups.join(", ")
                    : "Staff"}
              </p>
              <button
                type="button"
                onClick={onLogout}
                title="Se déconnecter"
                className={[
                  "mt-2 inline-flex items-center gap-1.5 text-xs font-medium text-terra-700 transition-colors hover:text-terra-800",
                  collapsed ? "lg:mt-0 lg:w-full lg:justify-center" : "",
                ].join(" ")}
              >
                <LogOut className="size-3.5" aria-hidden="true" />
                <span className={collapsed ? "lg:hidden" : ""}>Se déconnecter</span>
              </button>
            </div>
          ) : null}
        </div>
      </aside>
    </>
  );
}
