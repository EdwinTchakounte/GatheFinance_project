"use client";

import { useEffect, useMemo, useState } from "react";
import { Check, Copy, Pencil, Plus, Trash2, UserX } from "lucide-react";

import { Modal, ModalField, modalInputClass, buttonClasses } from "@/components/modal";
import {
  adminApi,
  type AccessResource,
  type ApiError,
  type StaffRole,
  type StaffUser,
} from "@/lib/api";


type Tab = "users" | "roles";

export default function AccessPage() {
  return <Inner />;
}

function Inner() {
  const [tab, setTab] = useState<Tab>("users");
  const [resources, setResources] = useState<AccessResource[]>([]);
  const [roles, setRoles] = useState<StaffRole[]>([]);
  const [users, setUsers] = useState<StaffUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [editUser, setEditUser] = useState<StaffUser | null | "new">(null);
  const [editRole, setEditRole] = useState<StaffRole | null | "new">(null);

  async function reload() {
    setLoading(true);
    setError(null);
    try {
      const [res, rl, us] = await Promise.all([
        adminApi.access.resources(),
        adminApi.access.listRoles(),
        adminApi.access.listUsers(),
      ]);
      setResources(res.results);
      setRoles(rl.results);
      setUsers(us.results);
    } catch (err) {
      setError((err as ApiError).detail ?? "Chargement impossible.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    reload();
  }, []);

  const roleName = useMemo(
    () => Object.fromEntries(roles.map((r) => [r.id, r.name])),
    [roles],
  );

  return (
    <div className="px-8 py-8 lg:px-12 lg:py-10">
      <header className="mb-6">
        <p className="font-display text-[0.7rem] font-semibold uppercase tracking-[0.18em] text-terra-600">
          Administration
        </p>
        <h1 className="mt-2 font-editorial text-3xl font-medium text-ink-900">
          Utilisateurs &amp; accès
        </h1>
        <p className="mt-1 text-sm text-ink-600">
          Crée des comptes staff et attribue-leur des rôles. Un rôle = un
          ensemble d&apos;onglets autorisés (ressources).
        </p>
      </header>

      {error ? (
        <div className="mb-5 rounded-md border border-terra-400/40 bg-terra-50/60 px-4 py-2.5 text-sm text-terra-700">
          {error}
        </div>
      ) : null}

      {/* Onglets */}
      <div className="mb-5 flex items-center gap-1 rounded-md border border-line-200 bg-paper p-1">
        {(
          [
            ["users", `Utilisateurs (${users.length})`],
            ["roles", `Rôles (${roles.length})`],
          ] as [Tab, string][]
        ).map(([key, label]) => (
          <button
            key={key}
            type="button"
            onClick={() => setTab(key)}
            className={[
              "rounded px-3 py-1.5 text-sm font-medium transition-colors",
              tab === key ? "bg-blue-700 text-white" : "text-ink-700 hover:text-blue-700",
            ].join(" ")}
          >
            {label}
          </button>
        ))}
        <div className="ml-auto">
          {tab === "users" ? (
            <button
              type="button"
              onClick={() => setEditUser("new")}
              className={buttonClasses({ variant: "primary", size: "sm" })}
            >
              <Plus className="mr-1 inline size-4" />
              Nouvel utilisateur
            </button>
          ) : (
            <button
              type="button"
              onClick={() => setEditRole("new")}
              className={buttonClasses({ variant: "primary", size: "sm" })}
            >
              <Plus className="mr-1 inline size-4" />
              Nouveau rôle
            </button>
          )}
        </div>
      </div>

      {loading ? (
        <p className="text-ink-600">Chargement…</p>
      ) : tab === "users" ? (
        <UsersTable
          users={users}
          roleName={roleName}
          onEdit={(u) => setEditUser(u)}
        />
      ) : (
        <RolesTable
          roles={roles}
          resources={resources}
          onEdit={(r) => setEditRole(r)}
          onDeleted={reload}
        />
      )}

      {editUser !== null ? (
        <UserModal
          user={editUser === "new" ? null : editUser}
          roles={roles}
          onClose={() => setEditUser(null)}
          onSaved={() => {
            setEditUser(null);
            reload();
          }}
        />
      ) : null}

      {editRole !== null ? (
        <RoleModal
          role={editRole === "new" ? null : editRole}
          resources={resources}
          onClose={() => setEditRole(null)}
          onSaved={() => {
            setEditRole(null);
            reload();
          }}
        />
      ) : null}
    </div>
  );
}


// ── Tables ─────────────────────────────────────────────────────────────────
function UsersTable({
  users,
  roleName,
  onEdit,
}: {
  users: StaffUser[];
  roleName: Record<number, string>;
  onEdit: (u: StaffUser) => void;
}) {
  if (users.length === 0)
    return (
      <p className="rounded-md border border-dashed border-line-200 bg-paper/70 p-12 text-center text-sm text-ink-600">
        Aucun utilisateur staff. Crée le premier avec « Nouvel utilisateur ».
      </p>
    );
  return (
    <div className="overflow-x-auto rounded-md border border-line-200 bg-paper">
      <table className="table-admin min-w-full">
        <thead>
          <tr>
            <th>E-mail</th>
            <th>Nom</th>
            <th>Rôles / accès</th>
            <th>Statut</th>
            <th className="text-right">Action</th>
          </tr>
        </thead>
        <tbody>
          {users.map((u) => (
            <tr key={u.id}>
              <td className="font-medium text-ink-900">{u.email}</td>
              <td className="text-ink-700">
                {`${u.first_name} ${u.last_name}`.trim() || ""}
              </td>
              <td>
                <div className="flex flex-wrap gap-1">
                  {u.full_access ? (
                    <span className="pill pill-success">Accès total</span>
                  ) : u.role_ids.length ? (
                    u.role_ids.map((id) => (
                      <span key={id} className="pill pill-muted">
                        {roleName[id] ?? `#${id}`}
                      </span>
                    ))
                  ) : (
                    <span className="text-xs text-ink-400">Aucun rôle</span>
                  )}
                </div>
              </td>
              <td>
                <span className={"pill " + (u.is_active ? "pill-success" : "pill-muted")}>
                  {u.is_active ? "Actif" : "Désactivé"}
                </span>
              </td>
              <td className="text-right">
                <button
                  type="button"
                  onClick={() => onEdit(u)}
                  className="rounded p-1.5 text-ink-500 hover:bg-blue-50 hover:text-blue-700"
                  title="Modifier"
                >
                  <Pencil className="size-4" />
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function RolesTable({
  roles,
  resources,
  onEdit,
  onDeleted,
}: {
  roles: StaffRole[];
  resources: AccessResource[];
  onEdit: (r: StaffRole) => void;
  onDeleted: () => void;
}) {
  const label = useMemo(
    () => Object.fromEntries(resources.map((r) => [r.key, r.label])),
    [resources],
  );
  async function del(role: StaffRole) {
    if (!confirm(`Supprimer le rôle « ${role.name} » ?`)) return;
    try {
      await adminApi.access.deleteRole(role.id);
      onDeleted();
    } catch (err) {
      alert((err as ApiError).detail ?? "Suppression impossible.");
    }
  }
  if (roles.length === 0)
    return (
      <p className="rounded-md border border-dashed border-line-200 bg-paper/70 p-12 text-center text-sm text-ink-600">
        Aucun rôle. Crée un rôle (ex. « Gestionnaire carnets ») puis assigne-le.
      </p>
    );
  return (
    <div className="overflow-x-auto rounded-md border border-line-200 bg-paper">
      <table className="table-admin min-w-full">
        <thead>
          <tr>
            <th>Rôle</th>
            <th>Ressources autorisées</th>
            <th>Utilisateurs</th>
            <th className="text-right">Actions</th>
          </tr>
        </thead>
        <tbody>
          {roles.map((r) => (
            <tr key={r.id}>
              <td>
                <p className="font-medium text-ink-900">{r.name}</p>
                {r.description ? (
                  <p className="text-xs text-ink-500">{r.description}</p>
                ) : null}
              </td>
              <td>
                <div className="flex flex-wrap gap-1">
                  {r.resources.slice(0, 6).map((k) => (
                    <span key={k} className="pill pill-muted">
                      {label[k] ?? k}
                    </span>
                  ))}
                  {r.resources.length > 6 ? (
                    <span className="pill pill-muted">
                      +{r.resources.length - 6}
                    </span>
                  ) : null}
                  {r.resources.length === 0 ? (
                    <span className="text-xs text-ink-400">Aucune</span>
                  ) : null}
                </div>
              </td>
              <td className="tabular-nums text-ink-700">{r.users_count}</td>
              <td className="text-right">
                <button
                  type="button"
                  onClick={() => onEdit(r)}
                  className="rounded p-1.5 text-ink-500 hover:bg-blue-50 hover:text-blue-700"
                  title="Modifier"
                >
                  <Pencil className="size-4" />
                </button>
                <button
                  type="button"
                  onClick={() => del(r)}
                  className="rounded p-1.5 text-ink-500 hover:bg-red-50 hover:text-red-600"
                  title="Supprimer"
                >
                  <Trash2 className="size-4" />
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}


// ── Modale utilisateur ───────────────────────────────────────────────────────
function UserModal({
  user,
  roles,
  onClose,
  onSaved,
}: {
  user: StaffUser | null;
  roles: StaffRole[];
  onClose: () => void;
  onSaved: () => void;
}) {
  const isNew = user === null;
  const [email, setEmail] = useState(user?.email ?? "");
  const [firstName, setFirstName] = useState(user?.first_name ?? "");
  const [lastName, setLastName] = useState(user?.last_name ?? "");
  const [password, setPassword] = useState("");
  const [roleIds, setRoleIds] = useState<number[]>(user?.role_ids ?? []);
  const [isActive, setIsActive] = useState(user?.is_active ?? true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tempPwd, setTempPwd] = useState<string | null>(null);

  function toggleRole(id: number) {
    setRoleIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id],
    );
  }

  async function save() {
    setSubmitting(true);
    setError(null);
    try {
      if (isNew) {
        const created = await adminApi.access.createUser({
          email,
          first_name: firstName,
          last_name: lastName,
          password: password || undefined,
          role_ids: roleIds,
        });
        if (created.temporary_password) {
          setTempPwd(created.temporary_password);
          return; // On garde la modale ouverte pour montrer le mot de passe.
        }
      } else {
        await adminApi.access.updateUser(user!.id, {
          first_name: firstName,
          last_name: lastName,
          role_ids: roleIds,
          is_active: isActive,
        });
      }
      onSaved();
    } catch (err) {
      setError((err as ApiError).detail ?? "Enregistrement impossible.");
    } finally {
      setSubmitting(false);
    }
  }

  async function resetPassword() {
    if (!user) return;
    if (!confirm("Générer un nouveau mot de passe pour cet utilisateur ?")) return;
    try {
      const res = await adminApi.access.updateUser(user.id, { reset_password: true });
      if (res.temporary_password) setTempPwd(res.temporary_password);
    } catch (err) {
      setError((err as ApiError).detail ?? "Réinitialisation impossible.");
    }
  }

  if (tempPwd) {
    return (
      <Modal
        open
        onClose={onSaved}
        title="Mot de passe généré"
        tone="success"
        footer={
          <button
            type="button"
            onClick={onSaved}
            className={buttonClasses({ variant: "primary", size: "sm" })}
          >
            Terminé
          </button>
        }
      >
        <div className="space-y-3">
          <p className="text-sm text-ink-700">
            Transmets ce mot de passe à l&apos;utilisateur. Il ne sera{" "}
            <strong>plus affiché</strong> ensuite.
          </p>
          <div className="flex items-center gap-2 rounded-md border border-line-200 bg-cream px-3 py-2">
            <code className="flex-1 font-mono text-sm text-ink-900">{tempPwd}</code>
            <button
              type="button"
              onClick={() => navigator.clipboard?.writeText(tempPwd)}
              className="rounded p-1.5 text-ink-500 hover:bg-blue-50 hover:text-blue-700"
              title="Copier"
            >
              <Copy className="size-4" />
            </button>
          </div>
        </div>
      </Modal>
    );
  }

  return (
    <Modal
      open
      onClose={onClose}
      title={isNew ? "Nouvel utilisateur staff" : `Modifier ${user?.email}`}
      footer={
        <>
          <button
            type="button"
            onClick={onClose}
            className={buttonClasses({ variant: "ghost", size: "sm" })}
          >
            Annuler
          </button>
          <button
            type="button"
            onClick={save}
            disabled={submitting || (isNew && !email)}
            className={buttonClasses({ variant: "primary", size: "sm" })}
          >
            {submitting ? "Enregistrement…" : isNew ? "Créer" : "Enregistrer"}
          </button>
        </>
      }
    >
      <div className="space-y-4">
        {error ? (
          <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
            {error}
          </div>
        ) : null}

        <ModalField label="E-mail">
          <input
            type="email"
            value={email}
            disabled={!isNew}
            onChange={(e) => setEmail(e.target.value)}
            className={modalInputClass + (isNew ? "" : " opacity-60")}
            placeholder="prenom.nom@gathe.finance"
          />
        </ModalField>

        <div className="grid grid-cols-2 gap-3">
          <ModalField label="Prénom">
            <input
              value={firstName}
              onChange={(e) => setFirstName(e.target.value)}
              className={modalInputClass}
            />
          </ModalField>
          <ModalField label="Nom">
            <input
              value={lastName}
              onChange={(e) => setLastName(e.target.value)}
              className={modalInputClass}
            />
          </ModalField>
        </div>

        {isNew ? (
          <ModalField
            label="Mot de passe (optionnel)"
            hint="Laisser vide = un mot de passe est généré et affiché une fois."
          >
            <input
              type="text"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className={modalInputClass}
              placeholder="Généré automatiquement"
            />
          </ModalField>
        ) : (
          <div className="flex items-center justify-between rounded-md border border-line-200 px-3 py-2">
            <div>
              <p className="text-sm font-medium text-ink-900">Compte actif</p>
              <p className="text-xs text-ink-500">
                Désactiver bloque la connexion sans supprimer l&apos;historique.
              </p>
            </div>
            <button
              type="button"
              onClick={() => setIsActive((v) => !v)}
              className={[
                "rounded-md px-3 py-1 text-xs font-medium",
                isActive
                  ? "bg-emerald/15 text-emerald"
                  : "bg-line-100 text-ink-600",
              ].join(" ")}
            >
              {isActive ? "Actif" : "Désactivé"}
            </button>
          </div>
        )}

        <ModalField
          label="Rôles"
          hint="Accès = union des ressources des rôles cochés. Aucun rôle = accès complet (compte non restreint)."
        >
          <div className="space-y-1.5">
            {roles.length === 0 ? (
              <p className="text-xs text-ink-500">
                Aucun rôle défini. Crée-en un dans l&apos;onglet « Rôles ».
              </p>
            ) : (
              roles.map((r) => (
                <label
                  key={r.id}
                  className="flex cursor-pointer items-center gap-2 rounded-md border border-line-200 px-3 py-1.5 hover:bg-cream"
                >
                  <input
                    type="checkbox"
                    checked={roleIds.includes(r.id)}
                    onChange={() => toggleRole(r.id)}
                    className="size-4 accent-blue-700"
                  />
                  <span className="text-sm text-ink-800">{r.name}</span>
                  <span className="ml-auto text-xs text-ink-400">
                    {r.resources.length} ressource{r.resources.length > 1 ? "s" : ""}
                  </span>
                </label>
              ))
            )}
          </div>
        </ModalField>

        {!isNew ? (
          <button
            type="button"
            onClick={resetPassword}
            className="inline-flex items-center gap-1.5 text-xs font-medium text-terra-700 hover:text-terra-800"
          >
            <UserX className="size-3.5" />
            Réinitialiser le mot de passe
          </button>
        ) : null}
      </div>
    </Modal>
  );
}


// ── Modale rôle ──────────────────────────────────────────────────────────────
function RoleModal({
  role,
  resources,
  onClose,
  onSaved,
}: {
  role: StaffRole | null;
  resources: AccessResource[];
  onClose: () => void;
  onSaved: () => void;
}) {
  const isNew = role === null;
  const [name, setName] = useState(role?.name ?? "");
  const [description, setDescription] = useState(role?.description ?? "");
  const [selected, setSelected] = useState<string[]>(role?.resources ?? []);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function toggle(key: string) {
    setSelected((prev) =>
      prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key],
    );
  }

  async function save() {
    setSubmitting(true);
    setError(null);
    try {
      if (isNew) {
        await adminApi.access.createRole({ name, description, resources: selected });
      } else {
        await adminApi.access.updateRole(role!.id, {
          name,
          description,
          resources: selected,
        });
      }
      onSaved();
    } catch (err) {
      setError((err as ApiError).detail ?? "Enregistrement impossible.");
    } finally {
      setSubmitting(false);
    }
  }

  const allSelected = selected.length === resources.length;

  return (
    <Modal
      open
      onClose={onClose}
      title={isNew ? "Nouveau rôle" : `Modifier « ${role?.name} »`}
      footer={
        <>
          <button
            type="button"
            onClick={onClose}
            className={buttonClasses({ variant: "ghost", size: "sm" })}
          >
            Annuler
          </button>
          <button
            type="button"
            onClick={save}
            disabled={submitting || !name.trim()}
            className={buttonClasses({ variant: "primary", size: "sm" })}
          >
            {submitting ? "Enregistrement…" : isNew ? "Créer" : "Enregistrer"}
          </button>
        </>
      }
    >
      <div className="space-y-4">
        {error ? (
          <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
            {error}
          </div>
        ) : null}

        <ModalField label="Nom du rôle">
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            className={modalInputClass}
            placeholder="Ex. Gestionnaire carnets"
          />
        </ModalField>

        <ModalField label="Description (optionnel)">
          <input
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            className={modalInputClass}
          />
        </ModalField>

        <ModalField label={`Ressources autorisées (${selected.length}/${resources.length})`}>
          <div className="mb-2">
            <button
              type="button"
              onClick={() =>
                setSelected(allSelected ? [] : resources.map((r) => r.key))
              }
              className="text-xs font-medium text-blue-700 hover:underline"
            >
              {allSelected ? "Tout décocher" : "Tout cocher"}
            </button>
          </div>
          <div className="grid grid-cols-1 gap-1 sm:grid-cols-2">
            {resources.map((r) => {
              const on = selected.includes(r.key);
              return (
                <label
                  key={r.key}
                  className={[
                    "flex cursor-pointer items-center gap-2 rounded-md border px-3 py-1.5 text-sm",
                    on
                      ? "border-blue-700/40 bg-blue-50 text-ink-900"
                      : "border-line-200 text-ink-700 hover:bg-cream",
                  ].join(" ")}
                >
                  <input
                    type="checkbox"
                    checked={on}
                    onChange={() => toggle(r.key)}
                    className="size-4 accent-blue-700"
                  />
                  <span className="flex-1">{r.label}</span>
                  {on ? <Check className="size-3.5 text-blue-700" /> : null}
                </label>
              );
            })}
          </div>
        </ModalField>
      </div>
    </Modal>
  );
}
