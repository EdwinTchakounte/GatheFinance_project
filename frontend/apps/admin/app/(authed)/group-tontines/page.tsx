"use client";

import { useEffect, useState } from "react";
import { Plus, Users, Lock, X, ArrowLeft } from "lucide-react";

import { buttonClasses, SkeletonList } from "@gathe/ui";

import { ConfirmModal } from "@/components/confirm-modal";
import { Modal, ModalField, modalInputClass } from "@/components/modal";
import { PageHeader } from "@/components/page-header";
import {
  adminApi,
  type ApiError,
  type GroupRole,
  type GroupRolePerms,
  type GroupTontineDetail,
  type GroupTontineRow,
  type Member,
} from "@/lib/api";
import { fullName } from "@/lib/name";

const ROLES: Array<{ value: GroupRole; label: string }> = [
  { value: "president", label: "Président" },
  { value: "tresorier", label: "Trésorier" },
  { value: "membre", label: "Membre" },
];

// Catalogue d'actions habilitables pour un rôle personnalisé.
const ROLE_ACTIONS: Array<{ key: keyof GroupRolePerms; label: string }> = [
  { key: "can_manage_funds", label: "Verser (payout)" },
  { key: "can_grant_loan", label: "Accorder un prêt" },
  { key: "can_manage_roster", label: "Gérer le roster / les rôles" },
  { key: "can_record_cotisation", label: "Enregistrer des cotisations" },
  { key: "can_close", label: "Clôturer la réunion" },
];

function fmtXAF(v: string | number | null | undefined): string {
  return `${Math.round(Number(v ?? 0)).toLocaleString("fr-FR")} FCFA`;
}

export default function GroupTontinesPage() {
  const [rows, setRows] = useState<GroupTontineRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [detailId, setDetailId] = useState<number | null>(null);

  async function reload() {
    try {
      setRows(await adminApi.groupTontines.list());
    } catch (e) {
      setError((e as ApiError).detail ?? "Chargement impossible.");
    }
  }
  useEffect(() => {
    reload();
  }, []);

  // Détail d'une réunion : affiché EN PLEINE PAGE (dans la zone de contenu),
  // pas en modale — la réunion occupe tout l'espace avec un bouton « Retour ».
  if (detailId !== null) {
    return (
      <GroupDetailPanel
        id={detailId}
        onBack={() => setDetailId(null)}
        onChanged={reload}
      />
    );
  }

  return (
    <div className="space-y-5">
      <PageHeader
        eyebrow="Épargne & versements"
        title="Tontines de groupe"
        description="Réunions de cotisation (quartier). L'admin crée la réunion, son roster et ses rôles ; le président/trésorier gèrent la cagnotte."
        actions={
          <button
            type="button"
            onClick={() => setCreateOpen(true)}
            className="inline-flex items-center gap-1.5 rounded-md bg-blue-700 px-3 py-2 text-xs font-medium text-white hover:bg-blue-800"
          >
            <Plus className="size-3.5" /> Nouvelle réunion
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
          Aucune réunion. Crée-en une pour commencer.
        </p>
      ) : (
        <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
          {rows.map((g) => (
            <button
              key={g.id}
              type="button"
              onClick={() => setDetailId(g.id)}
              className="rounded-lg border border-line-200 bg-paper p-4 text-left transition-colors hover:border-blue-400"
            >
              <div className="flex items-start justify-between">
                <p className="font-semibold text-ink-900">{g.nom}</p>
                {!g.is_open ? (
                  <span className="rounded bg-ink-100 px-1.5 py-0.5 text-[10px] text-ink-500">
                    clôturée
                  </span>
                ) : null}
              </div>
              <p className="mt-2 text-lg font-semibold tabular-nums text-emerald">
                {fmtXAF(g.solde)}
              </p>
              <p className="mt-1 flex items-center gap-1 text-xs text-ink-500">
                <Users className="size-3.5" /> {g.members_count} membre(s)
              </p>
            </button>
          ))}
        </div>
      )}

      <CreateGroupModal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        onCreated={() => {
          setCreateOpen(false);
          reload();
        }}
      />
    </div>
  );
}

