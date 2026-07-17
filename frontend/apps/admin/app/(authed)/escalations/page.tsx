"use client";

import { useEffect, useState } from "react";
import {
  Gavel,
  AlertCircle,
  CheckCircle2,
  XCircle,
  Briefcase,
  Plus,
  Trash2,
} from "lucide-react";

import { buttonClasses } from "@gathe/ui";

import { ExportMenu } from "@/components/export-menu";
import { Modal } from "@/components/modal";
import type { ExportColumn } from "@/lib/export";
import {
  adminApi,
  type ApiError,
  type JudicialBien,
  type JudicialEscalationRow,
  type JudicialStatut,
} from "@/lib/api";


const escalationsExportColumns: ExportColumn<JudicialEscalationRow>[] = [
  { key: "id", label: "ID", value: (r) => r.id },
  { key: "dossier", label: "N° dossier", value: (r) => r.loan_numero_dossier },
  { key: "membre", label: "Membre", value: (r) => r.member_nom },
  { key: "numero_membre", label: "N° membre", value: (r) => r.member_numero },
  { key: "statut", label: "Statut", value: (r) => r.statut_display },
  { key: "motif", label: "Motif", value: (r) => r.motif },
  { key: "mode", label: "Mode", value: (r) => r.declenche_mode },
  { key: "declenche_at", label: "Déclenchée le", value: (r) => r.declenche_at },
  {
    key: "decision_at",
    label: "Décision le",
    value: (r) => r.decision_date ?? "",
  },
  {
    key: "execution_at",
    label: "Exécution le",
    value: (r) => r.execution_date ?? "",
  },
  {
    key: "montant_recouvre",
    label: "Recouvré",
    value: (r) => r.montant_recouvre,
  },
  {
    key: "closed_at",
    label: "Classée le",
    value: (r) => r.closed_at ?? "",
  },
  { key: "close_reason", label: "Motif clôture", value: (r) => r.close_reason },
];


/**
 * Refonte 2026 — LOT 17 — Escalades judiciaires (phase D/E contentieux).
 *
 * Liste les escalades en cours et permet à l'admin de saisir la décision
 * (E1) ou l'exécution (E2), ou de classer sans suite.
 */
export default function EscalationsPage() {
  return <Inner />;
}


type FilterKey = "open" | "all" | JudicialStatut;


