"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { SkeletonList } from "@gathe/ui";
import { AlertTriangle, CalendarClock, CheckCircle2, Clock } from "lucide-react";

import { PageHeader } from "@/components/page-header";
import {
  adminApi,
  type AdminDeadline,
  type AdminDeadlinesResponse,
  type ApiError,
} from "@/lib/api";

const HORIZONS = [7, 30, 90] as const;

function fmtDate(iso: string | null): string {
  if (!iso) return "—";
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

/** Formule le délai en clair : « dépassé de 7 j » plutôt que « -7 ». */
function delai(d: AdminDeadline): string {
  if (d.jours_restants === null) return "pas de date";
  if (d.jours_restants < 0) return `dépassé de ${Math.abs(d.jours_restants)} j`;
  if (d.jours_restants === 0) return "aujourd'hui";
  return `dans ${d.jours_restants} j`;
}

const TONES: Record<AdminDeadline["gravite"], { card: string; pill: string; label: string }> = {
  urgent: {
    card: "border-terra-300 bg-terra-50/40",
    pill: "bg-terra-100 text-terra-700",
    label: "À traiter",
  },
  proche: {
    card: "border-amber-200 bg-amber-50/40",
    pill: "bg-amber-100 text-amber-800",
    label: "Bientôt",
  },
  info: {
    card: "border-line-200 bg-paper",
    pill: "bg-line-100 text-ink-600",
    label: "À suivre",
  },
};

/**
 * Onglet Notifications — les délais de fin de chaque processus au même endroit.
 *
 * Écran de LECTURE : il ne déclenche rien. Les actions (clôture mensuelle,
 * pénalités, suspensions) restent le travail des crons ; ici on rend seulement
 * visible ce qui arrive à terme, avec un lien vers l'écran où agir.
 */
export default function NotificationsPage() {
  const [data, setData] = useState<AdminDeadlinesResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [horizon, setHorizon] = useState<number>(30);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await adminApi.deadlines.list(horizon));
    } catch (e) {
      setError((e as ApiError).detail ?? "Chargement impossible.");
    } finally {
      setLoading(false);
    }
  }, [horizon]);

  useEffect(() => {
    void load();
  }, [load]);

  const cartes = data?.results ?? [];
  const urgentes = cartes.filter((c) => c.gravite === "urgent");
  const autres = cartes.filter((c) => c.gravite !== "urgent");

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Notifications"
        title="Échéances des processus"
        description="Ce qui arrive à terme : clôtures, crédits, campagnes, cycles de collecte, maturités et réinscriptions."
        actions={
          <div className="flex items-center gap-2">
            <span className="text-[0.65rem] font-semibold uppercase tracking-wider text-ink-500">
              Horizon
            </span>
            <div className="flex items-center gap-1 rounded-md border border-line-200 bg-paper p-1">
              {HORIZONS.map((h) => (
                <button
                  key={h}
                  type="button"
                  onClick={() => setHorizon(h)}
                  className={`rounded px-2.5 py-1 text-xs font-semibold transition-colors ${
                    horizon === h
                      ? "bg-blue-700 text-white"
                      : "text-ink-600 hover:bg-line-100"
                  }`}
                >
                  {h} j
                </button>
              ))}
            </div>
          </div>
        }
      />

      {error ? (
        <p className="rounded-md border border-terra-200 bg-terra-50/60 px-3 py-2 text-sm text-terra-700" role="alert">
          {error}
        </p>
      ) : null}

      {loading ? (
        <SkeletonList />
      ) : (
        <>
          {/* Bandeau de tête : ce qui brûle, en une ligne. */}
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <StatCard
              icon={AlertTriangle}
              label="Processus en dépassement"
              value={data?.summary.urgent ?? 0}
              tone={data?.summary.urgent ? "danger" : "default"}
            />
            <StatCard
              icon={Clock}
              label="Échéances proches"
              value={data?.summary.proche ?? 0}
              tone={data?.summary.proche ? "warning" : "default"}
            />
            <StatCard
              icon={CalendarClock}
              label="Éléments à traiter"
              value={data?.summary.a_traiter ?? 0}
              hint="Total des dossiers derrière les processus dépassés"
              tone={data?.summary.a_traiter ? "danger" : "default"}
            />
          </div>

          {urgentes.length === 0 ? (
            <p className="flex items-center gap-2 rounded-md border border-emerald/30 bg-emerald/5 px-3 py-2.5 text-sm text-emerald">
              <CheckCircle2 className="size-4" aria-hidden="true" />
              Aucun processus en dépassement. Rien ne réclame d&apos;action immédiate.
            </p>
          ) : null}

          <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
            {[...urgentes, ...autres].map((c) => (
              <DeadlineCard key={c.cle} deadline={c} />
            ))}
          </div>

          <p className="text-xs text-ink-500">
            Écran de consultation : ouvrir cette page ne déclenche aucun envoi ni
            aucune modification. Les clôtures, pénalités et suspensions restent
            exécutées par les tâches planifiées.
          </p>
        </>
      )}
    </div>
  );
}

function DeadlineCard({ deadline }: { deadline: AdminDeadline }) {
  const tone = TONES[deadline.gravite];
  const vide = deadline.volume === 0;

  return (
    <div className={`rounded-card border p-4 ${tone.card}`}>
      <div className="flex items-start justify-between gap-3">
        <h3 className="text-sm font-semibold text-ink-900">{deadline.titre}</h3>
        <span className={`pill shrink-0 ${tone.pill}`}>{tone.label}</span>
      </div>

      <p className="mt-1.5 text-xs leading-relaxed text-ink-600">{deadline.description}</p>

      <div className="mt-3 flex flex-wrap items-baseline gap-x-4 gap-y-1">
        <span className="text-2xl font-semibold tabular-nums text-ink-900">
          {deadline.volume}
        </span>
        <span className="text-xs text-ink-500">{deadline.unite}</span>
      </div>

      <div className="mt-3 flex items-center justify-between border-t border-line-200/70 pt-2.5 text-xs">
        <span className="text-ink-500">
          {fmtDate(deadline.date_echeance)}
          {deadline.date_echeance ? (
            <span className={deadline.en_retard && !vide ? "ml-1.5 font-semibold text-terra-700" : "ml-1.5 text-ink-500"}>
              · {delai(deadline)}
            </span>
          ) : null}
        </span>
        <Link href={deadline.lien} className="font-semibold text-blue-700 hover:underline">
          Ouvrir
        </Link>
      </div>
    </div>
  );
}

function StatCard({
  icon: Icon,
  label,
  value,
  hint,
  tone = "default",
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: number;
  hint?: string;
  tone?: "default" | "warning" | "danger";
}) {
  const colors = {
    default: "text-ink-500",
    warning: "text-amber-700",
    danger: "text-terra-700",
  }[tone];

  return (
    <div className="rounded-card border border-line-200 bg-paper p-4">
      <div className="flex items-center gap-2">
        <Icon className={`size-4 ${colors}`} aria-hidden="true" />
        <span className="text-[0.65rem] font-semibold uppercase tracking-wider text-ink-500">
          {label}
        </span>
      </div>
      <p className={`mt-1.5 text-2xl font-semibold tabular-nums ${colors}`}>{value}</p>
      {hint ? <p className="mt-0.5 text-xs text-ink-500">{hint}</p> : null}
    </div>
  );
}