// ── Recherche membre réutilisable ─────────────────────────────────────────────
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
        const res = await adminApi.members.list({ q: s, limit: 8 });
        setResults(res.results);
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

type RosterEntry = { member: Member; role: GroupRole };

function CreateGroupModal({
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
  const [cotisation, setCotisation] = useState("");
  const [roster, setRoster] = useState<RosterEntry[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (open) {
      setNom("");
      setDescription("");
      setCotisation("");
      setRoster([]);
      setError(null);
    }
  }, [open]);

  function addMember(m: Member) {
    if (roster.some((r) => r.member.id === m.id)) return;
    setRoster((prev) => [...prev, { member: m, role: "membre" }]);
  }
  function setRole(id: number, role: GroupRole) {
    setRoster((prev) => prev.map((r) => (r.member.id === id ? { ...r, role } : r)));
  }
  function remove(id: number) {
    setRoster((prev) => prev.filter((r) => r.member.id !== id));
  }

  async function submit() {
    setError(null);
    if (!nom.trim()) {
      setError("Le nom de la réunion est requis.");
      return;
    }
    if (roster.length === 0) {
      setError("Ajoute au moins un membre au roster.");
      return;
    }
    setBusy(true);
    try {
      await adminApi.groupTontines.create({
        nom: nom.trim(),
        description: description.trim() || undefined,
        montant_cotisation: cotisation ? Number(cotisation) : undefined,
        roster: roster.map((r) => ({ member_id: r.member.id, role: r.role })),
      });
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
      title="Nouvelle réunion"
      description="Définis le nom, la cotisation suggérée et le roster (avec un président et un trésorier)."
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
            {busy ? "Création…" : "Créer la réunion"}
          </button>
        </>
      }
    >
      <div className="space-y-3">
        <ModalField label="Nom de la réunion">
          <input value={nom} onChange={(e) => setNom(e.target.value)} className={modalInputClass} placeholder="Ex. Réunion Bonapriso" />
        </ModalField>
        <ModalField label="Cotisation suggérée (FCFA, optionnel)">
          <input type="number" min={0} value={cotisation} onChange={(e) => setCotisation(e.target.value)} className={modalInputClass} placeholder="0" />
        </ModalField>
        <ModalField label="Informations (optionnel)">
          <textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={2} className={modalInputClass} />
        </ModalField>

        <ModalField label="Ajouter des membres">
          <MemberSearch onPick={addMember} />
        </ModalField>

        {roster.length > 0 ? (
          <ul className="space-y-1.5">
            {roster.map((r) => (
              <li key={r.member.id} className="flex items-center gap-2 rounded-md border border-line-200 px-2.5 py-1.5">
                <span className="flex-1 text-sm text-ink-800">
                  {fullName(r.member.prenom, r.member.nom)}
                </span>
                <select
                  value={r.role}
                  onChange={(e) => setRole(r.member.id, e.target.value as GroupRole)}
                  className="rounded border border-line-300 px-1.5 py-1 text-xs"
                >
                  {ROLES.map((ro) => (
                    <option key={ro.value} value={ro.value}>{ro.label}</option>
                  ))}
                </select>
                <button type="button" onClick={() => remove(r.member.id)} className="text-ink-400 hover:text-terra-600">
                  <X className="size-4" />
                </button>
              </li>
            ))}
          </ul>
        ) : null}

        {error ? <p className="rounded-md bg-terra-50 px-3 py-2 text-sm text-terra-700">{error}</p> : null}
      </div>
    </Modal>
  );
}