function Inner() {
  const [filter, setFilter] = useState<FilterKey>("open");
  const [items, setItems] = useState<JudicialEscalationRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [opened, setOpened] = useState<JudicialEscalationRow | null>(null);
  const [message, setMessage] = useState<{
    tone: "ok" | "err";
    text: string;
  } | null>(null);

  async function reload() {
    setLoading(true);
    try {
      adminApi.primeCsrf().catch(() => undefined);
      const params: Parameters<typeof adminApi.escalations.list>[0] = {};
      if (filter === "open") params.open = "true";
      else if (filter !== "all") params.statut = filter;
      const data = await adminApi.escalations.list(params);
      setItems(data.results);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    reload();
    /* eslint-disable-next-line react-hooks/exhaustive-deps */
  }, [filter]);

  return (
    <main className="space-y-6 p-8">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div className="space-y-1">
          <h1 className="font-display text-2xl text-ink-900">
            Escalades judiciaires
          </h1>
          <p className="text-sm text-ink-500">
            Phase D/E du contentieux 2026 — instruction huissier, décision rendue,
            exécution saisie biens. Le crédit doit avoir une saisie épargne (R1)
            déjà tentée et un reliquat &gt; 0.
          </p>
        </div>
        <ExportMenu
          filenamePrefix="escalades-judiciaires"
          title="Escalades judiciaires — GATHE Finance"
          subtitle={`Filtre : ${filter}`}
          columns={escalationsExportColumns}
          rows={items}
        />
      </header>

      <div className="flex flex-wrap items-center gap-2">
        {(
          [
            ["open", "En cours"],
            ["en_instance", "En instance (D)"],
            ["decision_rendue", "Décision rendue (E1)"],
            ["executee", "Exécutées (E2)"],
            ["classee_sans_suite", "Classées sans suite"],
            ["all", "Toutes"],
          ] as const
        ).map(([key, label]) => (
          <button
            key={key}
            onClick={() => setFilter(key)}
            className={`rounded-full border px-4 py-1.5 text-sm transition ${
              filter === key
                ? "border-terra-600 bg-terra-50 text-terra-700"
                : "border-line-200 text-ink-500 hover:bg-paper-soft"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {message && (
        <div
          className={`rounded-lg border px-4 py-3 text-sm ${
            message.tone === "ok"
              ? "border-emerald-200 bg-emerald-50 text-emerald-700"
              : "border-red-200 bg-red-50 text-red-700"
          }`}
        >
          {message.text}
        </div>
      )}

      <section className="rounded-2xl border border-line-200 bg-paper">
        {loading && (
          <p className="px-6 py-12 text-center text-sm text-ink-500">
            Chargement…
          </p>
        )}
        {!loading && items.length === 0 && (
          <p className="px-6 py-12 text-center text-sm text-ink-500">
            Aucune escalade pour ce filtre.
          </p>
        )}
        {!loading && items.length > 0 && (
          <ul className="divide-y divide-line-200">
            {items.map((row) => (
              <EscalationRow
                key={row.id}
                row={row}
                onOpen={() => setOpened(row)}
              />
            ))}
          </ul>
        )}
      </section>

      {opened && (
        <DetailModal
          escalation={opened}
          onClose={() => setOpened(null)}
          onUpdated={(text) => {
            setMessage({ tone: "ok", text });
            reload();
          }}
          onError={(text) => setMessage({ tone: "err", text })}
        />
      )}
    </main>
  );
}


function EscalationRow({
  row,
  onOpen,
}: {
  row: JudicialEscalationRow;
  onOpen: () => void;
}) {
  return (
    <li className="flex flex-wrap items-start gap-4 px-6 py-5">
      <div className="flex-1 min-w-[300px] space-y-1.5">
        <div className="flex flex-wrap items-center gap-2 text-sm font-semibold text-ink-900">
          <Gavel className="h-4 w-4 text-terra-600" />
          {row.member_nom}{" "}
          <span className="text-xs font-medium text-ink-500">
            {row.member_numero}
          </span>
          <StatutBadge statut={row.statut} display={row.statut_display} />
          <span className="rounded-full bg-paper-soft px-2 py-0.5 text-xs font-medium text-ink-500">
            {row.loan_numero_dossier}
          </span>
        </div>
        <div className="flex flex-wrap items-center gap-4 text-xs text-ink-500">
          <span>
            Reliquat :{" "}
            <strong className="text-ink-900">
              {formatXaf(row.loan_solde_restant)}
            </strong>
          </span>
          <span>Mode : {row.declenche_mode}</span>
          <span>Ouverte le : {formatDate(row.declenche_at)}</span>
          {row.decision_date && (
            <span>Décision : {formatDate(row.decision_date)}</span>
          )}
          {row.execution_date && (
            <span>
              Exécutée le : {formatDate(row.execution_date)} (
              {formatXaf(row.montant_recouvre)})
            </span>
          )}
        </div>
      </div>
      <button
        onClick={onOpen}
        className={buttonClasses({ variant: "ghost", size: "sm" })}
      >
        Détail / actions
      </button>
    </li>
  );
}


function StatutBadge({
  statut,
  display,
}: {
  statut: JudicialStatut;
  display: string;
}) {
  const cls: Record<JudicialStatut, string> = {
    en_instance: "bg-amber-100 text-amber-700",
    decision_rendue: "bg-blue-100 text-blue-700",
    executee: "bg-emerald-100 text-emerald-700",
    classee_sans_suite: "bg-stone-200 text-stone-700",
  };
  const Icon: Record<JudicialStatut, React.ComponentType<{ className?: string }>> = {
    en_instance: AlertCircle,
    decision_rendue: Briefcase,
    executee: CheckCircle2,
    classee_sans_suite: XCircle,
  };
  const I = Icon[statut];
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${cls[statut]}`}
    >
      <I className="h-3 w-3" />
      {display}
    </span>
  );
}


// ---------------------------------------------------------------------------
// Detail + actions
// ---------------------------------------------------------------------------


function DetailModal({
  escalation,
  onClose,
  onUpdated,
  onError,
}: {
  escalation: JudicialEscalationRow;
  onClose: () => void;
  onUpdated: (msg: string) => void;
  onError: (msg: string) => void;
}) {
  const [tab, setTab] = useState<
    "info" | "decision" | "execution" | "classer"
  >("info");

  const canDecision = escalation.statut === "en_instance";
  const canExecution = escalation.statut === "decision_rendue";
  const canClasser =
    escalation.statut === "en_instance" ||
    escalation.statut === "decision_rendue";

  return (
    <Modal
      open
      onClose={onClose}
      title={`Escalade — ${escalation.member_nom} (${escalation.loan_numero_dossier})`}
    >
      <div className="mb-3 flex flex-wrap gap-2 border-b border-line-200 pb-2">
        <TabButton active={tab === "info"} onClick={() => setTab("info")}>
          Info
        </TabButton>
        {canDecision && (
          <TabButton
            active={tab === "decision"}
            onClick={() => setTab("decision")}
          >
            Saisir décision (E1)
          </TabButton>
        )}
        {canExecution && (
          <TabButton
            active={tab === "execution"}
            onClick={() => setTab("execution")}
          >
            Saisir exécution (E2)
          </TabButton>
        )}
        {canClasser && (
          <TabButton
            active={tab === "classer"}
            onClick={() => setTab("classer")}
          >
            Classer sans suite
          </TabButton>
        )}
      </div>

      {tab === "info" && <InfoTab e={escalation} />}
      {tab === "decision" && (
        <DecisionTab
          escalation={escalation}
          onDone={(msg) => {
            onUpdated(msg);
            onClose();
          }}
          onError={onError}
        />
      )}
      {tab === "execution" && (
        <ExecutionTab
          escalation={escalation}
          onDone={(msg) => {
            onUpdated(msg);
            onClose();
          }}
          onError={onError}
        />
      )}
      {tab === "classer" && (
        <ClasserTab
          escalation={escalation}
          onDone={(msg) => {
            onUpdated(msg);
            onClose();
          }}
          onError={onError}
        />
      )}
    </Modal>
  );
}


function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={`rounded-md px-3 py-1.5 text-xs font-medium transition ${
        active
          ? "bg-blue-700 text-white"
          : "text-ink-500 hover:bg-paper-soft"
      }`}
    >
      {children}
    </button>
  );
}


function InfoTab({ e }: { e: JudicialEscalationRow }) {
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-3 rounded-lg border border-line-200 bg-paper-soft p-3 text-xs">
        <Info label="Statut" value={e.statut_display} />
        <Info label="Mode déclenchement" value={e.declenche_mode} />
        <Info label="Ouverte le" value={formatDate(e.declenche_at)} />
        <Info label="Reliquat crédit" value={formatXaf(e.loan_solde_restant)} />
        {e.decision_date && (
          <Info label="Décision rendue le" value={formatDate(e.decision_date)} />
        )}
        {e.execution_date && (
          <>
            <Info label="Exécutée le" value={formatDate(e.execution_date)} />
            <Info label="Montant recouvré" value={formatXaf(e.montant_recouvre)} />
          </>
        )}
        {e.close_reason && (
          <Info label="Raison clôture" value={e.close_reason} />
        )}
      </div>

      <Section title="Motif d'ouverture">
        <p className="rounded-md border border-line-200 bg-paper-soft px-3 py-2 text-sm text-ink-700 whitespace-pre-wrap">
          {e.motif || ""}
        </p>
      </Section>

      {e.biens_saisissables.length > 0 && (
        <Section title="Biens saisissables (décision)">
          <BienList biens={e.biens_saisissables} />
        </Section>
      )}
      {e.biens_saisis.length > 0 && (
        <Section title="Biens effectivement saisis">
          <BienList biens={e.biens_saisis} />
        </Section>
      )}
    </div>
  );
}


