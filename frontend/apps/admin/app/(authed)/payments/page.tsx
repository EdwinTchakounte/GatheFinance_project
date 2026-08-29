"use client";

import { useEffect, useMemo, useState } from "react";
import { SkeletonList } from "@gathe/ui";
import { Search, Plus, Minus } from "lucide-react";

import { CashInModal } from "@/components/cash-in-modal";
import { ManualDebitModal } from "@/components/manual-debit-modal";
import { ConfirmModal } from "@/components/confirm-modal";
import { DataTable, type DataColumn } from "@/components/data-table";
import { PageHeader } from "@/components/page-header";
import { Pagination } from "@/components/pagination";
import {
  adminApi,
  type ApiError,
  type PaymentRow,
  type PaymentStats,
} from "@/lib/api";
import { fullName } from "@/lib/name";
import { StatusPill } from "@/components/status-pill";


type StatutFilter = "" | "en_attente" | "valide" | "rejete" | "annule";
// SOURCE DE VERITE : doit refleter Payment.Type cote backend
// (backend/apps_coop/payments/models.py Type TextChoices).
type TypeFilter =
  | ""
  | "epargne"
  | "epargne_classique"
  | "frais_adhesion"
  | "frais_inscription"
  | "frais_demande_credit"
  | "frais_reconduction"
  | "frais_carnet"
  | "remboursement"
  | "decaissement";


export default function PaymentsPage() {
  return <Inner />;
}


