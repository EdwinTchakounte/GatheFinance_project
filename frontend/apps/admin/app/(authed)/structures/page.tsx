"use client";

import { useEffect, useState } from "react";
import { Plus, Users, Lock, X, Wallet, HandCoins } from "lucide-react";

import { buttonClasses, SkeletonList } from "@gathe/ui";

import { ConfirmModal } from "@/components/confirm-modal";
import { Modal, ModalField, modalInputClass } from "@/components/modal";
import { PageHeader } from "@/components/page-header";
import {
  adminApi,
  type ApiError,
  type Member,
  type StructureDetail,
  type StructureEmployeeRow,
  type StructureRow,
} from "@/lib/api";
import { fullName } from "@/lib/name";

function fmtXAF(v: string | number | null | undefined): string {
  return `${Math.round(Number(v ?? 0)).toLocaleString("fr-FR")} FCFA`;
}

export default function StructuresPage() {
  const [rows, setRows] = useState<StructureRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [detailId, setDetailId] = useState<number | null>(null);

  async function reload() {
    try {
      setRows(await adminApi.structures.list());
    } catch (e) {
      setError((e as ApiError).detail ?? "Chargement impossible.");
    }
  }
  useEffect(() => {
    reload();
  }, []);

  return (
    <div className="space-y-5">
      <PageHeader
        eyebrow="Épargne & versements"
        title="Structures & paie"
        description="Payez les salaires des employés (membres) via la coopérative : approvisionnez la cagnotte de la structure, puis versez les paies dans leur épargne libre."
        actions={
          <button
            type="button"
            onClick={() => setCreateOpen(true)}
            className="inline-flex items-center gap-1.5 rounded-md bg-blue-700 px-3 py-2 text-xs font-medium text-white hover:bg-blue-800"
          >
            <Plus className="size-3.5" /> Nouvelle structure
          </button>
        }
      />

      {error ? (
        <div className="rounded-md bg-terra-50 px-4 py-2.5 text-sm text-terra-700">{error}</div>
      ) : null}

      {rows === null ? (
        <SkeletonList count={4} />
      ) : rows.length === 0 ? (
        <p className="rounded-md border border-line-200 bg-paper-soft/40 px-4 py-6 text-center text-sm text-ink-500">
          Aucune structure. Crée-en une pour commencer.
        </p>
      ) : (
        <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
          {rows.map((s) => (
            <button
              key={s.id}
              type="button"
              onClick={() => setDetailId(s.id)}
              className="rounded-lg border border-line-200 bg-paper p-4 text-left transition-colors hover:border-blue-400"
            >
              <div className="flex items-start justify-between">
                <p className="font-semibold text-ink-900">{s.nom}</p>
                {!s.is_active ? (
                  <span className="rounded bg-ink-100 px-1.5 py-0.5 text-[10px] text-ink-500">
                    clôturée
                  </span>
                ) : null}
              </div>
              <p className="mt-2 text-lg font-semibold tabular-nums text-emerald">
                {fmtXAF(s.solde)}
              </p>
              <p className="text-[11px] text-ink-500">cagnotte</p>
              <p className="mt-2 flex items-center gap-1 text-xs text-ink-500">
                <Users className="size-3.5" /> {s.employees_count} employé(s) · masse{" "}
                {fmtXAF(s.masse_salariale)}
              </p>
            </button>
          ))}
        </div>
      )}

      <CreateStructureModal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        onCreated={() => {
          setCreateOpen(false);
          reload();
        }}
      />

      {detailId !== null ? (
        <StructureDetailModal id={detailId} onClose={() => setDetailId(null)} onChanged={reload} />
      ) : null}
    </div>
  );
}

