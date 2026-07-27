"use client";

import { useEffect, useState } from "react";

import { DataTable, type DataColumn } from "@/components/data-table";
import { adminApi, type ApiError, type AvalisteConsentRow } from "@/lib/api";
import { fullName } from "@/lib/name";
import { StatusPill } from "@/components/status-pill";


function fmtMoney(v: string | number) {
  const n = typeof v === "string" ? Number(v) : v;
  if (!Number.isFinite(n)) return String(v);
  return n.toLocaleString("fr-FR");
}

function fmtDate(iso: string) {
  try {
    return new Date(iso).toLocaleDateString("fr-FR", {
      day: "2-digit",
      month: "short",
      year: "2-digit",
    });
  } catch {
    return iso;
  }
}

type Filter = "all" | "attente_frais" | "pending" | "accepted" | "refused";


/**
 * Onglet « Avalistes / cautions » — supervision de tous les mandats d'avaliste.
 *
 * Lecture seule côté admin : la décision (accepter / refuser) appartient à
 * l'avaliste depuis son espace membre (Q13, non-rétractable). Ici on visualise
 * qui garantit qui, la caution gelée et l'état.
 */
export default function AvalistePage() {
  const [filter, setFilter] = useState<Filter>("all");
  const [rows, setRows] = useState<AvalisteConsentRow[]>([]);
  const [counts, setCounts] = useState<Record<string, number>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actingId, setActingId] = useState<number | null>(null);
  const [notice, setNotice] = useState<{ tone: "ok" | "err"; text: string } | null>(
    null,
  );

  /**
   * Émet le mandat d'un avaliste désigné mais jamais sollicité. Le motif
   * d'échec (avaliste introuvable, couverture insuffisante…) est affiché :
   * c'est exactement l'information qui manquait quand la sollicitation
   * échouait en silence.
   */
  async function solliciter(row: AvalisteConsentRow) {
    setActingId(row.id);
    setNotice(null);
    try {
      await adminApi.avaliste.requestConsent(row.loan_request.id);
      setNotice({
        tone: "ok",
        text: `Mandat émis — ${fullName(row.demandeur.prenom, row.demandeur.nom)}. L'avaliste peut répondre depuis son espace.`,
      });
      setFilter((f) => f);
      const res = await adminApi.avaliste.list({});
      setRows(res.results);
      setCounts(res.counts ?? {});
    } catch (e) {
      setNotice({
        tone: "err",
        text: (e as ApiError).detail ?? "Sollicitation impossible.",
      });
    } finally {
      setActingId(null);
    }
  }

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    adminApi.avaliste
      .list({ statut: filter === "all" ? undefined : filter })
      .then((res) => {
        if (cancelled) return;
        setRows(res.results);
        setCounts(res.counts ?? {});
        setError(null);
      })
      .catch((e) => {
        if (!cancelled) setError((e as ApiError).detail ?? "Chargement impossible.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [filter]);

  const columns: DataColumn<AvalisteConsentRow>[] = [
    {
      key: "demandeur",
      label: "Demandeur",
      text: (r) => `${fullName(r.demandeur.prenom, r.demandeur.nom)} ${r.demandeur.numero_membre}`,
      render: (r) => (
        <div>
          <p className="font-medium text-ink-900">
            {fullName(r.demandeur.prenom, r.demandeur.nom)}
          </p>
          <p className="font-mono text-xs text-ink-500">{r.demandeur.numero_membre}</p>
        </div>
      ),
    },
    {
      key: "avaliste",
      label: "Avaliste (garant)",
      text: (r) => `${fullName(r.avaliste.prenom, r.avaliste.nom)} ${r.avaliste.numero_membre}`,
      render: (r) => (
        <div>
          <p className="font-medium text-ink-900">
            {fullName(r.avaliste.prenom, r.avaliste.nom) || "—"}
          </p>
          <p className="font-mono text-xs text-ink-500">{r.avaliste.numero_membre}</p>
        </div>
      ),
    },
    {
      key: "montant_demande",
      label: "Montant crédit",
      numeric: true,
      align: "right",
      text: (r) => r.loan_request.montant_demande,
      render: (r) => (
        <span className="font-mono text-ink-900">
          {fmtMoney(r.loan_request.montant_demande)} XAF
        </span>
      ),
    },
    {
      key: "montant_gele",
      label: "Caution gelée",
      numeric: true,
      align: "right",
      text: (r) => r.montant_gele,
      render: (r) =>
        r.statut === "attente_frais" ? (
          <span className="text-ink-400">—</span>
        ) : (
          <span className="font-mono font-medium text-amber-700">
            {fmtMoney(r.montant_gele)} XAF
          </span>
        ),
    },
    {
      key: "ratio",
      label: "Couverture",
      align: "right",
      text: (r) => r.couverture.ratio,
      render: (r) =>
        r.statut === "attente_frais" ? (
          <span className="text-ink-400">—</span>
        ) : (
          <span className="font-mono text-ink-700">×{r.couverture.ratio}</span>
        ),
    },
    {
      key: "pieces",
      label: "Pièces / motif",
      text: (r) => `${r.cni_avaliste ?? ""} ${r.refus_motif ?? ""}`,
      render: (r) => {
        const hasMotif = r.statut === "refused" && !!r.refus_motif;
        if (!r.cni_avaliste && !r.cni_avaliste_fichier && !hasMotif) {
          return <span className="text-ink-400">—</span>;
        }
        return (
          <div className="space-y-1 text-xs">
            {r.cni_avaliste ? (
              <p className="font-mono text-ink-700">CNI : {r.cni_avaliste}</p>
            ) : null}
            {r.cni_avaliste_fichier ? (
              <a
                href={r.cni_avaliste_fichier}
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-700 hover:underline"
              >
                Voir la CNI
              </a>
            ) : null}
            {hasMotif ? (
              <p className="text-red-700">Motif : {r.refus_motif}</p>
            ) : null}
          </div>
        );
      },
    },
    {
      key: "statut",
      label: "Statut",
      text: (r) => r.statut_display,
      render: (r) => <StatusPill statut={r.statut} label={r.statut_display} />,
    },
    {
      key: "date",
      label: "Créé le",
      text: (r) => r.created_at,
      render: (r) => <span className="text-ink-600">{fmtDate(r.created_at)}</span>,
    },
  ];

  return (
    <section className="space-y-6">
      <header>
        <h1 className="font-editorial text-3xl font-medium tracking-tight text-ink-900">
          Avalistes / cautions
        </h1>
        <p className="text-sm text-ink-500">
          Qui garantit qui, la caution gelée sur l&apos;épargne du garant et
          l&apos;état de chaque mandat. La décision appartient à
          l&apos;avaliste depuis son espace ; l&apos;acceptation est
          définitive.
        </p>
      </header>

      <FilterTabs value={filter} onChange={setFilter} counts={counts} />

      {notice ? (
        <p
          className={`rounded-md border px-4 py-3 text-sm ${
            notice.tone === "ok"
              ? "border-emerald-300 bg-emerald-50 text-emerald-800"
              : "border-red-300 bg-red-50 text-red-800"
          }`}
        >
          {notice.text}
        </p>
      ) : null}

      {error ? (
        <p className="rounded-md border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-800">
          {error}
        </p>
      ) : loading ? (
        <p className="text-ink-600">Chargement…</p>
      ) : (
        <DataTable
          columns={columns}
          rows={rows}
          rowKey={(r) => r.id}
          emptyLabel="Aucune demande avec avaliste pour ce filtre."
          leftMeta={
            <>
              <span className="font-mono font-medium text-ink-900">{rows.length}</span>
              <span>mandat{rows.length > 1 ? "s" : ""}</span>
            </>
          }
          actions={(r) =>
            r.statut === "attente_frais" ? (
              <button
                type="button"
                onClick={() => solliciter(r)}
                disabled={actingId === r.id}
                className="rounded-md border border-line-200 bg-paper px-3 py-1.5 text-xs font-medium text-ink-700 transition hover:border-blue-700 hover:text-blue-700 disabled:opacity-50"
                title="Émettre le mandat maintenant — l'avaliste pourra accepter ou refuser depuis son espace"
              >
                {actingId === r.id ? "Envoi…" : "Solliciter l'avaliste"}
              </button>
            ) : null
          }
          exportFilename="avalistes-cautions"
          exportTitle="Avalistes / cautions — GATHE Finance"
          exportSubtitle={`Filtre : ${filter}`}
        />
      )}
    </section>
  );
}


function FilterTabs({
  value,
  onChange,
  counts,
}: {
  value: Filter;
  onChange: (v: Filter) => void;
  counts: Record<string, number>;
}) {
  const tabs: Array<{ key: Filter; label: string; count?: number }> = [
    { key: "all", label: "Tous" },
    {
      key: "attente_frais",
      label: "Désignés",
      count: counts.attente_frais,
    },
    { key: "pending", label: "À répondre", count: counts.pending },
    { key: "accepted", label: "Acceptés", count: counts.accepted },
    { key: "refused", label: "Refusés", count: counts.refused },
  ];
  return (
    <div className="flex flex-wrap gap-2">
      {tabs.map((t) => (
        <button
          key={t.key}
          type="button"
          onClick={() => onChange(t.key)}
          className={`rounded-md px-3 py-1.5 text-sm font-medium transition ${
            value === t.key
              ? "bg-ink-900 text-paper"
              : "border border-line-200 bg-paper text-ink-700 hover:bg-cream"
          }`}
        >
          {t.label}
          {typeof t.count === "number" ? (
            <span className="ml-1.5 opacity-70">({t.count})</span>
          ) : null}
        </button>
      ))}
    </div>
  );
}
