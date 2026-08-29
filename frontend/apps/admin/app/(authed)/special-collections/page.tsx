"use client";

import { useEffect, useMemo, useState } from "react";
import {
  CalendarPlus,
  CheckCircle2,
  Coins,
  Eye,
  GraduationCap,
  Lock,
  Users,
  XCircle,
} from "lucide-react";

import { buttonClasses, SkeletonList } from "@gathe/ui";

import { ConfirmModal } from "@/components/confirm-modal";
import { DataTable, type DataColumn } from "@/components/data-table";
import { Modal } from "@/components/modal";
import { PageHeader } from "@/components/page-header";
import { StatusPill } from "@/components/status-pill";
import {
  adminApi,
  type ApiError,
  type SpecialCollectionCycleRow,
  type SpecialCollectionRow,
  type SpecialCollectionTx,
  type SpecialCollectionType,
} from "@/lib/api";

const COLLECTION_TYPES: Array<{ key: SpecialCollectionType; label: string }> = [
  { key: "caisse_scolaire", label: "Caisse scolaire" },
  { key: "tontine_alimentaire", label: "Tontine" },
];

const TYPE_TABS: Array<{ key: SpecialCollectionType | "all"; label: string }> = [
  { key: "all", label: "Toutes" },
  { key: "caisse_scolaire", label: "Caisse scolaire" },
  { key: "tontine_alimentaire", label: "Tontine" },
];

const STATUT_TABS: Array<{ key: string; label: string }> = [
  { key: "all", label: "Tous statuts" },
  { key: "en_attente", label: "À valider" },
  { key: "valide", label: "Validés" },
  { key: "rejete", label: "Rejetés" },
];

function fmtXAF(v: string | number | null): string {
  const n = Number(v ?? 0);
  return `${Math.round(n).toLocaleString("fr-FR")} FCFA`;
}