function GroupDetailPanel({
  id,
  onBack,
  onChanged,
}: {
  id: number;
  onBack: () => void;
  onChanged: () => void;
}) {
  const [g, setG] = useState<GroupTontineDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [confirmClose, setConfirmClose] = useState(false);
  // Rôle personnalisé en cours de création (nom + actions cochées).
  const [newRoleName, setNewRoleName] = useState("");
  const [newRolePerms, setNewRolePerms] = useState<GroupRolePerms>({
    can_manage_funds: false,
    can_grant_loan: false,
    can_manage_roster: false,
    can_record_cotisation: false,
    can_close: false,
  });

  async function load() {
    try {
      setG(await adminApi.groupTontines.detail(id));
    } catch (e) {
      setError((e as ApiError).detail ?? "Détail indisponible.");
    }
  }
  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  async function setRole(memberId: number, role: GroupRole) {
    try {
      setG(await adminApi.groupTontines.setRole(id, memberId, role));
      onChanged();
    } catch (e) {
      setError((e as ApiError).detail ?? "Changement de rôle impossible.");
    }
  }
  async function removeMember(memberId: number) {
    try {
      setG(await adminApi.groupTontines.removeMember(id, memberId));
      onChanged();
    } catch (e) {
      setError((e as ApiError).detail ?? "Retrait impossible.");
    }
  }
  async function addMember(m: Member) {
    try {
      setG(await adminApi.groupTontines.addMember(id, m.id, "membre"));
      onChanged();
    } catch (e) {
      setError((e as ApiError).detail ?? "Ajout impossible.");
    }
  }
  async function doClose() {
    try {
      await adminApi.groupTontines.close(id);
      setConfirmClose(false);
      await load();
      onChanged();
    } catch (e) {
      setError((e as ApiError).detail ?? "Clôture impossible.");
    }
  }
  async function createRole() {
    if (!newRoleName.trim()) return;
    try {
      setG(await adminApi.groupTontines.createRole(id, newRoleName.trim(), newRolePerms));
      setNewRoleName("");
      setNewRolePerms({
        can_manage_funds: false,
        can_grant_loan: false,
        can_manage_roster: false,
        can_record_cotisation: false,
        can_close: false,
      });
      onChanged();
    } catch (e) {
      setError((e as ApiError).detail ?? "Création du rôle impossible.");
    }
  }
  async function deleteRole(roleId: number) {
    try {
      setG(await adminApi.groupTontines.deleteRole(id, roleId));
      onChanged();
    } catch (e) {
      setError((e as ApiError).detail ?? "Suppression impossible.");
    }
  }
  async function assignCustomRole(memberId: number, roleId: number | null) {
    try {
      setG(await adminApi.groupTontines.assignRole(id, memberId, roleId));
      onChanged();
    } catch (e) {
      setError((e as ApiError).detail ?? "Attribution impossible.");
    }
  }

  return (
    <div className="space-y-5">
      {/* En-tête pleine page : retour + nom + cagnotte (pas de modale). */}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={onBack}
            className="inline-flex items-center gap-1.5 rounded-md border border-line-200 px-2.5 py-1.5 text-xs font-medium text-ink-600 hover:border-blue-400 hover:text-blue-700"
          >
            <ArrowLeft className="size-3.5" /> Retour
          </button>
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-wider text-emerald">
              Tontine de groupe
            </p>
            <h1 className="font-display text-2xl font-semibold text-ink-900">
              {g?.nom ?? "Réunion"}
            </h1>
          </div>
        </div>
        {g ? (
          <div className="text-right">
            <p className="text-[11px] font-semibold uppercase tracking-wider text-ink-500">
              Cagnotte
            </p>
            <p className="text-2xl font-semibold tabular-nums text-emerald">
              {fmtXAF(g.solde)}
            </p>
            {!g.is_open ? (
              <span className="mt-0.5 inline-block rounded bg-ink-100 px-1.5 py-0.5 text-[10px] text-ink-500">
                clôturée
              </span>
            ) : null}
          </div>
        ) : null}
      </div>

      {error ? <p className="rounded-md bg-terra-50 px-3 py-2 text-sm text-terra-700">{error}</p> : null}
      {g === null ? (
        <p className="text-sm text-ink-500">Chargement…</p>
      ) : (
        <div className="grid gap-5 lg:grid-cols-3">
          {/* Colonne principale : membres + rôles */}
          <div className="space-y-5 lg:col-span-2">
          {/* Membres + rôles */}
          <div className="rounded-lg border border-line-200 bg-paper p-4">
            <p className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-ink-500">
              Membres ({g.members.length})
            </p>
            <ul className="space-y-1.5">
              {g.members.map((mem) => (
                <li key={mem.id} className="flex items-center gap-2 rounded-md border border-line-200 px-2.5 py-1.5">
                  <span className="flex-1 text-sm text-ink-800">
                    {fullName(mem.prenom, mem.nom)}
                    <span className="ml-1 font-mono text-[10px] text-ink-400">{mem.numero_membre}</span>
                  </span>
                  {g.is_open ? (
                    <>
                      <select
                        value={mem.role}
                        onChange={(e) => setRole(mem.member_id, e.target.value as GroupRole)}
                        className="rounded border border-line-300 px-1.5 py-1 text-xs"
                      >
                        {ROLES.map((ro) => (
                          <option key={ro.value} value={ro.value}>{ro.label}</option>
                        ))}
                      </select>
                      {g.custom_roles.length > 0 ? (
                        <select
                          value={mem.custom_role_id ?? ""}
                          onChange={(e) =>
                            assignCustomRole(
                              mem.member_id,
                              e.target.value ? Number(e.target.value) : null,
                            )
                          }
                          title="Rôle personnalisé (actions supplémentaires)"
                          className="rounded border border-line-300 px-1.5 py-1 text-xs"
                        >
                          <option value="">— Rôle custom —</option>
                          {g.custom_roles.map((r) => (
                            <option key={r.id} value={r.id}>{r.nom}</option>
                          ))}
                        </select>
                      ) : null}
                      <button type="button" onClick={() => removeMember(mem.member_id)} className="text-ink-400 hover:text-terra-600">
                        <X className="size-4" />
                      </button>
                    </>
                  ) : (
                    <span className="text-xs text-ink-500">
                      {mem.role_display}
                      {mem.custom_role_nom ? ` · ${mem.custom_role_nom}` : ""}
                    </span>
                  )}
                </li>
              ))}
            </ul>
            {g.is_open ? (
              <div className="mt-2">
                <MemberSearch onPick={addMember} />
              </div>
            ) : null}
          </div>

          {/* Rôles personnalisés (actions rattachées, propres à la réunion) */}
          <div className="rounded-lg border border-line-200 bg-paper p-4">
            <p className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-ink-500">
              Rôles personnalisés
            </p>
            {g.custom_roles.length > 0 ? (
              <ul className="mb-2 space-y-1.5">
                {g.custom_roles.map((r) => (
                  <li
                    key={r.id}
                    className="flex items-start gap-2 rounded-md border border-line-200 px-2.5 py-1.5"
                  >
                    <div className="flex-1">
                      <p className="text-sm font-medium text-ink-800">{r.nom}</p>
                      <div className="mt-0.5 flex flex-wrap gap-1">
                        {ROLE_ACTIONS.filter((a) => r[a.key]).map((a) => (
                          <span
                            key={a.key}
                            className="rounded bg-blue-50 px-1.5 py-0.5 text-[10px] font-medium text-blue-700"
                          >
                            {a.label}
                          </span>
                        ))}
                        {ROLE_ACTIONS.every((a) => !r[a.key]) ? (
                          <span className="text-[10px] text-ink-400">Aucune action</span>
                        ) : null}
                      </div>
                    </div>
                    {g.is_open ? (
                      <button
                        type="button"
                        onClick={() => deleteRole(r.id)}
                        className="text-ink-400 hover:text-terra-600"
                        title="Supprimer ce rôle"
                      >
                        <X className="size-4" />
                      </button>
                    ) : null}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="mb-2 text-xs text-ink-400">
                Aucun rôle personnalisé. Créez-en un (ex. « Secrétaire ») avec ses
                actions.
              </p>
            )}
            {g.is_open ? (
              <div className="rounded-md border border-dashed border-line-300 p-2.5">
                <input
                  value={newRoleName}
                  onChange={(e) => setNewRoleName(e.target.value)}
                  placeholder="Nom du rôle (ex. Secrétaire)"
                  className="mb-2 w-full rounded border border-line-300 px-2 py-1.5 text-sm"
                />
                <div className="mb-2 grid grid-cols-1 gap-1 sm:grid-cols-2">
                  {ROLE_ACTIONS.map((a) => (
                    <label
                      key={a.key}
                      className="flex items-center gap-1.5 text-xs text-ink-700"
                    >
                      <input
                        type="checkbox"
                        checked={newRolePerms[a.key]}
                        onChange={(e) =>
                          setNewRolePerms((p) => ({ ...p, [a.key]: e.target.checked }))
                        }
                      />
                      {a.label}
                    </label>
                  ))}
                </div>
                <button
                  type="button"
                  onClick={createRole}
                  disabled={!newRoleName.trim()}
                  className="inline-flex items-center gap-1.5 rounded-md bg-blue-700 px-3 py-1.5 text-xs font-medium text-white hover:bg-blue-800 disabled:opacity-40"
                >
                  <Plus className="size-3.5" /> Créer le rôle
                </button>
              </div>
            ) : null}
          </div>

          </div>

          {/* Colonne latérale : prêts + mouvements + clôture */}
          <div className="space-y-5">
          {/* Prêts en cours */}
          {g.loans.length > 0 ? (
            <div className="rounded-lg border border-line-200 bg-paper p-4">
              <p className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-ink-500">Prêts</p>
              <ul className="space-y-1">
                {g.loans.map((l) => (
                  <li key={l.id} className="flex justify-between gap-2 rounded-md border border-line-200 px-2.5 py-1.5 text-xs">
                    <span>
                      {fullName(l.prenom, l.nom)}
                      {l.avaliste_display ? (
                        <span className="ml-1 text-ink-400">
                          · avaliste : {l.avaliste_display}
                        </span>
                      ) : null}
                    </span>
                    <span className="whitespace-nowrap tabular-nums">
                      reste {fmtXAF(l.solde_restant)} / {fmtXAF(l.montant)} · {l.statut_display}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}

          {/* Mouvements */}
          <div className="rounded-lg border border-line-200 bg-paper p-4">
            <p className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-ink-500">
              Mouvements ({g.transactions.length})
            </p>
            {g.transactions.length === 0 ? (
              <p className="text-sm text-ink-500">Aucun mouvement.</p>
            ) : (
              <ul className="max-h-80 space-y-1 overflow-y-auto">
                {g.transactions.map((t) => (
                  <li key={t.id} className="flex justify-between rounded-md border border-line-200 px-2.5 py-1.5 text-xs">
                    <span>
                      {t.type_op_display}
                      {t.member_nom ? ` · ${t.member_prenom} ${t.member_nom}` : ""}
                      {t.acted_by_name ? (
                        <span className="ml-1 text-ink-400">par {t.acted_by_name}</span>
                      ) : null}
                    </span>
                    <span className="tabular-nums text-ink-600">
                      {fmtXAF(t.montant)} → {fmtXAF(t.solde_apres)}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>

          {g.is_open ? (
            <button
              type="button"
              onClick={() => setConfirmClose(true)}
              className="inline-flex w-full items-center justify-center gap-2 rounded-md border border-line-300 px-3 py-2 text-sm font-medium text-ink-700 hover:border-terra-400 hover:text-terra-700"
            >
              <Lock className="size-4" /> Clôturer la réunion
            </button>
          ) : null}
          </div>
        </div>
      )}

      <ConfirmModal
        open={confirmClose}
        onClose={() => setConfirmClose(false)}
        onConfirm={doClose}
        title="Clôturer cette réunion ?"
        tone="danger"
        confirmLabel="Clôturer"
        message={<p>La réunion sera gelée : plus aucun mouvement de cagnotte possible.</p>}
      />
    </div>
  );
}
