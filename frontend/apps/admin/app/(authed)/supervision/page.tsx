"use client";

import { useCallback, useEffect, useState } from "react";
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Database,
  ExternalLink,
  Loader2,
  Mail,
  RefreshCw,
  Search,
  Server,
  Timer,
} from "lucide-react";

import {
  adminApi,
  type ApiError,
  type SupervisionEmail,
  type SupervisionEmailsResponse,
  type SupervisionOverview,
} from "@/lib/api";
import { PageHeader } from "@/components/page-header";

const STATUT_FILTERS = [
  { key: "", label: "Tous" },
  { key: "envoye", label: "Envoyés" },
  { key: "echec", label: "Échecs" },
  { key: "en_attente", label: "En attente" },
] as const;

function fmtDate(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("fr-FR", {
      day: "2-digit",
      month: "short",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

function statutPill(statut: string): string {
  if (statut === "envoye") return "pill pill-success";
  if (statut === "echec") return "pill pill-danger";
  return "pill pill-warning";
}

/** Petite carte KPI (label + valeur + icône). */
function StatCard({
  icon: Icon,
  label,
  value,
  hint,
  tone = "default",
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: React.ReactNode;
  hint?: string;
  tone?: "default" | "success" | "danger" | "warning";
}) {
  const dot =
    tone === "success"
      ? "text-green-600"
      : tone === "danger"
        ? "text-error"
        : tone === "warning"
          ? "text-warning"
          : "text-ink-400";
  return (
    <div className="rounded-card border border-line-200 bg-paper p-5">
      <div className="flex items-center gap-2 text-ink-500">
        <Icon className={`size-4 ${dot}`} />
        <span className="text-[0.72rem] font-semibold uppercase tracking-[0.12em]">
          {label}
        </span>
      </div>
      <p className="mt-3 font-display text-2xl font-bold tracking-tight text-ink-900">
        {value}
      </p>
      {hint ? <p className="mt-1 text-xs text-ink-500">{hint}</p> : null}
    </div>
  );
}

export default function SupervisionPage() {
  const [ov, setOv] = useState<SupervisionOverview | null>(null);
  const [ovLoading, setOvLoading] = useState(true);
  const [ovError, setOvError] = useState<string | null>(null);

  const [emails, setEmails] = useState<SupervisionEmailsResponse | null>(null);
  const [emailsLoading, setEmailsLoading] = useState(true);
  const [statut, setStatut] = useState<string>("");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);

  const loadOverview = useCallback(async () => {
    setOvLoading(true);
    setOvError(null);
    try {
      setOv(await adminApi.supervision.overview());
    } catch (err) {
      setOvError((err as ApiError).detail ?? "Chargement impossible.");
    } finally {
      setOvLoading(false);
    }
  }, []);

  const loadEmails = useCallback(async () => {
    setEmailsLoading(true);
    try {
      setEmails(
        await adminApi.supervision.emails({ statut: statut || undefined, q: q || undefined, page }),
      );
    } catch {
      setEmails(null);
    } finally {
      setEmailsLoading(false);
    }
  }, [statut, q, page]);

  useEffect(() => {
    loadOverview();
  }, [loadOverview]);

  useEffect(() => {
    loadEmails();
  }, [loadEmails]);

  const health = ov?.health;
  const sched = ov?.scheduler;

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Ops"
        title="Supervision"
        description="État opérationnel en un coup d'œil : santé du service, planificateur des tâches, messages e-mail envoyés par le système, et accès rapide aux ressources sensibles."
        actions={
          <button
            type="button"
            onClick={() => {
              loadOverview();
              loadEmails();
            }}
            className="inline-flex items-center gap-2 rounded-full border border-line-200 bg-paper px-4 py-2 text-sm font-medium text-ink-700 transition hover:border-blue-300 hover:bg-blue-50"
          >
            <RefreshCw className="size-4" /> Rafraîchir
          </button>
        }
      />

      {ovError ? (
        <div className="rounded-card border border-error/30 bg-error-soft p-4 text-sm text-error">
          {ovError}
        </div>
      ) : null}

      {/* ===== Santé + planificateur + monitoring ===== */}
      <section>
        <h2 className="mb-3 font-display text-[0.72rem] font-semibold uppercase tracking-[0.14em] text-ink-500">
          Santé du système
        </h2>
        {ovLoading ? (
          <div className="flex items-center gap-2 text-ink-500">
            <Loader2 className="size-4 animate-spin" /> Chargement…
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard
              icon={Server}
              label="Backend"
              value={health?.backend ? "En ligne" : "Hors ligne"}
              tone={health?.backend ? "success" : "danger"}
            />
            <StatCard
              icon={Database}
              label="Base de données"
              value={health?.database ? "OK" : "Erreur"}
              tone={health?.database ? "success" : "danger"}
            />
            <StatCard
              icon={Timer}
              label="Planificateur"
              value={sched?.available ? `${sched?.schedules ?? 0} tâches` : "Indispo."}
              hint={
                sched?.available
                  ? `${sched?.success_24h ?? 0} ok · ${sched?.failed_24h ?? 0} échec(s) / 24 h`
                  : sched?.error
              }
              tone={sched?.available ? (sched?.failed_24h ? "warning" : "success") : "danger"}
            />
            {/* Monitoring conteneurs — Beszel (externe) */}
            <div className="rounded-card border border-line-200 bg-paper p-5">
              <div className="flex items-center gap-2 text-ink-500">
                <Activity className="size-4 text-blue-700" />
                <span className="text-[0.72rem] font-semibold uppercase tracking-[0.12em]">
                  Monitoring serveur
                </span>
              </div>
              {ov?.monitor_url ? (
                <a
                  href={ov.monitor_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="mt-3 inline-flex items-center gap-2 rounded-full bg-blue-700 px-4 py-2 text-sm font-medium text-white transition hover:bg-blue-800"
                >
                  Ouvrir Beszel <ExternalLink className="size-4" />
                </a>
              ) : (
                <p className="mt-3 text-sm text-ink-500">
                  Non configuré — définir <code className="font-mono text-xs">MONITOR_URL</code> côté serveur.
                </p>
              )}
            </div>
          </div>
        )}

        {/* Prochaines tâches planifiées */}
        {sched?.available && (sched.upcoming?.length ?? 0) > 0 ? (
          <div className="mt-4 rounded-card border border-line-200 bg-paper p-5">
            <p className="mb-3 text-[0.72rem] font-semibold uppercase tracking-[0.12em] text-ink-500">
              Prochaines tâches planifiées
            </p>
            <ul className="divide-y divide-line-50">
              {sched.upcoming!.map((s) => (
                <li key={s.name} className="flex items-center justify-between gap-4 py-2 text-sm">
                  <span className="font-mono text-ink-800">{s.name}</span>
                  <span className="font-mono text-xs text-ink-500">{s.cron}</span>
                  <span className="text-xs text-ink-500">{fmtDate(s.next_run)}</span>
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </section>

      {/* ===== Stats e-mails ===== */}
      <section>
        <h2 className="mb-3 font-display text-[0.72rem] font-semibold uppercase tracking-[0.14em] text-ink-500">
          Messages e-mail (système)
        </h2>
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          <StatCard icon={Mail} label="Total envoyés" value={ov?.emails.total ?? "—"} />
          <StatCard
            icon={CheckCircle2}
            label="Envoyés (7 j)"
            value={ov?.emails.sent_7d ?? "—"}
            tone="success"
          />
          <StatCard
            icon={AlertTriangle}
            label="Échecs (7 j)"
            value={ov?.emails.failed_7d ?? "—"}
            tone={ov?.emails.failed_7d ? "danger" : "default"}
          />
          <StatCard
            icon={Timer}
            label="En attente"
            value={ov?.emails.pending ?? "—"}
            tone={ov?.emails.pending ? "warning" : "default"}
          />
        </div>
      </section>

      {/* ===== Table EmailLog ===== */}
      <section className="rounded-panel border border-line-200 bg-paper">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line-100 p-4">
          <div className="flex flex-wrap gap-1">
            {STATUT_FILTERS.map((f) => (
              <button
                key={f.key}
                type="button"
                onClick={() => {
                  setStatut(f.key);
                  setPage(1);
                }}
                className={`rounded-full px-3 py-1.5 text-sm font-medium transition ${
                  statut === f.key
                    ? "bg-blue-700 text-white"
                    : "text-ink-600 hover:bg-line-100"
                }`}
              >
                {f.label}
              </button>
            ))}
          </div>
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-ink-400" />
            <input
              value={q}
              onChange={(e) => {
                setQ(e.target.value);
                setPage(1);
              }}
              placeholder="Rechercher un destinataire…"
              className="w-64 rounded-field border border-line-200 bg-paper py-2 pl-9 pr-3 text-sm text-ink-900 focus:border-blue-700 focus:outline-none"
            />
          </div>
        </div>

        {emailsLoading ? (
          <div className="flex items-center gap-2 p-6 text-ink-500">
            <Loader2 className="size-4 animate-spin" /> Chargement…
          </div>
        ) : !emails || emails.results.length === 0 ? (
          <p className="p-8 text-center text-sm text-ink-500">
            Aucun message pour ce filtre.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="table-admin">
              <thead>
                <tr>
                  <th>Destinataire</th>
                  <th>Objet</th>
                  <th>Modèle</th>
                  <th>Statut</th>
                  <th>Date</th>
                </tr>
              </thead>
              <tbody>
                {emails.results.map((r: SupervisionEmail) => (
                  <tr key={r.id}>
                    <td>
                      <span className="font-mono text-xs text-ink-800">{r.destinataire}</span>
                      {r.member ? (
                        <span className="block text-xs text-ink-500">{r.member}</span>
                      ) : null}
                    </td>
                    <td className="max-w-[22rem] truncate text-ink-800">{r.objet}</td>
                    <td>
                      <span className="font-mono text-xs text-ink-500">{r.template}</span>
                    </td>
                    <td>
                      <span className={statutPill(r.statut)}>{r.statut_display}</span>
                      {r.statut === "echec" && r.erreur ? (
                        <span className="mt-1 block max-w-[18rem] truncate text-xs text-error" title={r.erreur}>
                          {r.erreur}
                        </span>
                      ) : null}
                    </td>
                    <td className="whitespace-nowrap text-xs text-ink-500">
                      {fmtDate(r.created_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination */}
        {emails && emails.count > emails.page_size ? (
          <div className="flex items-center justify-between gap-4 border-t border-line-100 p-4 text-sm text-ink-600">
            <span>
              {emails.count} message(s) · page {emails.page}
            </span>
            <div className="flex gap-2">
              <button
                type="button"
                disabled={page <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                className="rounded-full border border-line-200 px-3 py-1.5 disabled:opacity-40"
              >
                Précédent
              </button>
              <button
                type="button"
                disabled={!emails.has_next}
                onClick={() => setPage((p) => p + 1)}
                className="rounded-full border border-line-200 px-3 py-1.5 disabled:opacity-40"
              >
                Suivant
              </button>
            </div>
          </div>
        ) : null}
      </section>

      {/* ===== Liens rapides ressources clés ===== */}
      {ov && ov.quick_links.length > 0 ? (
        <section>
          <h2 className="mb-3 font-display text-[0.72rem] font-semibold uppercase tracking-[0.14em] text-ink-500">
            Ressources clés
          </h2>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
            {ov.quick_links.map((l) => (
              <a
                key={l.href}
                href={l.href}
                className="rounded-card border border-line-200 bg-paper px-4 py-3 text-sm font-medium text-ink-700 transition hover:border-blue-300 hover:bg-blue-50"
              >
                {l.label}
              </a>
            ))}
          </div>
        </section>
      ) : null}
    </div>
  );
}
