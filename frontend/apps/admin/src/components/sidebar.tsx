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
  FileCheck,
  RefreshCw,
  Settings2,
  Megaphone,
  Gavel,
  ArrowDownToLine,
  Clock,
  FileText,
} from "lucide-react";

import { adminApi, type Identity } from "@/lib/api";


type QueueKey =
  | "adhesions_en_attente"
  | "credits_en_instruction"
  | "campaign_validation_pending"
  | "escalades_ouvertes";

type NavItem = {
  href: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  queueKey?: QueueKey;
};

const NAV: NavItem[] = [
  { href: "/dashboard", label: "Vue d'ensemble", icon: LayoutDashboard },
  { href: "/membership-requests", label: "Adhésions", icon: UserPlus, queueKey: "adhesions_en_attente" },
  { href: "/loan-requests", label: "Demandes de crédit", icon: HandCoins, queueKey: "credits_en_instruction" },
  { href: "/loans", label: "Crédits", icon: Wallet },
  { href: "/payments", label: "Paiements", icon: Receipt },
  { href: "/withdrawals", label: "Retraits épargne", icon: ArrowDownToLine },
  { href: "/members", label: "Membres", icon: Users },
  // Refonte 2026 — LOT 1 + LOT 5 + LOT 16.
  { href: "/brc", label: "Justificatifs BRC", icon: FileCheck },
  { href: "/renewals", label: "Renouvellements épargne", icon: RefreshCw },
  {
    href: "/campaigns",
    label: "Campagnes micro-crédit",
    icon: Megaphone,
    queueKey: "campaign_validation_pending",
  },
  {
    href: "/escalations",
    label: "Escalades judiciaires",
    icon: Gavel,
    queueKey: "escalades_ouvertes",
  },
  { href: "/costs", label: "Coûts", icon: SlidersHorizontal },
  // P2 — Tunables règlement 2026 (BRC, ancienneté, collecte, épargne,
  // lender, funding, eligibility, seizure, judicial, campagne).
  { href: "/app-settings", label: "Paramètres 2026", icon: Settings2 },
  // Recette — éditer la cadence des cron + run-now (django-q schedules).
  { href: "/cron-schedules", label: "Planification (cron)", icon: Clock },
  // Documents officiels (règlement intérieur PDF joint au mail de bienvenue).
  { href: "/cooperative-asset", label: "Documents officiels", icon: FileText },
];


export function Sidebar({
  identity,
  queues,
}: {
  identity: Identity | null;
  queues?: {
    adhesions_en_attente: number;
    credits_en_instruction: number;
    campaign_validation_pending?: number;
    escalades_ouvertes?: number;
  };
}) {
  const pathname = usePathname();
  const router = useRouter();

  async function onLogout() {
    try { await adminApi.logout(); } catch { /* swallow */ }
    router.replace("/login");
  }

  return (
    <aside className="flex w-64 shrink-0 flex-col border-r border-line-200 bg-paper">
      {/* Header */}
      <div className="border-b border-line-200 px-5 py-4">
        <p className="font-display text-[0.7rem] font-semibold uppercase tracking-[0.18em] text-terra-600">
          Gathe Finance
        </p>
        <p className="mt-1 font-editorial text-lg font-medium text-ink-900">Administration</p>
      </div>

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto px-3 py-4">
        <ul className="space-y-0.5">
          {NAV.map(({ href, label, icon: Icon, queueKey }) => {
            // Match exact ou descendance par segment — évite que `/members`
            // s'active sur `/membership-requests` (cas où un href est préfixe
            // textuel d'un autre).
            const active = pathname === href || pathname.startsWith(href + "/");
            const count = queueKey && queues ? queues[queueKey] : undefined;
            return (
              <li key={href}>
                <Link
                  href={href}
                  className={[
                    "group flex items-center gap-2.5 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                    active
                      ? "bg-blue-700 text-white"
                      : "text-ink-700 hover:bg-cream hover:text-blue-700",
                  ].join(" ")}
                >
                  <Icon className="size-4 shrink-0" aria-hidden="true" />
                  <span className="flex-1">{label}</span>
                  {count && count > 0 ? (
                    <span
                      className={[
                        "rounded-full px-1.5 py-0.5 font-mono text-xs",
                        active
                          ? "bg-white/20 text-white"
                          : "bg-terra-500/15 text-terra-700",
                      ].join(" ")}
                    >
                      {count}
                    </span>
                  ) : null}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>

      {/* User */}
      <div className="border-t border-line-200 p-3">
        {identity ? (
          <div className="rounded-md bg-cream px-3 py-2.5">
            <p className="font-medium text-sm text-ink-900 truncate">{identity.email}</p>
            <p className="mt-0.5 text-xs text-ink-600">
              {identity.is_superuser
                ? "Superuser"
                : identity.groups.length
                  ? identity.groups.join(", ")
                  : "Staff"}
            </p>
            <button
              type="button"
              onClick={onLogout}
              className="mt-2 inline-flex items-center gap-1.5 text-xs font-medium text-terra-700 hover:text-terra-800 transition-colors"
            >
              <LogOut className="size-3.5" aria-hidden="true" />
              Se déconnecter
            </button>
          </div>
        ) : null}
      </div>
    </aside>
  );
}