export default function SpecialCollectionsPage() {
  const [typeFilter, setTypeFilter] = useState<SpecialCollectionType | "all">("all");
  const [statutFilter, setStatutFilter] = useState<string>("all");
  const [rows, setRows] = useState<SpecialCollectionRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [actingId, setActingId] = useState<number | null>(null);
  const [message, setMessage] = useState<{ tone: "ok" | "err"; text: string } | null>(null);

  const [rejectTarget, setRejectTarget] = useState<SpecialCollectionRow | null>(null);
  const [detail, setDetail] = useState<
    (SpecialCollectionRow & { transactions: SpecialCollectionTx[] }) | null
  >(null);

  async function reload() {
    setLoading(true);
    try {
      const data = await adminApi.specialCollections.list({
        type: typeFilter === "all" ? undefined : typeFilter,
        statut: statutFilter === "all" ? undefined : statutFilter,
      });
      setRows(data);
    } catch (err) {
      setMessage({ tone: "err", text: (err as ApiError).detail ?? "Chargement impossible." });
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [typeFilter, statutFilter]);

  async function onValidate(row: SpecialCollectionRow) {
    setActingId(row.id);
    try {
      await adminApi.specialCollections.validate(row.id);
      setMessage({ tone: "ok", text: `Participation de ${row.member_prenom} ${row.member_nom} validée.` });
      await reload();
    } catch (err) {
      setMessage({ tone: "err", text: (err as ApiError).detail ?? "Validation impossible." });
    } finally {
      setActingId(null);
    }
  }

  async function onReject(motif: string) {
    if (!rejectTarget) return;
    setActingId(rejectTarget.id);
    try {
      await adminApi.specialCollections.reject(rejectTarget.id, motif);
      setMessage({ tone: "ok", text: "Participation rejetée." });
      setRejectTarget(null);
      await reload();
    } catch (err) {
      setMessage({ tone: "err", text: (err as ApiError).detail ?? "Rejet impossible." });
    } finally {
      setActingId(null);
    }
  }

  async function openDetail(row: SpecialCollectionRow) {
    try {
      setDetail(await adminApi.specialCollections.detail(row.id));
    } catch (err) {
      setMessage({ tone: "err", text: (err as ApiError).detail ?? "Détail indisponible." });
    }
  }

  const totalSolde = useMemo(
    () => rows.reduce((s, r) => s + Number(r.solde || 0), 0),
    [rows],
  );

  const columns: DataColumn<SpecialCollectionRow>[] = [
    {
      key: "membre",
      label: "Membre participant",
      text: (r) => `${r.member_prenom} ${r.member_nom} ${r.numero_membre}`,
      render: (r) => (
        <div className="min-w-0">
          <p className="truncate font-medium text-ink-900">
            {r.member_prenom} {r.member_nom}
          </p>
          <p className="text-xs text-ink-500">{r.numero_membre}</p>
        </div>
      ),
    },
    {
      key: "type",
      label: "Collecte",
      text: (r) => r.type_display,
      render: (r) => <span className="text-sm text-ink-700">{r.type_display}</span>,
    },
    {
      key: "cycle",
      label: "Cycle",
      text: (r) => r.cycle_nom,
      render: (r) => (
        <span className="text-xs text-ink-600">
          {r.cycle_nom}
          {r.cycle_statut === "clos" ? (
            <span className="ml-1 rounded bg-ink-100 px-1 py-0.5 text-[10px] text-ink-500">
              clos
            </span>
          ) : null}
        </span>
      ),
    },
    {
      key: "objectif",
      label: "Objectif",
      text: (r) => r.objectif ?? "",
      render: (r) => (
        <span className="line-clamp-2 max-w-xs text-xs text-ink-600" title={r.objectif}>
          {r.objectif || "—"}
        </span>
      ),
    },
    {
      key: "cible",
      label: "Cible",
      numeric: true,
      align: "right",
      text: (r) => (r.montant_cible ? fmtXAF(r.montant_cible) : "—"),
    },
    {
      key: "solde",
      label: "Solde",
      numeric: true,
      align: "right",
      text: (r) => fmtXAF(r.solde),
      render: (r) => <span className="font-semibold tabular-nums text-ink-900">{fmtXAF(r.solde)}</span>,
    },
    {
      key: "statut",
      label: "Statut",
      text: (r) => r.statut_display,
      render: (r) => <StatusPill statut={r.statut} label={r.statut_display} />,
    },
    {
      key: "actions",
      label: "",
      filterable: false,
      text: () => "",
      render: (r) => (
        <div className="flex items-center justify-end gap-2">
          <button
            type="button"
            onClick={() => openDetail(r)}
            className="inline-flex items-center gap-1 rounded-md border border-line-300 px-2.5 py-1.5 text-xs font-medium text-ink-700 hover:border-blue-400 hover:text-blue-700"
          >
            <Eye className="size-3.5" /> Détail
          </button>
          {r.statut === "en_attente" ? (
            <>
              <button
                type="button"
                disabled={actingId === r.id}
                onClick={() => onValidate(r)}
                className="inline-flex items-center gap-1 rounded-md border border-emerald/40 bg-emerald/10 px-2.5 py-1.5 text-xs font-semibold text-emerald hover:bg-emerald/20 disabled:opacity-50"
              >
                <CheckCircle2 className="size-3.5" /> Valider
              </button>
              <button
                type="button"
                disabled={actingId === r.id}
                onClick={() => setRejectTarget(r)}
                className="inline-flex items-center gap-1 rounded-md border border-terra-300 bg-terra-50/60 px-2.5 py-1.5 text-xs font-semibold text-terra-700 hover:bg-terra-50 disabled:opacity-50"
              >
                <XCircle className="size-3.5" /> Rejeter
              </button>
            </>
          ) : null}
        </div>
      ),
    },
  ];

  return (
    <div className="space-y-5">
      <PageHeader
        eyebrow="Épargne & versements"
        title="Collectes particulières"
        description="Caisse scolaire et tontine : validez les demandes de participation et suivez le solde de chaque membre participant."
      />

      {message ? (
        <div
          className={
            "rounded-md px-4 py-2.5 text-sm " +
            (message.tone === "ok"
              ? "bg-emerald/10 text-emerald"
              : "bg-terra-50 text-terra-700")
          }
        >
          {message.text}
        </div>
      ) : null}

      {/* Collectes — plusieurs ouvertes par type possibles ; clôture individuelle */}
      <CyclesPanel onMessage={setMessage} onChanged={reload} />

      {/* Filtres */}
      <div className="flex flex-wrap items-center gap-2">
        {TYPE_TABS.map((t) => (
          <button
            key={t.key}
            type="button"
            onClick={() => setTypeFilter(t.key)}
            className={
              "rounded-full px-3.5 py-1.5 text-sm font-medium " +
              (typeFilter === t.key
                ? "bg-blue-600 text-white"
                : "border border-line-300 text-ink-700 hover:border-blue-400")
            }
          >
            {t.label}
          </button>
        ))}
        <span className="mx-1 h-5 w-px bg-line-300" />
        {STATUT_TABS.map((t) => (
          <button
            key={t.key}
            type="button"
            onClick={() => setStatutFilter(t.key)}
            className={
              "rounded-full px-3.5 py-1.5 text-sm font-medium " +
              (statutFilter === t.key
                ? "bg-ink-900 text-white"
                : "border border-line-300 text-ink-700 hover:border-ink-400")
            }
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Récap */}
      <div className="flex items-center gap-2 rounded-md border border-line-200 bg-paper-soft/40 px-4 py-3 text-sm">
        <Coins className="size-4 text-blue-600" />
        <span className="text-ink-700">
          <strong>{rows.length}</strong> participation{rows.length > 1 ? "s" : ""} · encours total{" "}
          <strong className="tabular-nums">{fmtXAF(totalSolde)}</strong>
        </span>
      </div>

      {loading ? (
        <SkeletonList count={6} />
      ) : (
        <DataTable
          columns={columns}
          rows={rows}
          rowKey={(r) => r.id}
          emptyLabel="Aucune participation pour ce filtre."
        />
      )}

      {/* Rejet — motif obligatoire */}
      <ConfirmModal
        open={rejectTarget !== null}
        onClose={() => setRejectTarget(null)}
        onConfirm={onReject}
        title="Rejeter cette demande de participation ?"
        tone="danger"
        confirmLabel="Rejeter"
        message={
          <p>
            La demande de{" "}
            <strong>
              {rejectTarget?.member_prenom} {rejectTarget?.member_nom}
            </strong>{" "}
            pour « {rejectTarget?.type_display} » sera rejetée. Le membre pourra la
            re-soumettre.
          </p>
        }
        input={{
          label: "Motif (communiqué au membre)",
          placeholder: "Ex. objectif à préciser…",
          required: true,
          multiline: true,
        }}
      />

      {/* Détail + transactions */}
      {detail ? (
        <Modal
          open
          onClose={() => setDetail(null)}
          title={`${detail.member_prenom} ${detail.member_nom}`}
          description={`${detail.type_display} · ${detail.statut_display}`}
        >
          <div className="space-y-4">
            <div className="rounded-md border border-line-200 bg-paper-soft/40 px-4 py-3 text-sm">
              <div className="flex justify-between py-1">
                <span className="text-ink-500">Solde actuel</span>
                <span className="font-semibold tabular-nums">{fmtXAF(detail.solde)}</span>
              </div>
              {detail.montant_cible ? (
                <div className="flex justify-between py-1">
                  <span className="text-ink-500">Montant cible</span>
                  <span className="tabular-nums">{fmtXAF(detail.montant_cible)}</span>
                </div>
              ) : null}
            </div>

            <div>
              <p className="mb-1 text-xs font-semibold uppercase tracking-wider text-ink-500">
                Objectif du membre
              </p>
              <p className="whitespace-pre-wrap text-sm text-ink-800">{detail.objectif || "—"}</p>
            </div>

            {Object.keys(detail.form_payload ?? {}).length > 0 ? (
              <div>
                <p className="mb-1 text-xs font-semibold uppercase tracking-wider text-ink-500">
                  Champs additionnels
                </p>
                {Object.entries(detail.form_payload).map(([k, v]) => (
                  <div key={k} className="flex justify-between gap-4 py-1 text-sm">
                    <span className="text-ink-500">{k}</span>
                    <span className="text-right font-medium text-ink-900">{String(v)}</span>
                  </div>
                ))}
              </div>
            ) : null}

            <div>
              <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-ink-500">
                Mouvements ({detail.transactions.length})
              </p>
              {detail.transactions.length === 0 ? (
                <p className="text-sm text-ink-500">Aucun mouvement pour l’instant.</p>
              ) : (
                <div className="space-y-1.5">
                  {detail.transactions.map((t) => (
                    <div
                      key={t.id}
                      className="flex items-center justify-between rounded-md border border-line-200 px-3 py-2 text-sm"
                    >
                      <div>
                        <p className="font-medium text-ink-800">{t.type_op_display}</p>
                        <p className="text-xs text-ink-500">
                          {new Date(t.date_effective ?? t.created_at).toLocaleString("fr-FR", {
                            day: "2-digit",
                            month: "short",
                            hour: "2-digit",
                            minute: "2-digit",
                          })}
                        </p>
                      </div>
                      <div className="text-right">
                        <p className="font-semibold tabular-nums text-emerald">+{fmtXAF(t.montant)}</p>
                        <p className="text-xs text-ink-500 tabular-nums">
                          solde {fmtXAF(t.solde_apres)}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <button
              type="button"
              onClick={() => setDetail(null)}
              className={buttonClasses({ variant: "secondary", fullWidth: true })}
            >
              Fermer
            </button>
          </div>
        </Modal>
      ) : null}
    </div>
  );
}


// ── Panneau Cycles ────────────────────────────────────────────────────────────
// Pastille de type — icône teintée douce (bleu = caisse, vert = tontine).
function CycleTypeBadge({ type }: { type: SpecialCollectionType }) {
  const isCaisse = type === "caisse_scolaire";
  return (
    <span
      className={
        "flex size-9 shrink-0 items-center justify-center rounded-xl " +
        (isCaisse ? "bg-blue-50 text-blue-600" : "bg-emerald/10 text-emerald")
      }
      title={isCaisse ? "Caisse scolaire" : "Tontine"}
    >
      {isCaisse ? (
        <GraduationCap className="size-[18px]" />
      ) : (
        <Users className="size-[18px]" />
      )}
    </span>
  );
}

// Indicateur d'état discret (point + libellé).
function StatusDot({ open }: { open: boolean }) {
  return (
    <span className="hidden w-[76px] items-center gap-1.5 md:inline-flex">
      <span
        className={
          "size-1.5 rounded-full " + (open ? "bg-emerald" : "bg-line-300")
        }
      />
      <span
        className={
          "text-[11.5px] " + (open ? "text-ink-600" : "text-ink-400")
        }
      >
        {open ? "Ouverte" : "Clôturée"}
      </span>
    </span>
  );
}

function CyclesPanel({
  onMessage,
  onChanged,
}: {
  onMessage: (m: { tone: "ok" | "err"; text: string }) => void;
  onChanged: () => void;
}) {
  const [cycles, setCycles] = useState<SpecialCollectionCycleRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [openFor, setOpenFor] = useState<SpecialCollectionType | null>(null);
  const [nom, setNom] = useState("");
  const [description, setDescription] = useState("");
  const [montantMin, setMontantMin] = useState("");
  const [dateDebut, setDateDebut] = useState("");
  const [dateFin, setDateFin] = useState("");
  const [busy, setBusy] = useState(false);
  const [closeTarget, setCloseTarget] = useState<SpecialCollectionCycleRow | null>(null);

  async function reload() {
    setLoading(true);
    try {
      setCycles(await adminApi.specialCollections.cycles.list());
    } catch (err) {
      onMessage({ tone: "err", text: (err as ApiError).detail ?? "Cycles indisponibles." });
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function openCycle(type: SpecialCollectionType) {
    setOpenFor(type);
    setNom("");
    setDescription("");
    setMontantMin("");
    setDateDebut("");
    setDateFin("");
  }

  async function submitOpen() {
    if (!openFor || !nom.trim()) return;
    setBusy(true);
    try {
      await adminApi.specialCollections.cycles.open({
        type: openFor,
        nom: nom.trim(),
        description: description.trim() || undefined,
        montant_minimal: montantMin ? Number(montantMin) : undefined,
        date_debut: dateDebut || undefined,
        date_fin: dateFin || undefined,
      });
      onMessage({ tone: "ok", text: `Collecte « ${nom.trim()} » ouverte.` });
      setOpenFor(null);
      await reload();
      onChanged();
    } catch (err) {
      onMessage({ tone: "err", text: (err as ApiError).detail ?? "Ouverture impossible." });
    } finally {
      setBusy(false);
    }
  }

  async function doClose(cycle: SpecialCollectionCycleRow) {
    setBusy(true);
    try {
      await adminApi.specialCollections.cycles.close(cycle.id);
      onMessage({ tone: "ok", text: `Cycle « ${cycle.nom} » clôturé (gelé + archivé).` });
      setCloseTarget(null);
      await reload();
      onChanged();
    } catch (err) {
      onMessage({ tone: "err", text: (err as ApiError).detail ?? "Clôture impossible." });
    } finally {
      setBusy(false);
    }
  }

  // Listing plat : ouvertes d'abord, puis archivées ; chaque famille garde son
  // ordre le plus récent (l'API renvoie déjà -date_debut).
  const ordered = [...cycles].sort((a, b) => {
    if (a.is_open !== b.is_open) return a.is_open ? -1 : 1;
    return 0;
  });

  return (
    <section className="rounded-xl border border-line-200 bg-paper">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-line-200 px-5 py-3.5">
        <div>
          <h2 className="text-sm font-semibold text-ink-900">Collectes</h2>
          <p className="text-xs text-ink-500">
            Caisses scolaires &amp; tontines — plusieurs par type, clôture individuelle.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {COLLECTION_TYPES.map((t) => (
            <button
              key={t.key}
              type="button"
              disabled={busy}
              onClick={() => openCycle(t.key)}
              className="inline-flex items-center gap-1.5 rounded-lg border border-line-200 bg-paper px-3 py-1.5 text-xs font-medium text-ink-700 transition-colors hover:border-blue-400 hover:text-blue-700 disabled:opacity-50"
            >
              <CalendarPlus className="size-3.5" /> {t.label}
            </button>
          ))}
        </div>
      </header>

      {loading ? (
        <div className="p-4">
          <SkeletonList count={3} />
        </div>
      ) : ordered.length === 0 ? (
        <p className="px-5 py-8 text-center text-sm text-ink-400">
          Aucune collecte pour le moment — ouvres-en une pour permettre les demandes.
        </p>
      ) : (
        <ul className="divide-y divide-line-100">
          {ordered.map((c) => (
            <li
              key={c.id}
              className="group flex items-center gap-4 px-5 py-2.5 transition-colors hover:bg-paper-soft/50"
            >
              <CycleTypeBadge type={c.type} />
              <div className="min-w-0 flex-1">
                <p className="truncate text-[13.5px] font-medium text-ink-900">
                  {c.nom}
                </p>
                <p className="truncate text-[11.5px] text-ink-400">
                  {c.participants ?? 0} participant{(c.participants ?? 0) > 1 ? "s" : ""}
                  {Number(c.montant_minimal ?? 0) > 0
                    ? ` · min ${fmtXAF(c.montant_minimal ?? 0)}`
                    : ""}
                </p>
              </div>
              <div className="hidden text-right sm:block">
                <p className="text-[10px] uppercase tracking-wide text-ink-400">
                  Collecté
                </p>
                <p
                  className={
                    "text-[13.5px] font-semibold tabular-nums " +
                    (c.is_open ? "text-ink-900" : "text-ink-400")
                  }
                >
                  {fmtXAF(c.total_collecte ?? 0)}
                </p>
              </div>
              <StatusDot open={c.is_open} />
              {c.is_open ? (
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => setCloseTarget(c)}
                  className="inline-flex items-center gap-1 rounded-lg border border-line-200 px-2.5 py-1.5 text-[11.5px] font-medium text-ink-500 opacity-0 transition-all hover:border-terra-300 hover:text-terra-600 group-hover:opacity-100 disabled:opacity-50"
                  title="Clôturer (gèle + archive ce cycle)"
                >
                  <Lock className="size-3.5" /> Clôturer
                </button>
              ) : (
                <span className="w-[92px]" />
              )}
            </li>
          ))}
        </ul>
      )}

      {/* Modale ouverture de cycle */}
      {openFor ? (
        <Modal
          open
          onClose={() => setOpenFor(null)}
          title="Ouvrir une nouvelle collecte"
          description={COLLECTION_TYPES.find((t) => t.key === openFor)?.label}
        >
          <div className="space-y-3">
            <p className="rounded-md bg-cream px-3 py-2 text-xs text-ink-600">
              Plusieurs collectes du même type peuvent coexister. Fixe le titre, le
              montant minimal par versement et les informations. Les membres
              choisiront cette collecte pour y participer.
            </p>
            <label className="block text-sm">
              <span className="mb-1 block text-xs font-semibold text-ink-600">Titre de la collecte</span>
              <input
                value={nom}
                onChange={(e) => setNom(e.target.value)}
                placeholder="Ex. Tontine des fêtes 2026"
                className="w-full rounded-md border border-line-300 px-3 py-2 text-sm"
              />
            </label>
            <label className="block text-sm">
              <span className="mb-1 block text-xs font-semibold text-ink-600">
                Montant minimal par versement (FCFA)
              </span>
              <input
                type="number"
                min={0}
                value={montantMin}
                onChange={(e) => setMontantMin(e.target.value)}
                placeholder="0 = pas de plancher"
                className="w-full rounded-md border border-line-300 px-3 py-2 text-sm"
              />
            </label>
            <label className="block text-sm">
              <span className="mb-1 block text-xs font-semibold text-ink-600">
                Informations (facultatif)
              </span>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                rows={3}
                placeholder="Règles, dates clés, modalités…"
                className="w-full rounded-md border border-line-300 px-3 py-2 text-sm"
              />
            </label>
            <div className="grid grid-cols-2 gap-3">
              <label className="block text-sm">
                <span className="mb-1 block text-xs font-semibold text-ink-600">Début (optionnel)</span>
                <input
                  type="date"
                  value={dateDebut}
                  onChange={(e) => setDateDebut(e.target.value)}
                  className="w-full rounded-md border border-line-300 px-3 py-2 text-sm"
                />
              </label>
              <label className="block text-sm">
                <span className="mb-1 block text-xs font-semibold text-ink-600">Fin (optionnel)</span>
                <input
                  type="date"
                  value={dateFin}
                  onChange={(e) => setDateFin(e.target.value)}
                  className="w-full rounded-md border border-line-300 px-3 py-2 text-sm"
                />
              </label>
            </div>
            <button
              type="button"
              disabled={busy || !nom.trim()}
              onClick={submitOpen}
              className={buttonClasses({ variant: "primary", fullWidth: true })}
            >
              {busy ? "Ouverture…" : "Ouvrir la collecte"}
            </button>
          </div>
        </Modal>
      ) : null}

      <ConfirmModal
        open={closeTarget !== null}
        onClose={() => setCloseTarget(null)}
        onConfirm={() => (closeTarget ? doClose(closeTarget) : undefined)}
        title="Clôturer cette collecte ?"
        tone="danger"
        confirmLabel="Clôturer (geler)"
        message={
          <p>
            La collecte <strong>{closeTarget?.nom}</strong> sera gelée et archivée :
            les soldes sont figés, plus aucun versement possible. Aucun mouvement
            d’argent automatique. Les autres collectes du même type restent ouvertes.
          </p>
        }
      />
    </section>
  );
}