function Inner() {
  const [statut, setStatut] = useState<StatutFilter>("");
  const [typeFilter, setTypeFilter] = useState<TypeFilter>("");
  // Deep-link « voir ce paiement » : ?q=<id> dans l'URL (ex. « Paiement #52 »
  // depuis une commande de carnet) initialise la recherche DÈS le 1er rendu,
  // pour que tous les chargements (y compris le double-invoke StrictMode en dev)
  // partent du bon `q` — sinon un chargement « tout » écrase le filtré.
  const [q, setQ] = useState(() =>
    typeof window !== "undefined"
      ? new URLSearchParams(window.location.search).get("q") ?? ""
      : "",
  );
  const [items, setItems] = useState<PaymentRow[]>([]);
  const [count, setCount] = useState(0);
  const [limit, setLimit] = useState(25);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  // B1 . Cash-in modal admin (saisie versement agence).
  const [cashInOpen, setCashInOpen] = useState(false);
  const [debitOpen, setDebitOpen] = useState(false);
  const [flash, setFlash] = useState<string | null>(null);
  // Invalidation : cible de la modale de confirmation (remplace window.prompt).
  const [invalidateTarget, setInvalidateTarget] = useState<PaymentRow | null>(null);

  // État global (totaux essentiels) — agrégats sur TOUS les paiements, filtrables
  // par période. Indépendant de la pagination de la table.
  const [stats, setStats] = useState<PaymentStats | null>(null);
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  // `reload`/`loadStats` acceptent un override de `q` : au tout premier montage
  // on applique un éventuel deep-link `?q=<id>` (ex. « voir ce paiement » depuis
  // une commande de carnet) en UN SEUL fetch — sinon un chargement « tout » et
  // le chargement filtré se courent après et le mauvais gagne.
  async function loadStats(qOverride?: string) {
    try {
      const res = await adminApi.payments.stats({
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
        type: typeFilter || undefined,
        q: (qOverride ?? q).trim() || undefined,
      });
      setStats(res);
    } catch {
      // Le bandeau est secondaire : on n'interrompt pas la page en cas d'échec.
      setStats(null);
    }
  }

  async function reload(qOverride?: string) {
    setLoading(true);
    setError(null);
    try {
      const res = await adminApi.payments.list({
        statut: statut || undefined,
        type: typeFilter || undefined,
        q: (qOverride ?? q).trim() || undefined,
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
  }, [statut, typeFilter, limit, offset]);

  // Bandeau « état global » : recharge sur changement de période ou de type.
  useEffect(() => {
    loadStats();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dateFrom, dateTo, typeFilter]);

  const totalValide = useMemo(
    () =>
      items
        .filter((p) => p.statut === "valide")
        .reduce((acc, p) => acc + Number(p.montant || 0), 0),
    [items],
  );

  const totalFrais = useMemo(
    () =>
      items
        .filter((p) => p.statut === "valide")
        .reduce((acc, p) => acc + Number(p.frais_transaction || 0), 0),
    [items],
  );

  const columns: DataColumn<PaymentRow>[] = [
    {
      key: "date",
      label: "Date",
      text: (p) => p.date_versement,
      render: (p) => (
        <div className="whitespace-nowrap text-sm">
          <p className="text-ink-900">
            {new Date(p.date_versement).toLocaleDateString("fr-FR", {
              day: "2-digit",
              month: "short",
              year: "2-digit",
            })}
          </p>
          <p className="font-mono text-xs text-ink-500">
            {new Date(p.date_versement).toLocaleTimeString("fr-FR", {
              hour: "2-digit",
              minute: "2-digit",
            })}
          </p>
        </div>
      ),
    },
    {
      key: "membre",
      label: "Membre",
      locked: true,
      text: (p) => `${fullName(p.member.prenom, p.member.nom)} ${p.member.numero_membre}`,
      render: (p) => (
        <div>
          <p className="font-medium text-ink-900">
            {fullName(p.member.prenom, p.member.nom)}
          </p>
          <p className="font-mono text-xs text-ink-500">{p.member.numero_membre}</p>
        </div>
      ),
    },
    {
      key: "type",
      label: "Type",
      text: (p) => p.type_display,
      render: (p) => (
        <span className="text-sm text-ink-700">
          {p.type_display}
          {p.type === "epargne" &&
          typeof p.nb_jours_couverts === "number" &&
          p.nb_jours_couverts > 1 ? (
            <span className="ml-1 inline-flex rounded-full bg-amber-100 px-1.5 py-0.5 text-[10px] font-medium text-amber-700">
              × {p.nb_jours_couverts} j
            </span>
          ) : null}
        </span>
      ),
    },
    {
      key: "montant",
      label: "Montant",
      numeric: true,
      align: "right",
      text: (p) => p.montant,
      render: (p) => (
        <span className="font-mono text-sm text-ink-900">
          {Number(p.montant).toLocaleString("fr-FR")}
          <span className="ml-1 text-xs text-ink-500">XAF</span>
        </span>
      ),
    },
    {
      // Frais de transaction facturés EN PLUS du montant (3% MoMo, 0 en agence).
      key: "frais",
      label: "Frais",
      numeric: true,
      align: "right",
      text: (p) => p.frais_transaction ?? "0",
      render: (p) => {
        const frais = Number(p.frais_transaction || 0);
        return frais > 0 ? (
          <span className="font-mono text-sm text-amber-700">
            +{frais.toLocaleString("fr-FR")}
            <span className="ml-1 text-xs text-amber-600/70">XAF</span>
          </span>
        ) : (
          <span className="text-xs text-ink-400"></span>
        );
      },
    },
    {
      // Total réellement débité au membre = montant initié + frais.
      key: "total",
      label: "Total payé",
      numeric: true,
      align: "right",
      text: (p) => String(Number(p.montant || 0) + Number(p.frais_transaction || 0)),
      render: (p) => {
        const total = Number(p.montant || 0) + Number(p.frais_transaction || 0);
        const frais = Number(p.frais_transaction || 0);
        return (
          <span className="font-mono text-sm font-semibold text-ink-900">
            {total.toLocaleString("fr-FR")}
            <span className="ml-1 text-xs text-ink-500">XAF</span>
            {frais > 0 ? (
              <span className="ml-1 block text-[10px] font-normal text-ink-400">
                {Number(p.montant).toLocaleString("fr-FR")} + {frais.toLocaleString("fr-FR")}
              </span>
            ) : null}
          </span>
        );
      },
    },
    {
      key: "source",
      label: "Canal",
      defaultVisible: false,
      text: (p) => p.source,
    },
    {
      key: "ref",
      label: "Référence",
      text: (p) => `${p.reference_externe} ${p.provider_code}`,
      render: (p) => (
        <div className="font-mono text-xs text-ink-600">
          {p.reference_externe || <span className="text-ink-400"></span>}
          <p className="text-[10px] uppercase tracking-wide text-ink-400">
            {p.provider_code}
          </p>
        </div>
      ),
    },
    {
      key: "statut",
      label: "Statut",
      text: (p) => p.statut_display,
      render: (p) => (
        <div>
          <StatusPill statut={p.statut} label={p.statut_display} />
          {p.statut === "rejete" && p.motif_rejet ? (
            <p className="mt-1 max-w-[14rem] text-xs text-terra-700">{p.motif_rejet}</p>
          ) : null}
        </div>
      ),
    },
  ];

  // Confirmée depuis la modale custom (remplace le window.prompt natif qui
  // gelait l'onglet). Le motif saisi part dans la contre-passation.
  async function confirmInvalidate(motif: string) {
    const p = invalidateTarget;
    if (!p) return;
    try {
      await adminApi.payments.invalidate(p.id, motif || undefined);
      setFlash("Paiement invalidé — effet contre-passé.");
      setInvalidateTarget(null);
      await reload();
      loadStats();
    } catch (err) {
      setError((err as ApiError).detail ?? "Invalidation impossible.");
      setInvalidateTarget(null);
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Paiements"
        title="Suivi des paiements"
        description="Tous les versements traversant la plateforme (Mobile Money, espèces, virements)."
        actions={
          <div className="flex items-center gap-3 text-sm text-ink-600">
            <span className="font-mono text-ink-900 font-medium">{count}</span>
            <span>paiement{count > 1 ? "s" : ""}</span>
            <span className="text-ink-400">·</span>
            <span className="font-mono text-emerald font-medium">
              {totalValide.toLocaleString("fr-FR")}
            </span>
            <span>XAF validés (vue actuelle)</span>
            {totalFrais > 0 ? (
              <>
                <span className="text-ink-400">·</span>
                <span className="font-mono text-amber-700 font-medium">
                  +{totalFrais.toLocaleString("fr-FR")}
                </span>
                <span>XAF de frais</span>
              </>
            ) : null}
            <button
              type="button"
              onClick={() => setCashInOpen(true)}
              title="Enregistrer un versement reçu en agence (espèces, virement, dépôt direct)"
              className="inline-flex items-center gap-1.5 rounded-md bg-blue-700 px-3 py-2 text-xs font-medium text-white hover:bg-blue-800"
            >
              <Plus className="size-3.5" />
              Saisir versement agence
            </button>
            <button
              type="button"
              onClick={() => setDebitOpen(true)}
              title="Débiter un compte membre (retrait agence) ou prélever un frais depuis l'épargne"
              className="inline-flex items-center gap-1.5 rounded-md border border-terra-300 px-3 py-2 text-xs font-medium text-terra-700 hover:bg-terra-50"
            >
              <Minus className="size-3.5" />
              Débit / prélèvement
            </button>
          </div>
        }
      />

      {/* État global — totaux essentiels sur TOUS les paiements, filtrables par
          période (indépendant de la pagination de la table ci-dessous). */}
      <section className="rounded-lg border border-line-200 bg-paper p-4">
        <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h2 className="text-sm font-semibold text-ink-900">État global</h2>
            <p className="text-xs text-ink-500">
              {stats?.period.from || stats?.period.to
                ? `Période : ${stats?.period.from ?? "…"} → ${stats?.period.to ?? "…"}`
                : "Sur l'ensemble de l'historique (aucune période sélectionnée)."}
            </p>
          </div>
          <div className="flex flex-wrap items-end gap-2">
            <label className="flex flex-col text-[11px] font-medium text-ink-500">
              Du
              <input
                type="date"
                value={dateFrom}
                onChange={(e) => setDateFrom(e.target.value)}
                className="mt-0.5 rounded-md border border-line-200 bg-paper px-2 py-1.5 text-sm text-ink-900 focus:border-blue-700 focus:outline-none focus:ring-1 focus:ring-blue-700"
              />
            </label>
            <label className="flex flex-col text-[11px] font-medium text-ink-500">
              Au
              <input
                type="date"
                value={dateTo}
                onChange={(e) => setDateTo(e.target.value)}
                className="mt-0.5 rounded-md border border-line-200 bg-paper px-2 py-1.5 text-sm text-ink-900 focus:border-blue-700 focus:outline-none focus:ring-1 focus:ring-blue-700"
              />
            </label>
            <div className="flex gap-1">
              <PeriodPreset
                label="Aujourd'hui"
                onClick={() => {
                  const t = todayISO();
                  setDateFrom(t);
                  setDateTo(t);
                }}
              />
              <PeriodPreset
                label="Ce mois"
                onClick={() => {
                  const now = new Date();
                  setDateFrom(
                    isoDate(new Date(now.getFullYear(), now.getMonth(), 1)),
                  );
                  setDateTo(todayISO());
                }}
              />
              <PeriodPreset
                label="Tout"
                onClick={() => {
                  setDateFrom("");
                  setDateTo("");
                }}
              />
            </div>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <StatTile
            label="Encaissé (validés)"
            value={stats ? Number(stats.valides.montant) : 0}
            count={stats?.valides.count ?? 0}
            tone="emerald"
          />
          <StatTile
            label="Frais encaissés"
            value={stats ? Number(stats.valides.frais) : 0}
            count={stats?.valides.count ?? 0}
            tone="amber"
          />
          <StatTile
            label="En attente"
            value={stats ? Number(stats.en_attente.montant) : 0}
            count={stats?.en_attente.count ?? 0}
            tone="ink"
          />
          <StatTile
            label="Rejetés"
            value={stats ? Number(stats.rejetes.montant) : 0}
            count={stats?.rejetes.count ?? 0}
            tone="terra"
          />
        </div>

        {stats && stats.par_type.length > 0 ? (
          <div className="mt-4 flex flex-wrap gap-2 border-t border-line-200 pt-4">
            {stats.par_type.map((t) => (
              <div
                key={t.type}
                className="rounded-md border border-line-200 bg-paper-soft/40 px-3 py-2"
              >
                <p className="text-[11px] font-medium text-ink-500">
                  {t.type_display}
                </p>
                <p className="font-mono text-sm font-semibold text-ink-900">
                  {Number(t.montant).toLocaleString("fr-FR")}
                  <span className="ml-1 text-[10px] font-normal text-ink-400">
                    XAF · {t.count}
                  </span>
                </p>
              </div>
            ))}
          </div>
        ) : null}
      </section>

      <div className="mb-5 flex flex-col gap-3 md:flex-row md:flex-wrap md:items-center">
        <FilterPills
          label="Statut"
          value={statut}
          onChange={(v) => {
            setStatut(v as StatutFilter);
            setOffset(0);
          }}
          options={[
            { v: "", l: "Tous" },
            { v: "en_attente", l: "En attente" },
            { v: "valide", l: "Validés" },
            { v: "rejete", l: "Rejetés" },
            { v: "annule", l: "Annulés" },
          ]}
        />
        <FilterPills
          label="Type"
          value={typeFilter}
          onChange={(v) => {
            setTypeFilter(v as TypeFilter);
            setOffset(0);
          }}
          options={[
            // SOURCE DE VERITE : 9 types Payment cote backend (Article 4 + frais
            // refonte 2026). Tout ajout cote backend doit etre repercute ici.
            { v: "", l: "Tous" },
            { v: "epargne", l: "Collecte" },
            { v: "epargne_classique", l: "Épargne classique" },
            { v: "remboursement", l: "Remboursement" },
            { v: "decaissement", l: "Décaissement" },
            { v: "frais_adhesion", l: "Frais adhésion" },
            { v: "frais_inscription", l: "Frais inscription" },
            { v: "frais_demande_credit", l: "Frais demande crédit" },
            { v: "frais_reconduction", l: "Frais reconduction" },
            { v: "frais_carnet", l: "Frais carnet" },
          ]}
        />
        <form
          onSubmit={(e) => {
            e.preventDefault();
            setOffset(0);
            reload();
            loadStats();
          }}
          className="flex min-w-[240px] flex-1 items-center gap-2"
        >
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-ink-400" />
            <input
              type="search"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Recherche (n° membre, nom, référence Tara…)"
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
      ) : (
        <DataTable
          columns={columns}
          rows={items}
          rowKey={(p) => p.id}
          actions={(p) =>
            p.statut === "valide" && p.type !== "decaissement" ? (
              <button
                type="button"
                onClick={() => setInvalidateTarget(p)}
                className="rounded-md border border-terra-300 px-2.5 py-1 text-xs font-medium text-terra-700 hover:bg-terra-50"
                title="Invalider ce paiement (contre-passation)"
              >
                Invalider
              </button>
            ) : null
          }
          emptyLabel="Aucun paiement ne correspond à ces filtres."
          exportFilename="paiements"
          exportTitle="Suivi des paiements — GATHE Finance"
          exportSubtitle={
            [
              statut && `statut : ${statut}`,
              typeFilter && `type : ${typeFilter}`,
              q && `recherche : ${q}`,
            ]
              .filter(Boolean)
              .join(" · ") || "tous"
          }
        />
      )}

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

      {flash ? (
        <div className="fixed bottom-6 left-1/2 z-40 -translate-x-1/2 rounded-md bg-emerald px-4 py-2 text-sm font-medium text-white shadow-lg">
          {flash}
        </div>
      ) : null}

      <CashInModal
        open={cashInOpen}
        onClose={() => setCashInOpen(false)}
        onSuccess={(msg) => {
          setFlash(msg);
          setTimeout(() => setFlash(null), 4500);
          reload();
          loadStats();
        }}
      />

      <ManualDebitModal
        open={debitOpen}
        onClose={() => setDebitOpen(false)}
        onSuccess={(msg) => {
          setFlash(msg);
          setTimeout(() => setFlash(null), 4500);
          reload();
          loadStats();
        }}
      />

      {/* Invalidation — modale custom (remplace le window.prompt natif qui
          gelait l'onglet). L'effet ledger du paiement est contre-passé. */}
      <ConfirmModal
        open={invalidateTarget !== null}
        onClose={() => setInvalidateTarget(null)}
        onConfirm={confirmInvalidate}
        title="Invalider / annuler ce paiement ?"
        tone="danger"
        confirmLabel="Annuler le paiement"
        message={
          invalidateTarget ? (
            <>
              Le paiement de{" "}
              <strong>
                {Number(invalidateTarget.montant).toLocaleString("fr-FR")} XAF
              </strong>{" "}
              ({invalidateTarget.type_display}) sera marqué rejeté et son effet{" "}
              <strong>contre-passé</strong> — épargne collecte/classique,
              remboursement crédit, collecte particulière ou cagnotte de tontine
              de groupe (le compte concerné est ramené du montant). Action tracée.
            </>
          ) : null
        }
        input={{
          label: "Motif de l'invalidation (optionnel)",
          placeholder: "ex. erreur de saisie, doublon…",
          multiline: true,
        }}
      />
    </div>
  );
}


function isoDate(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(
    d.getDate(),
  ).padStart(2, "0")}`;
}

function todayISO(): string {
  return isoDate(new Date());
}

const STAT_TONES: Record<string, string> = {
  emerald: "text-emerald",
  amber: "text-amber-700",
  terra: "text-terra-700",
  ink: "text-ink-900",
};

function StatTile({
  label,
  value,
  count,
  tone,
}: {
  label: string;
  value: number;
  count: number;
  tone: "emerald" | "amber" | "terra" | "ink";
}) {
  return (
    <div className="rounded-md border border-line-200 bg-paper-soft/40 px-3 py-3">
      <p className="text-[11px] font-medium uppercase tracking-wide text-ink-500">
        {label}
      </p>
      <p className={`mt-1 font-mono text-lg font-semibold ${STAT_TONES[tone]}`}>
        {value.toLocaleString("fr-FR")}
        <span className="ml-1 text-[10px] font-normal text-ink-400">XAF</span>
      </p>
      <p className="text-[11px] text-ink-400">
        {count} paiement{count > 1 ? "s" : ""}
      </p>
    </div>
  );
}

function PeriodPreset({
  label,
  onClick,
}: {
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="rounded-md border border-line-200 bg-paper px-2 py-1.5 text-[11px] font-medium text-ink-600 hover:border-blue-700 hover:text-blue-700"
    >
      {label}
    </button>
  );
}

function FilterPills<T extends string>({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: T;
  onChange: (v: T) => void;
  options: { v: T; l: string }[];
}) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-[0.65rem] font-semibold uppercase tracking-wider text-ink-500">
        {label}
      </span>
      <div className="flex flex-wrap items-center gap-1 rounded-md border border-line-200 bg-paper p-1">
        {options.map((opt) => (
          <button
            key={opt.v || "all"}
            type="button"
            onClick={() => onChange(opt.v)}
            className={[
              "rounded px-2.5 py-1 text-xs font-medium transition-colors",
              value === opt.v
                ? "bg-blue-700 text-white"
                : "text-ink-700 hover:text-blue-700",
            ].join(" ")}
          >
            {opt.l}
          </button>
        ))}
      </div>
    </div>
  );
}