function DecisionTab({
  escalation,
  onDone,
  onError,
}: {
  escalation: JudicialEscalationRow;
  onDone: (msg: string) => void;
  onError: (msg: string) => void;
}) {
  const today = new Date().toISOString().slice(0, 10);
  const [decisionDate, setDecisionDate] = useState(today);
  const [biens, setBiens] = useState<JudicialBien[]>([]);
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit(ev: React.FormEvent) {
    ev.preventDefault();
    setSubmitting(true);
    try {
      await adminApi.escalations.decision(escalation.id, {
        decision_date: decisionDate,
        biens_saisissables: biens,
      });
      onDone("Décision enregistrée.");
    } catch (err) {
      const apiErr = err as ApiError;
      onError(apiErr.detail ?? "Enregistrement impossible.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="space-y-3">
      <Field label="Date de la décision judiciaire">
        <input
          type="date"
          value={decisionDate}
          onChange={(e) => setDecisionDate(e.target.value)}
          required
          className={inputCls}
        />
      </Field>
      <Section title="Biens autorisés à la saisie (inventaire)">
        <BienEditor biens={biens} onChange={setBiens} />
      </Section>
      <SubmitBar submitting={submitting} label="Enregistrer la décision" />
    </form>
  );
}


function ExecutionTab({
  escalation,
  onDone,
  onError,
}: {
  escalation: JudicialEscalationRow;
  onDone: (msg: string) => void;
  onError: (msg: string) => void;
}) {
  const today = new Date().toISOString().slice(0, 10);
  const [executionDate, setExecutionDate] = useState(today);
  const [montant, setMontant] = useState<string>(escalation.loan_solde_restant);
  const [biens, setBiens] = useState<JudicialBien[]>(
    escalation.biens_saisissables.length > 0
      ? escalation.biens_saisissables
      : [],
  );
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit(ev: React.FormEvent) {
    ev.preventDefault();
    setSubmitting(true);
    try {
      await adminApi.escalations.execution(escalation.id, {
        execution_date: executionDate,
        montant_recouvre: montant,
        biens_saisis: biens,
      });
      onDone("Exécution enregistrée — crédit mis à jour.");
    } catch (err) {
      const apiErr = err as ApiError;
      onError(apiErr.detail ?? "Enregistrement impossible.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="space-y-3">
      <Field label="Date d'exécution">
        <input
          type="date"
          value={executionDate}
          onChange={(e) => setExecutionDate(e.target.value)}
          required
          className={inputCls}
        />
      </Field>
      <Field
        label="Montant recouvré (FCFA)"
        hint={`Clamp automatique au reliquat (${formatXaf(escalation.loan_solde_restant)}). Si = reliquat, le crédit est clôturé.`}
      >
        <input
          type="number"
          min={0}
          step={1}
          value={montant}
          onChange={(e) => setMontant(e.target.value)}
          required
          className={inputCls}
        />
      </Field>
      <Section title="Biens effectivement saisis">
        <BienEditor biens={biens} onChange={setBiens} />
      </Section>
      <SubmitBar submitting={submitting} label="Enregistrer l'exécution" />
    </form>
  );
}


function ClasserTab({
  escalation,
  onDone,
  onError,
}: {
  escalation: JudicialEscalationRow;
  onDone: (msg: string) => void;
  onError: (msg: string) => void;
}) {
  const [motif, setMotif] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit(ev: React.FormEvent) {
    ev.preventDefault();
    setSubmitting(true);
    try {
      await adminApi.escalations.classer(escalation.id, motif.trim());
      onDone("Escalade classée sans suite.");
    } catch (err) {
      const apiErr = err as ApiError;
      onError(apiErr.detail ?? "Classement impossible.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="space-y-3">
      <p className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-700">
        Action irréversible. Le crédit conserve son solde résiduel (
        <strong>{formatXaf(escalation.loan_solde_restant)}</strong>) que la
        compta devra passer en perte.
      </p>
      <Field label="Motif du classement sans suite">
        <textarea
          value={motif}
          onChange={(e) => setMotif(e.target.value)}
          required
          className={`${inputCls} min-h-[100px]`}
          placeholder="Ex: débiteur introuvable, biens insuffisants…"
        />
      </Field>
      <SubmitBar
        submitting={submitting}
        label="Confirmer le classement"
        disabled={!motif.trim()}
      />
    </form>
  );
}


// ---------------------------------------------------------------------------
// Biens editor (réutilisé décision + exécution)
// ---------------------------------------------------------------------------


function BienEditor({
  biens,
  onChange,
}: {
  biens: JudicialBien[];
  onChange: (b: JudicialBien[]) => void;
}) {
  function add() {
    onChange([...biens, { description: "", valeur_estimee: "" }]);
  }
  function remove(idx: number) {
    onChange(biens.filter((_, i) => i !== idx));
  }
  function update(idx: number, field: keyof JudicialBien, value: string) {
    onChange(biens.map((b, i) => (i === idx ? { ...b, [field]: value } : b)));
  }

  return (
    <div className="space-y-2">
      {biens.map((b, idx) => (
        <div key={idx} className="flex gap-2">
          <input
            value={b.description}
            onChange={(e) => update(idx, "description", e.target.value)}
            placeholder="Description (ex: Mobylette)"
            className={`${inputCls} flex-1`}
          />
          <input
            type="number"
            value={b.valeur_estimee ?? ""}
            onChange={(e) => update(idx, "valeur_estimee", e.target.value)}
            placeholder="Valeur (FCFA)"
            className={`${inputCls} w-36`}
          />
          <button
            type="button"
            onClick={() => remove(idx)}
            className="rounded-md p-2 text-ink-400 hover:bg-red-50 hover:text-red-600"
          >
            <Trash2 className="h-4 w-4" />
          </button>
        </div>
      ))}
      <button
        type="button"
        onClick={add}
        className={buttonClasses({ variant: "ghost", size: "sm" })}
      >
        <Plus className="mr-1 h-3.5 w-3.5" />
        Ajouter un bien
      </button>
    </div>
  );
}


function BienList({ biens }: { biens: JudicialBien[] }) {
  return (
    <ul className="divide-y divide-line-200 rounded-lg border border-line-200 text-sm">
      {biens.map((b, idx) => (
        <li
          key={idx}
          className="flex items-center justify-between px-3 py-2"
        >
          <span className="text-ink-900">{b.description}</span>
          {b.valeur_estimee && (
            <span className="text-ink-500">{formatXaf(b.valeur_estimee)}</span>
          )}
        </li>
      ))}
    </ul>
  );
}


// ---------------------------------------------------------------------------
// Helpers UI
// ---------------------------------------------------------------------------


function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-1.5">
      <p className="text-xs font-semibold uppercase tracking-wider text-ink-500">
        {title}
      </p>
      {children}
    </div>
  );
}

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block space-y-1">
      <span className="text-xs font-medium text-ink-700">{label}</span>
      {children}
      {hint && <span className="block text-[11px] text-ink-500">{hint}</span>}
    </label>
  );
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="font-medium text-ink-500">{label}</p>
      <p className="mt-0.5 text-ink-900">{value}</p>
    </div>
  );
}

function SubmitBar({
  submitting,
  label,
  disabled,
}: {
  submitting: boolean;
  label: string;
  disabled?: boolean;
}) {
  return (
    <div className="flex justify-end pt-1">
      <button
        type="submit"
        disabled={submitting || disabled}
        className={buttonClasses({ variant: "primary", size: "sm" })}
      >
        {submitting ? "En cours…" : label}
      </button>
    </div>
  );
}


const inputCls =
  "block w-full rounded-md border border-line-200 bg-paper px-3 py-2 text-sm text-ink-900 placeholder-ink-400 focus:border-blue-700 focus:outline-none focus:ring-1 focus:ring-blue-700";


function formatXaf(amount: string | number): string {
  const n = typeof amount === "number" ? amount : parseFloat(amount);
  if (Number.isNaN(n)) return String(amount);
  return Math.round(n).toLocaleString("fr-FR") + " XAF";
}

function formatDate(iso: string): string {
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