function MemberSearch({ onPick }: { onPick: (m: Member) => void }) {
  const [q, setQ] = useState("");
  const [results, setResults] = useState<Member[]>([]);
  useEffect(() => {
    const s = q.trim();
    if (s.length < 2) {
      setResults([]);
      return;
    }
    const h = setTimeout(async () => {
      try {
        setResults((await adminApi.members.list({ q: s, limit: 8 })).results);
      } catch {
        setResults([]);
      }
    }, 250);
    return () => clearTimeout(h);
  }, [q]);
  return (
    <div>
      <input
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder="Rechercher un membre (nom, n°)…"
        className={modalInputClass}
      />
      {results.length > 0 ? (
        <ul className="mt-1 max-h-40 overflow-y-auto rounded-md border border-line-200">
          {results.map((m) => (
            <li key={m.id}>
              <button
                type="button"
                onClick={() => {
                  onPick(m);
                  setQ("");
                  setResults([]);
                }}
                className="block w-full px-3 py-1.5 text-left text-xs hover:bg-line-100"
              >
                {fullName(m.prenom, m.nom)}{" "}
                <span className="font-mono text-ink-400">{m.numero_membre}</span>
              </button>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

function CreateStructureModal({
  open,
  onClose,
  onCreated,
}: {
  open: boolean;
  onClose: () => void;
  onCreated: () => void;
}) {
  const [nom, setNom] = useState("");
  const [description, setDescription] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (open) {
      setNom("");
      setDescription("");
      setError(null);
    }
  }, [open]);

  async function submit() {
    if (!nom.trim()) {
      setError("Le nom de la structure est requis.");
      return;
    }
    setBusy(true);
    try {
      await adminApi.structures.create({ nom: nom.trim(), description: description.trim() || undefined });
      onCreated();
    } catch (e) {
      setError((e as ApiError).detail ?? "Création impossible.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Nouvelle structure"
      description="L'employeur qui paie ses salariés via la coopérative."
      footer={
        <>
          <button type="button" className={buttonClasses({ variant: "ghost" })} onClick={onClose}>
            Annuler
          </button>
          <button
            type="button"
            className={buttonClasses({ variant: "primary" })}
            onClick={submit}
            disabled={busy}
          >
            {busy ? "Création…" : "Créer"}
          </button>
        </>
      }
    >
      <div className="space-y-3">
        <ModalField label="Nom de la structure">
          <input value={nom} onChange={(e) => setNom(e.target.value)} className={modalInputClass} placeholder="Ex. Boulangerie du Coin" />
        </ModalField>
        <ModalField label="Informations (optionnel)">
          <textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={2} className={modalInputClass} />
        </ModalField>
        {error ? <p className="rounded-md bg-terra-50 px-3 py-2 text-sm text-terra-700">{error}</p> : null}
      </div>
    </Modal>
  );
}

function StructureDetailModal({
  id,
  onClose,
  onChanged,
}: {
  id: number;
  onClose: () => void;
  onChanged: () => void;
}) {
  const [s, setS] = useState<StructureDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [flash, setFlash] = useState<string | null>(null);
  const [confirmClose, setConfirmClose] = useState(false);

  async function load() {
    try {
      setS(await adminApi.structures.detail(id));
    } catch (e) {
      setError((e as ApiError).detail ?? "Détail indisponible.");
    }
  }
  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  async function run(fn: () => Promise<StructureDetail>, ok?: string) {
    setError(null);
    try {
      setS(await fn());
      if (ok) setFlash(ok);
      onChanged();
    } catch (e) {
      setError((e as ApiError).detail ?? "Opération impossible.");
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      title={s?.nom ?? "Structure"}
      description={s ? `Cagnotte : ${fmtXAF(s.solde)}` : undefined}
    >
      {error ? <p className="mb-3 rounded-md bg-terra-50 px-3 py-2 text-sm text-terra-700">{error}</p> : null}
      {flash ? <p className="mb-3 rounded-md bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{flash}</p> : null}
      {s === null ? (
        <p className="text-sm text-ink-500">Chargement…</p>
      ) : (
        <div className="space-y-4">
          {/* Cagnotte */}
          <div className="rounded-md border border-line-200 bg-paper-soft/40 p-3">
            <p className="text-xs text-ink-500">Cagnotte de la structure</p>
            <p className="text-xl font-semibold tabular-nums text-emerald">{fmtXAF(s.solde)}</p>
            {s.is_active ? (
              <CagnotteBar
                onFund={(m) => run(() => adminApi.structures.fund(id, m), "Cagnotte approvisionnée.")}
                onWithdraw={(m) => run(() => adminApi.structures.withdraw(id, m), "Retrait effectué.")}
              />
            ) : null}
          </div>

          {/* Verser les paies (lot) */}
          {s.is_active && s.employees.length > 0 ? (
            <PayrollBar
              onRun={(periode) =>
                run(() => adminApi.structures.runPayroll(id, periode), "Paies versées.")
              }
              masse={s.masse_salariale}
            />
          ) : null}

          {/* Employés */}
          <div>
            <p className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-ink-500">
              Employés ({s.employees.length}) · masse salariale {fmtXAF(s.masse_salariale)}
            </p>
            <ul className="space-y-1.5">
              {s.employees.map((emp) => (
                <EmployeeRow
                  key={emp.id}
                  emp={emp}
                  active={s.is_active}
                  onUpdate={(payload) =>
                    run(() => adminApi.structures.updateEmployee(id, emp.id, payload))
                  }
                  onRemove={() =>
                    run(() => adminApi.structures.removeEmployee(id, emp.id), "Employé retiré.")
                  }
                  onPay={() =>
                    run(() => adminApi.structures.payEmployee(id, emp.id), "Paie versée.")
                  }
                />
              ))}
            </ul>
            {s.is_active ? (
              <div className="mt-2">
                <AddEmployee
                  onAdd={(payload) =>
                    run(() => adminApi.structures.addEmployee(id, payload), "Employé ajouté.")
                  }
                />
              </div>
            ) : null}
          </div>

          {/* Historique lots + mouvements */}
          {s.payroll_runs.length > 0 ? (
            <div>
              <p className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-ink-500">Lots de paie</p>
              <ul className="space-y-1">
                {s.payroll_runs.map((r) => (
                  <li key={r.id} className="flex items-center justify-between gap-2 rounded-md border border-line-200 px-2.5 py-1.5 text-xs">
                    <span>{r.periode}</span>
                    <span className="flex items-center gap-3">
                      <span className="tabular-nums">{fmtXAF(r.total_verse)} · {r.employes_count} employé(s)</span>
                      <a
                        href={adminApi.structures.payrollPdfUrl(id, r.id)}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="font-medium text-blue-700 hover:underline"
                      >
                        📄 État de paie
                      </a>
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}

          {s.is_active ? (
            <button
              type="button"
              onClick={() => setConfirmClose(true)}
              className="inline-flex w-full items-center justify-center gap-2 rounded-md border border-line-300 px-3 py-2 text-sm font-medium text-ink-700 hover:border-terra-400 hover:text-terra-700"
            >
              <Lock className="size-4" /> Clôturer la structure
            </button>
          ) : null}
        </div>
      )}

      <ConfirmModal
        open={confirmClose}
        onClose={() => setConfirmClose(false)}
        onConfirm={async () => {
          await run(() => adminApi.structures.close(id));
          setConfirmClose(false);
        }}
        title="Clôturer cette structure ?"
        tone="danger"
        confirmLabel="Clôturer"
        message={<p>Plus aucun mouvement (paie, approvisionnement) ne sera possible.</p>}
      />
    </Modal>
  );
}

function CagnotteBar({
  onFund,
  onWithdraw,
}: {
  onFund: (montant: number) => void;
  onWithdraw: (montant: number) => void;
}) {
  const [montant, setMontant] = useState("");
  const val = () => Number(montant.replace(/\D/g, ""));
  return (
    <div className="mt-2 flex items-center gap-2">
      <input
        type="number"
        min={1}
        value={montant}
        onChange={(e) => setMontant(e.target.value)}
        placeholder="Montant (FCFA)"
        className="w-40 rounded border border-line-300 px-2 py-1 text-xs"
      />
      <button
        type="button"
        disabled={val() <= 0}
        onClick={() => {
          if (val() > 0) {
            onFund(val());
            setMontant("");
          }
        }}
        className="inline-flex items-center gap-1 rounded-md border border-emerald/40 bg-emerald/10 px-2.5 py-1.5 text-xs font-semibold text-emerald hover:bg-emerald/20 disabled:opacity-50"
      >
        <Wallet className="size-3.5" /> Approvisionner
      </button>
      <button
        type="button"
        disabled={val() <= 0}
        onClick={() => {
          if (val() > 0) {
            onWithdraw(val());
            setMontant("");
          }
        }}
        className="inline-flex items-center gap-1 rounded-md border border-line-300 px-2.5 py-1.5 text-xs font-medium text-ink-700 hover:border-terra-400 disabled:opacity-50"
      >
        Retirer
      </button>
    </div>
  );
}

function PayrollBar({ onRun, masse }: { onRun: (periode: string) => void; masse: string }) {
  const [periode, setPeriode] = useState("");
  return (
    <div className="flex items-center gap-2 rounded-md border border-blue-200 bg-blue-50/50 p-2.5">
      <HandCoins className="size-4 text-blue-700" />
      <input
        value={periode}
        onChange={(e) => setPeriode(e.target.value)}
        placeholder="Période (ex. Août 2026)"
        className="flex-1 rounded border border-line-300 px-2 py-1 text-xs"
      />
      <button
        type="button"
        onClick={() => onRun(periode || "Paie")}
        className="rounded-md bg-blue-700 px-3 py-1.5 text-xs font-semibold text-white hover:bg-blue-800"
      >
        Verser les paies ({fmtXAF(masse)})
      </button>
    </div>
  );
}

function EmployeeRow({
  emp,
  active,
  onUpdate,
  onRemove,
  onPay,
}: {
  emp: StructureEmployeeRow;
  active: boolean;
  onUpdate: (p: { poste?: string; montant_paie?: number }) => void;
  onRemove: () => void;
  onPay: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const [poste, setPoste] = useState(emp.poste);
  const [montant, setMontant] = useState(String(Number(emp.montant_paie)));

  return (
    <li className="rounded-md border border-line-200 px-2.5 py-2">
      <div className="flex items-center gap-2">
        <div className="flex-1">
          <p className="text-sm font-medium text-ink-900">
            {emp.prenom} {emp.nom}{" "}
            <span className="font-mono text-[10px] text-ink-400">{emp.numero_membre}</span>
          </p>
          {!editing ? (
            <p className="text-xs text-ink-500">
              {emp.poste || "—"} · <span className="tabular-nums">{fmtXAF(emp.montant_paie)}</span>/mois
            </p>
          ) : null}
        </div>
        {active ? (
          editing ? (
            <button
              type="button"
              onClick={() => {
                onUpdate({ poste, montant_paie: Number(montant.replace(/\D/g, "")) });
                setEditing(false);
              }}
              className="rounded-md bg-blue-700 px-2 py-1 text-[11px] font-semibold text-white"
            >
              OK
            </button>
          ) : (
            <>
              <button
                type="button"
                onClick={onPay}
                title="Verser sa paie maintenant"
                className="rounded-md border border-emerald/40 bg-emerald/10 px-2 py-1 text-[11px] font-semibold text-emerald hover:bg-emerald/20"
              >
                Payer
              </button>
              <button
                type="button"
                onClick={() => setEditing(true)}
                className="rounded-md border border-line-300 px-2 py-1 text-[11px] text-ink-700 hover:border-blue-400"
              >
                Modifier
              </button>
              <button type="button" onClick={onRemove} className="text-ink-400 hover:text-terra-600">
                <X className="size-4" />
              </button>
            </>
          )
        ) : null}
      </div>
      {editing ? (
        <div className="mt-2 grid grid-cols-2 gap-2">
          <input
            value={poste}
            onChange={(e) => setPoste(e.target.value)}
            placeholder="Poste"
            className="rounded border border-line-300 px-2 py-1 text-xs"
          />
          <input
            type="number"
            value={montant}
            onChange={(e) => setMontant(e.target.value)}
            placeholder="Montant paie"
            className="rounded border border-line-300 px-2 py-1 text-xs"
          />
        </div>
      ) : null}
    </li>
  );
}

function AddEmployee({
  onAdd,
}: {
  onAdd: (p: { member_id: number; poste?: string; montant_paie?: number }) => void;
}) {
  const [picked, setPicked] = useState<Member | null>(null);
  const [poste, setPoste] = useState("");
  const [montant, setMontant] = useState("");

  if (!picked) {
    return (
      <div>
        <p className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-ink-400">
          Ajouter un employé
        </p>
        <MemberSearch onPick={setPicked} />
      </div>
    );
  }
  return (
    <div className="space-y-2 rounded-md border border-line-200 p-2.5">
      <p className="text-sm text-ink-800">{fullName(picked.prenom, picked.nom)}</p>
      <div className="grid grid-cols-2 gap-2">
        <input value={poste} onChange={(e) => setPoste(e.target.value)} placeholder="Poste" className="rounded border border-line-300 px-2 py-1 text-xs" />
        <input type="number" value={montant} onChange={(e) => setMontant(e.target.value)} placeholder="Montant paie (FCFA)" className="rounded border border-line-300 px-2 py-1 text-xs" />
      </div>
      <div className="flex gap-2">
        <button
          type="button"
          onClick={() => {
            onAdd({
              member_id: picked.id,
              poste: poste || undefined,
              montant_paie: montant ? Number(montant.replace(/\D/g, "")) : undefined,
            });
            setPicked(null);
            setPoste("");
            setMontant("");
          }}
          className="rounded-md bg-blue-700 px-3 py-1.5 text-xs font-semibold text-white"
        >
          Ajouter
        </button>
        <button type="button" onClick={() => setPicked(null)} className="text-xs text-ink-500">
          Annuler
        </button>
      </div>
    </div>
  );
}
