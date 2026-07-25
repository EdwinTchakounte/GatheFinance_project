"use client";

import { useEffect, useState } from "react";
import { Skeleton, SkeletonCard } from "@gathe/ui";
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
  FileDown,
  Search,
} from "lucide-react";

import { adminApi, type AdminInstallmentRow, type DashboardKpis } from "@/lib/api";
import { LoanDetailModal } from "@/components/loan-detail-modal";
import { StatusPill } from "@/components/status-pill";


function formatXAF(amount: string): string {
  const n = Number(amount);
  if (Number.isNaN(n)) return amount;
  return n.toLocaleString("fr-FR", { maximumFractionDigits: 0 }) + " XAF";
}

function formatDate(iso: string | null): string {
  if (!iso) return "";
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
      <div>
        <Skeleton className="mb-6 h-8 w-52" />
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <SkeletonCard key={i} className="h-28" />
          ))}
        </div>
      </div>
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
      hint: "réponse de l'avaliste attendue",
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
      // A3 . Total = libre (cash sur ClassicSavingsAccount) + placement
      // (LenderTranche actives). Le breakdown est dans le hint.
      label: "Épargne classique",
      value: formatXAF(kpis.finance.epargne_classique),
      hint: `Libre ${formatXAF(kpis.finance.epargne_classique_libre)} · Placement ${formatXAF(kpis.finance.epargne_placement)}`,
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
    <div className="space-y-6">
      <header className="mb-8 flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="font-display text-[0.7rem] font-semibold uppercase tracking-[0.18em] text-terra-600">
            Vue d'ensemble
          </p>
          <h1 className="mt-2 font-editorial text-3xl font-medium text-ink-900">
            Tableau de bord
          </h1>
          <p className="mt-1 text-sm text-ink-600">
            État opérationnel de la coopérative en temps réel.
          </p>
        </div>
        <a
          href={adminApi.reports.coopUrl()}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-2 rounded-md border border-line-300 bg-white px-3.5 py-2 text-sm font-medium text-ink-800 transition-colors hover:border-blue-400 hover:text-blue-700"
        >
          <FileDown className="size-4" aria-hidden="true" />
          Rapport PDF
        </a>
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
          Éligibilité 3 voies &amp; prêteurs
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

      {/* A2 . Suivi paiement . echeances a venir + en retard */}
      <UpcomingRepayments />

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
          <div className="overflow-x-auto rounded-xl border border-line-100 bg-paper shadow-xs">
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


// ---------------------------------------------------------------------------
// A2 . Widget "Suivi paiement" . echeances a payer + en retard (top 15).
//   Source : GET /loans/admin/installments/ (non-payees, tri date_echeance ASC).
// ---------------------------------------------------------------------------
function UpcomingRepayments() {
  const [rows, setRows] = useState<AdminInstallmentRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<"" | "en_retard" | "a_venir,partielle">("");
  // Bouton « check » : ouvre l'état complet de l'abonné sur ce crédit.
  const [checkLoanId, setCheckLoanId] = useState<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    adminApi.loans
      .listInstallments({ statut: filter || undefined, limit: 15 })
      .then((res) => {
        if (!cancelled) setRows(res.results);
      })
      .catch(() => {
        if (!cancelled) setRows([]);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [filter]);

  return (
    <section className="mt-10">
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="font-editorial text-xl font-medium text-ink-900">
            Remboursements à venir
          </h2>
          <p className="text-xs text-ink-500">
            Échéances de crédits actifs ou en retard (top 15, tri date)
          </p>
        </div>
        <div className="flex items-center gap-1 rounded-md border border-line-200 bg-paper p-1">
          {[
            { v: "", l: "Tous" },
            { v: "a_venir,partielle", l: "À venir" },
            { v: "en_retard", l: "En retard" },
          ].map((opt) => (
            <button
              key={opt.v || "all"}
              type="button"
              onClick={() => setFilter(opt.v as typeof filter)}
              className={
                "rounded px-2.5 py-1 text-xs font-medium transition-colors " +
                (filter === opt.v
                  ? "bg-blue-700 text-white"
                  : "text-ink-700 hover:text-blue-700")
              }
            >
              {opt.l}
            </button>
          ))}
        </div>
      </div>
      {loading ? (
        <p className="rounded-md border border-dashed border-line-200 bg-paper/70 p-6 text-center text-sm text-ink-600">
          Chargement…
        </p>
      ) : rows.length === 0 ? (
        <p className="rounded-md border border-dashed border-line-200 bg-paper/70 p-6 text-center text-sm text-ink-600">
          Aucune échéance non payée.
        </p>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-line-100 bg-paper shadow-xs">
          <table className="table-admin">
            <thead>
              <tr>
                <th>Échéance</th>
                <th>Membre</th>
                <th>Dossier</th>
                <th className="text-right">Montant restant</th>
                <th>Statut</th>
                <th className="text-right">État</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id}>
                  <td className="whitespace-nowrap text-sm text-ink-700">
                    {new Date(r.date_echeance).toLocaleDateString("fr-FR", {
                      day: "2-digit",
                      month: "short",
                      year: "2-digit",
                    })}
                    <p className="text-[10px] text-ink-500">
                      #{r.numero_echeance}
                    </p>
                  </td>
                  <td>
                    <p className="font-medium text-ink-900">
                      {r.member.prenom} {r.member.nom}
                    </p>
                    <p className="font-mono text-xs text-ink-500">
                      {r.member.numero_membre}
                    </p>
                  </td>
                  <td>
                    <a
                      href="/loans"
                      className="font-mono text-sm text-blue-700 underline-offset-2 hover:underline"
                    >
                      {r.loan.numero_dossier}
                    </a>
                  </td>
                  <td className="text-right font-mono text-sm font-medium text-ink-900">
                    {Number(r.montant_restant).toLocaleString("fr-FR")}
                    <p className="text-[10px] uppercase tracking-wide text-ink-400">
                      XAF
                    </p>
                  </td>
                  <td>
                    <StatusPill statut={r.statut} label={r.statut_display} />
                  </td>
                  <td className="text-right">
                    <button
                      type="button"
                      onClick={() => setCheckLoanId(r.loan.id)}
                      title="Voir l'état complet de l'abonné sur ce crédit"
                      className="inline-flex items-center gap-1 rounded-md border border-line-200 px-2 py-1 text-xs font-medium text-blue-700 transition-colors hover:border-blue-300 hover:bg-blue-50"
                    >
                      <Search className="h-3.5 w-3.5" />
                      Check
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <LoanDetailModal
        loanId={checkLoanId}
        onClose={() => setCheckLoanId(null)}
      />
    </section>
  );
}
