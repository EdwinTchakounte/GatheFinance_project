"use client";

import { useEffect, useState } from "react";
import {
  ArrowUpRight,
  Wallet,
  Users,
  ClipboardCheck,
  AlertCircle,
  PiggyBank,
  HandCoins,
  Megaphone,
  ShieldAlert,
  Gavel,
  UserCheck,
} from "lucide-react";

import { adminApi, type DashboardKpis } from "@/lib/api";


function formatXAF(amount: string): string {
  const n = Number(amount);
  if (Number.isNaN(n)) return amount;
  return n.toLocaleString("fr-FR", { maximumFractionDigits: 0 }) + " XAF";
}

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleDateString("fr-FR", { day: "2-digit", month: "short" });
  } catch {
    return iso;
  }
}


export default function DashboardPage() {
  return (
    
      <DashboardContent />
    
  );
}

function DashboardContent() {
  const [kpis, setKpis] = useState<DashboardKpis | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    adminApi.dashboard().then(setKpis).finally(() => setLoading(false));
  }, []);

  if (loading || !kpis) {
    return (
      <div className="px-8 py-12 text-ink-600">Chargement des KPIs…</div>
    );
  }

  const generalCards: KpiCardProps[] = [
    {
      label: "Membres actifs",
      value: kpis.members.actif,
      hint: `${kpis.members.suspendu} suspendu(s) · ${kpis.members.temporaire} temporaire(s)`,
      icon: Users,
      tone: "emerald",
    },
    {
      label: "Adhésions à instruire",
      value: kpis.queues.adhesions_en_attente,
      hint: "à valider",
      icon: ClipboardCheck,
      tone: "terra",
      href: "/membership-requests",
    },
    {
      label: "Crédits en instruction",
      value: kpis.queues.credits_en_instruction,
      hint: "comité crédit",
      icon: AlertCircle,
      tone: "blue",
      href: "/loan-requests",
    },
    {
      label: "Encours crédit",
      value: formatXAF(kpis.finance.encours_credit),
      hint: `Épargne totale : ${formatXAF(kpis.finance.epargne_total)}`,
      icon: Wallet,
      tone: "blue",
      large: true,
    },
  ];

  const refonteCards: KpiCardProps[] = [
    {
      label: "Avalistes en attente",
      value: kpis.queues.avaliste_pending,
      hint: "réponse attendue (Q13 non-rétractable)",
      icon: UserCheck,
      tone: "terra",
    },
    {
      label: "Campagnes validations",
      value: kpis.queues.campaign_validation_pending,
      hint: `${kpis.campaigns.actives} campagne(s) active(s)`,
      icon: Megaphone,
      tone: "terra",
    },
    {
      label: "Prêteurs actifs",
      value: kpis.lenders.consents_actifs,
      hint: `Dispo : ${formatXAF(kpis.lenders.tranches_disponible)} · Engagé : ${formatXAF(kpis.lenders.tranches_engagee)}`,
      icon: HandCoins,
      tone: "blue",
      large: true,
    },
    {
      label: "Funding en cours",
      value: kpis.lenders.funding_in_progress,
      hint: "PENDING + REALLOCATING",
      icon: HandCoins,
      tone: "blue",
    },
  ];

  const epargneCards: KpiCardProps[] = [
    {
      label: "Épargne collecte",
      value: formatXAF(kpis.finance.epargne_collecte),
      hint: "comptes journaliers",
      icon: PiggyBank,
      tone: "emerald",
      large: true,
    },
    {
      label: "Épargne classique",
      value: formatXAF(kpis.finance.epargne_classique),
      hint: "contrats 12 mois",
      icon: PiggyBank,
      tone: "emerald",
      large: true,
    },
    {
      label: "Cycle anniversaire",
      value: kpis.epargne_classique_cycle.en_attente_paiement,
      hint: `${kpis.epargne_classique_cycle.notifie} notifié(s) · ${kpis.epargne_classique_cycle.urgence} urgence(s)`,
      icon: AlertCircle,
      tone: "terra",
      href: "/renewals",
    },
    {
      label: "BRC validés",
      value: kpis.members.brc_validated,
      hint: "voie crédit directe débloquée",
      icon: ShieldAlert,
      tone: "emerald",
      href: "/brc",
    },
  ];

  const risqueCards: KpiCardProps[] = [
    {
      label: "Crédits en retard",
      value: kpis.contentieux.loans_en_retard,
      hint: "rappels graduellement envoyés",
      icon: AlertCircle,
      tone: "terra",
    },
    {
      label: "Crédits contentieux",
      value: kpis.contentieux.loans_contentieux,
      hint: "saisie épargne déclenchée",
      icon: ShieldAlert,
      tone: "terra",
    },
    {
      label: "Escalades judiciaires",
      value: kpis.contentieux.escalades_ouvertes,
      hint: "EN_INSTANCE + DECISION_RENDUE",
      icon: Gavel,
      tone: "terra",
      large: true,
    },
  ];

  return (
    <div className="px-8 py-8 lg:px-12 lg:py-10">
      <header className="mb-8">
        <p className="font-display text-[0.7rem] font-semibold uppercase tracking-[0.18em] text-terra-600">
          Vue d'ensemble
        </p>
        <h1 className="mt-2 font-editorial text-3xl font-medium text-ink-900">
          Tableau de bord
        </h1>
        <p className="mt-1 text-sm text-ink-600">
          État opérationnel de la coopérative en temps réel.
        </p>
      </header>

      {/* Général */}
      <section className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {generalCards.map((c) => (
          <KpiCard key={c.label} {...c} />
        ))}
      </section>

      {/* Refonte 2026 — éligibilité + prêteurs */}
      <section className="mt-10">
        <h2 className="mb-3 font-display text-xs font-semibold uppercase tracking-wider text-ink-500">
          Éligibilité 3 voies &amp; prêteurs (refonte 2026)
        </h2>
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          {refonteCards.map((c) => (
            <KpiCard key={c.label} {...c} />
          ))}
        </div>
      </section>

      {/* Épargne — collecte + classique */}
      <section className="mt-10">
        <h2 className="mb-3 font-display text-xs font-semibold uppercase tracking-wider text-ink-500">
          Épargne &amp; cycles
        </h2>
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          {epargneCards.map((c) => (
            <KpiCard key={c.label} {...c} />
          ))}
        </div>
      </section>

      {/* Risque — retards + contentieux + judiciaire */}
      <section className="mt-10">
        <h2 className="mb-3 font-display text-xs font-semibold uppercase tracking-wider text-ink-500">
          Risque &amp; contentieux
        </h2>
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {risqueCards.map((c) => (
            <KpiCard key={c.label} {...c} />
          ))}
        </div>
      </section>

      {/* Recent payments */}
      <section className="mt-10">
        <h2 className="mb-4 font-editorial text-xl font-medium text-ink-900">
          Derniers paiements validés
        </h2>
        {kpis.recent_payments.length === 0 ? (
          <p className="rounded-md border border-dashed border-line-200 bg-paper/70 p-8 text-center text-sm text-ink-600">
            Aucun paiement validé pour le moment.
          </p>
        ) : (
          <div className="overflow-hidden rounded-md border border-line-200 bg-paper">
            <table className="table-admin">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Type</th>
                  <th className="text-right">Montant</th>
                  <th>Statut</th>
                  <th>Validé le</th>
                </tr>
              </thead>
              <tbody>
                {kpis.recent_payments.map((p) => (
                  <tr key={p.id}>
                    <td className="font-mono text-xs text-ink-600">#{p.id}</td>
                    <td>{p.type_display}</td>
                    <td className="text-right font-mono">{formatXAF(p.montant)}</td>
                    <td><span className="pill pill-success">{p.statut}</span></td>
                    <td className="text-sm text-ink-600">{formatDate(p.date_validation)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}


type KpiCardProps = {
  label: string;
  value: string | number;
  hint?: string;
  icon: React.ComponentType<{ className?: string }>;
  tone: "emerald" | "blue" | "terra";
  href?: string;
  large?: boolean;
};


function KpiCard({
  label, value, hint, icon: Icon, tone, href, large,
}: KpiCardProps) {
  const accent = {
    emerald: { bg: "bg-emerald/10", text: "text-emerald" },
    blue: { bg: "bg-blue-700/10", text: "text-blue-700" },
    terra: { bg: "bg-terra-500/15", text: "text-terra-700" },
  }[tone];

  const Inner = (
    <>
      <div className="flex items-center justify-between">
        <p className="font-display text-[0.7rem] font-semibold uppercase tracking-[0.14em] text-ink-600">
          {label}
        </p>
        <div className={`inline-flex size-8 items-center justify-center rounded-md ${accent.bg} ${accent.text}`}>
          <Icon className="size-4" aria-hidden="true" />
        </div>
      </div>
      <p className={`mt-3 font-editorial font-medium leading-none text-ink-900 ${large ? "text-2xl" : "text-4xl"}`}>
        {value}
      </p>
      {hint ? <p className="mt-2 text-xs text-ink-600">{hint}</p> : null}
      {href ? (
        <p className="mt-3 inline-flex items-center gap-1 text-xs font-medium text-blue-700">
          Voir <ArrowUpRight className="size-3" aria-hidden="true" />
        </p>
      ) : null}
    </>
  );

  const className = "block rounded-lg border border-line-200 bg-paper p-5 transition-shadow hover:shadow-[var(--shadow-sm)]";
  return href ? <a href={href} className={className}>{Inner}</a> : <div className={className}>{Inner}</div>;
}
