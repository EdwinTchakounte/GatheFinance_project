"use client";

import { useEffect, useMemo, useState, type ReactNode } from "react";
import { SkeletonList } from "@gathe/ui";
import { Mail, Phone, Search } from "lucide-react";

import { ColumnsMenu } from "@/components/columns-menu";
import { ExportMenu } from "@/components/export-menu";
import { Modal } from "@/components/modal";
import { Pagination } from "@/components/pagination";
import type { ExportColumn } from "@/lib/export";
import { adminApi, type ApiError, type Member } from "@/lib/api";


type StatutFilter = "" | "actif" | "suspendu" | "radie";


function fmtXAF(v?: string): string {
  const n = Number(v ?? 0);
  return Number.isFinite(n) ? n.toLocaleString("fr-FR") : "0";
}

function fmtDate(iso: string): string {
  return new Date(iso).toLocaleDateString("fr-FR", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}


// ── Définition des colonnes ────────────────────────────────────────────────
// `text` : valeur brute pour filtre + export. `num` : colonne numérique
// (filtre = seuil minimum ≥). `locked` : toujours visible.
type Col = {
  key: string;
  label: string;
  locked?: boolean;
  defaultVisible: boolean;
  numeric?: boolean;
  align?: "right";
  text: (m: Member) => string;
  render: (m: Member) => ReactNode;
};

const COLUMNS: Col[] = [
  {
    key: "numero",
    label: "N° membre",
    locked: true,
    defaultVisible: true,
    text: (m) => m.numero_membre,
    render: (m) => (
      <span className="font-mono text-sm font-medium text-ink-900">
        {m.numero_membre}
      </span>
    ),
  },
  {
    key: "membre",
    label: "Membre",
    locked: true,
    defaultVisible: true,
    text: (m) => `${m.prenom} ${m.nom}`,
    render: (m) => (
      <span className="font-medium text-ink-900">
        {m.prenom} {m.nom}
      </span>
    ),
  },
  {
    key: "contact",
    label: "Contact",
    defaultVisible: false,
    text: (m) => `${m.email ?? ""} ${m.phone ?? ""}`.trim(),
    render: (m) => (
      <div className="space-y-1">
        {m.email ? (
          <p className="flex items-center gap-1.5 text-sm text-ink-700">
            <Mail className="size-3.5 text-ink-400" aria-hidden="true" />
            {m.email}
          </p>
        ) : null}
        {m.phone ? (
          <p className="flex items-center gap-1.5 text-xs text-ink-600">
            <Phone className="size-3 text-ink-400" aria-hidden="true" />
            {m.phone}
          </p>
        ) : null}
      </div>
    ),
  },
  {
    key: "statut",
    label: "Statut",
    defaultVisible: true,
    text: (m) => m.statut_display,
    render: (m) => (
      <div className="flex flex-wrap items-center gap-1">
        <span
          className={
            "pill " +
            (m.statut === "actif"
              ? "pill-success"
              : m.statut === "suspendu"
                ? "pill-warning"
                : "pill-muted")
          }
        >
          {m.statut_display}
        </span>
        {m.is_brc_member ? <span className="pill pill-success">BRC</span> : null}
        {m.is_senior ? <span className="pill pill-muted">Ancien</span> : null}
      </div>
    ),
  },
  {
    key: "collecte",
    label: "Épargne collecte",
    defaultVisible: true,
    numeric: true,
    align: "right",
    text: (m) => fmtXAF(m.epargne_collecte),
    render: (m) => <span className="tabular-nums">{fmtXAF(m.epargne_collecte)}</span>,
  },
  {
    key: "libre",
    label: "Épargne libre",
    defaultVisible: true,
    numeric: true,
    align: "right",
    text: (m) => fmtXAF(m.epargne_classique_libre),
    render: (m) => (
      <span className="tabular-nums">{fmtXAF(m.epargne_classique_libre)}</span>
    ),
  },
  {
    key: "placement",
    label: "Placement",
    defaultVisible: true,
    numeric: true,
    align: "right",
    text: (m) => fmtXAF(m.epargne_placement),
    render: (m) => <span className="tabular-nums">{fmtXAF(m.epargne_placement)}</span>,
  },
  {
    key: "epargne_total",
    label: "Épargne totale",
    defaultVisible: true,
    numeric: true,
    align: "right",
    text: (m) => fmtXAF(m.epargne_total),
    render: (m) => (
      <span className="font-semibold tabular-nums text-ink-900">
        {fmtXAF(m.epargne_total)}
      </span>
    ),
  },
  {
    key: "credit",
    label: "Crédit en cours",
    defaultVisible: true,
    numeric: true,
    align: "right",
    text: (m) => fmtXAF(m.credit_encours),
    render: (m) => {
      const v = Number(m.credit_encours ?? 0);
      return (
        <span
          className={
            "tabular-nums " + (v > 0 ? "font-medium text-terra-700" : "text-ink-500")
          }
        >
          {fmtXAF(m.credit_encours)}
        </span>
      );
    },
  },
  {
    key: "adhesion",
    label: "Adhésion",
    defaultVisible: false,
    text: (m) => m.date_adhesion,
    render: (m) => (
      <span className="whitespace-nowrap text-sm text-ink-600">
        {fmtDate(m.date_adhesion)}
        {typeof m.seniority_months === "number" ? (
          <span className="ml-1 text-xs text-ink-400">({m.seniority_months} m.)</span>
        ) : null}
      </span>
    ),
  },
];


export default function MembersPage() {
  return <Inner />;
}


// ── Carte recap financier d'un membre ──────────────────────────────────────
// Consolide, en un coup d'œil : épargne (collecte + libre + placement),
// crédit en cours, et le solde net (épargne totale − crédit).
function MemberRecapModal({
  member,
  onClose,
}: {
  member: Member | null;
  onClose: () => void;
}) {
  if (!member) return null;
  const collecte = Number(member.epargne_collecte ?? 0);
  const libre = Number(member.epargne_classique_libre ?? 0);
  const placement = Number(member.epargne_placement ?? 0);
  const epargneTotal = Number(member.epargne_total ?? 0);
  const credit = Number(member.credit_encours ?? 0);
  const net = epargneTotal - credit;

  return (
    <Modal
      open
      onClose={onClose}
      title={`${member.prenom} ${member.nom}`}
      description={`N° ${member.numero_membre} · ${member.statut_display}`}
    >
      <div className="space-y-4">
        {/* Épargne détaillée */}
        <div>
          <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-ink-500">
            Épargne
          </p>
          <div className="space-y-1.5 rounded-md border border-line-200 bg-paper-soft/40 px-4 py-3">
            <RecapLine label="Collecte (journalière)" value={collecte} />
            <RecapLine label="Classique libre" value={libre} />
            <RecapLine label="Placement" value={placement} />
            <div className="mt-1 border-t border-line-200 pt-1.5">
              <RecapLine label="Épargne totale" value={epargneTotal} strong />
            </div>
          </div>
        </div>

        {/* Crédit */}
        <div>
          <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-ink-500">
            Crédit
          </p>
          <div className="rounded-md border border-line-200 bg-paper-soft/40 px-4 py-3">
            <RecapLine
              label="Crédit en cours"
              value={credit}
              tone={credit > 0 ? "terra" : undefined}
            />
          </div>
        </div>

        {/* Solde net */}
        <div
          className={
            "flex items-center justify-between rounded-md px-4 py-3 " +
            (net >= 0 ? "bg-emerald/10" : "bg-terra-50")
          }
        >
          <div>
            <p className="text-sm font-semibold text-ink-900">Solde net</p>
            <p className="text-xs text-ink-500">Épargne totale − crédit en cours</p>
          </div>
          <span
            className={
              "text-lg font-bold tabular-nums " +
              (net >= 0 ? "text-emerald" : "text-terra-700")
            }
          >
            {net.toLocaleString("fr-FR")} FCFA
          </span>
        </div>

        {credit > 0 ? (
          <p className="text-xs text-ink-500">
            Note : une partie de l'épargne classique peut être gelée en garantie
            tant qu'un crédit est actif (bloquée au retrait).
          </p>
        ) : null}
      </div>
    </Modal>
  );
}


function RecapLine({
  label,
  value,
  strong,
  tone,
}: {
  label: string;
  value: number;
  strong?: boolean;
  tone?: "terra";
}) {
  return (
    <div className="flex items-center justify-between">
      <span className={"text-sm " + (strong ? "font-semibold text-ink-900" : "text-ink-700")}>
        {label}
      </span>
      <span
        className={
          "tabular-nums " +
          (strong ? "font-semibold text-ink-900" : "text-ink-800") +
          (tone === "terra" ? " text-terra-700" : "")
        }
      >
        {value.toLocaleString("fr-FR")} FCFA
      </span>
    </div>
  );
}


function Inner() {
  const [statut, setStatut] = useState<StatutFilter>("");
  const [q, setQ] = useState("");
  const [items, setItems] = useState<Member[]>([]);
  const [count, setCount] = useState(0);
  const [limit, setLimit] = useState(25);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<Member | null>(null);

  // Colonnes visibles + filtres par colonne (appliqués à la page courante).
  const [visible, setVisible] = useState<Set<string>>(
    () => new Set(COLUMNS.filter((c) => c.defaultVisible).map((c) => c.key)),
  );
  const [colFilters, setColFilters] = useState<Record<string, string>>({});

  async function reload() {
    setLoading(true);
    setError(null);
    try {
      const res = await adminApi.members.list({
        statut: statut || undefined,
        q: q.trim() || undefined,
        limit,
        offset,
      });
      setItems(res.results);
      setCount(res.count);
    } catch (err) {
      const apiErr = err as ApiError;
      setError(apiErr.detail ?? "Chargement impossible.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [statut, limit, offset]);

  const shownCols = COLUMNS.filter((c) => visible.has(c.key));

  // Filtre par colonne : texte = "contient" (insensible à la casse) ;
  // numérique = seuil minimum (≥).
  const filtered = useMemo(() => {
    const active = Object.entries(colFilters).filter(([, v]) => v.trim() !== "");
    if (active.length === 0) return items;
    return items.filter((m) =>
      active.every(([key, raw]) => {
        const col = COLUMNS.find((c) => c.key === key);
        if (!col) return true;
        if (col.numeric) {
          const min = Number(raw.replace(/\s/g, "").replace(",", "."));
          if (!Number.isFinite(min)) return true;
          return Number(col.text(m).replace(/\s/g, "")) >= min;
        }
        return col.text(m).toLowerCase().includes(raw.trim().toLowerCase());
      }),
    );
  }, [items, colFilters]);

  const exportColumns: ExportColumn<Member>[] = shownCols.map((c) => ({
    key: c.key,
    label: c.label,
    value: (r) => c.text(r),
  }));

  return (
    <div className="px-8 py-8 lg:px-12 lg:py-10">
      <header className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="font-display text-[0.7rem] font-semibold uppercase tracking-[0.18em] text-terra-600">
            Membres
          </p>
          <h1 className="mt-2 font-editorial text-3xl font-medium text-ink-900">
            Annuaire des membres
          </h1>
          <p className="mt-1 text-sm text-ink-600">
            Recap financier par membre — épargne (collecte, libre, placement) et
            crédit en cours. Filtres par colonne + export.
          </p>
        </div>

        <div className="flex items-center gap-3 text-sm text-ink-600">
          <span className="font-mono font-medium text-ink-900">{count}</span>
          <span>membre{count > 1 ? "s" : ""}</span>
          <ColumnsMenu
            columns={COLUMNS.map((c) => ({ key: c.key, label: c.label }))}
            visible={visible}
            lockedKeys={COLUMNS.filter((c) => c.locked).map((c) => c.key)}
            onToggle={(key) =>
              setVisible((prev) => {
                const next = new Set(prev);
                if (next.has(key)) next.delete(key);
                else next.add(key);
                return next;
              })
            }
          />
          <ExportMenu
            filenamePrefix="membres"
            title="Annuaire des membres — GATHE Finance"
            subtitle={`Filtre : ${statut || "tous"}${q ? ` · recherche : ${q}` : ""}`}
            columns={exportColumns}
            rows={filtered}
          />
        </div>
      </header>

      <div className="mb-5 grid grid-cols-1 gap-3 md:grid-cols-[auto_1fr]">
        <div className="flex items-center gap-2">
          <span className="text-[0.65rem] font-semibold uppercase tracking-wider text-ink-500">
            Statut
          </span>
          <div className="flex items-center gap-1 rounded-md border border-line-200 bg-paper p-1">
            {[
              { v: "", l: "Tous" },
              { v: "actif", l: "Actifs" },
              { v: "suspendu", l: "Suspendus" },
              { v: "radie", l: "Radiés" },
            ].map((opt) => (
              <button
                key={opt.v || "all"}
                type="button"
                onClick={() => {
                  setStatut(opt.v as StatutFilter);
                  setOffset(0);
                }}
                className={[
                  "rounded px-2.5 py-1 text-xs font-medium transition-colors",
                  statut === opt.v
                    ? "bg-blue-700 text-white"
                    : "text-ink-700 hover:text-blue-700",
                ].join(" ")}
              >
                {opt.l}
              </button>
            ))}
          </div>
        </div>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            setOffset(0);
            reload();
          }}
          className="flex items-center gap-2"
        >
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-ink-400" />
            <input
              type="search"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Recherche (n° membre, nom, prénom, téléphone, email)"
              className="w-full rounded-md border border-line-200 bg-paper py-2 pl-9 pr-3 text-sm placeholder:text-ink-400 focus:border-blue-700 focus:outline-none focus:ring-1 focus:ring-blue-700"
            />
          </div>
          <button
            type="submit"
            className="rounded-md border border-line-200 bg-paper px-3 py-2 text-xs font-medium text-ink-700 hover:border-blue-700 hover:text-blue-700"
          >
            Rechercher
          </button>
        </form>
      </div>

      {error ? (
        <div className="mb-5 rounded-md border border-terra-400/40 bg-terra-50/60 px-4 py-2.5 text-sm text-terra-700">
          {error}
        </div>
      ) : null}

      {loading ? (
        <SkeletonList count={6} cardClassName="h-14" />
      ) : items.length === 0 ? (
        <p className="rounded-md border border-dashed border-line-200 bg-paper/70 p-12 text-center text-sm text-ink-600">
          Aucun membre ne correspond à ces filtres.
        </p>
      ) : (
        <div className="overflow-x-auto rounded-md border border-line-200 bg-paper">
          <table className="table-admin min-w-full">
            <thead>
              <tr>
                {shownCols.map((c) => (
                  <th key={c.key} className={c.align === "right" ? "text-right" : ""}>
                    {c.label}
                  </th>
                ))}
              </tr>
              {/* Ligne de filtres par colonne (applique à la page courante) */}
              <tr className="bg-paper-soft/60">
                {shownCols.map((c) => (
                  <th key={c.key} className="py-1.5">
                    <input
                      value={colFilters[c.key] ?? ""}
                      onChange={(e) =>
                        setColFilters((prev) => ({ ...prev, [c.key]: e.target.value }))
                      }
                      placeholder={c.numeric ? "≥ min" : "filtrer…"}
                      className={
                        "w-full rounded border border-line-200 bg-paper px-2 py-1 text-xs font-normal placeholder:text-ink-300 focus:border-blue-700 focus:outline-none " +
                        (c.align === "right" ? "text-right" : "")
                      }
                    />
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered.map((m) => (
                <tr
                  key={m.id}
                  onClick={() => setSelected(m)}
                  className="cursor-pointer transition-colors hover:bg-blue-50/50"
                  title="Voir le recap financier"
                >
                  {shownCols.map((c) => (
                    <td key={c.key} className={c.align === "right" ? "text-right" : ""}>
                      {c.render(m)}
                    </td>
                  ))}
                </tr>
              ))}
              {filtered.length === 0 ? (
                <tr>
                  <td
                    colSpan={shownCols.length}
                    className="py-6 text-center text-sm text-ink-500"
                  >
                    Aucune ligne ne correspond aux filtres de colonne (sur cette page).
                  </td>
                </tr>
              ) : null}
            </tbody>
            {filtered.length > 0 && shownCols.some((c) => c.numeric) ? (
              <tfoot>
                <tr className="border-t-2 border-line-300 bg-paper-soft/60 font-semibold">
                  {shownCols.map((c, i) => {
                    if (c.numeric) {
                      const total = filtered.reduce(
                        (s, m) => s + Number(c.text(m).replace(/\s/g, "")),
                        0,
                      );
                      return (
                        <td key={c.key} className="text-right tabular-nums text-ink-900">
                          {total.toLocaleString("fr-FR")}
                        </td>
                      );
                    }
                    return (
                      <td key={c.key} className="text-ink-600">
                        {i === 0 ? `Total (${filtered.length})` : ""}
                      </td>
                    );
                  })}
                </tr>
              </tfoot>
            ) : null}
          </table>
        </div>
      )}

      <MemberRecapModal member={selected} onClose={() => setSelected(null)} />

      {!loading && count > 0 ? (
        <Pagination
          count={count}
          limit={limit}
          offset={offset}
          onChange={setOffset}
          onLimitChange={(v) => {
            setLimit(v);
            setOffset(0);
          }}
        />
      ) : null}
    </div>
  );
}
