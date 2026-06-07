"use client";

import { useEffect, useState } from "react";
import { Clock, Play, RotateCcw, Edit3, CheckCircle2, AlertCircle } from "lucide-react";

import { buttonClasses } from "@gathe/ui";

import { Modal } from "@/components/modal";
import {
  adminApi,
  type ApiError,
  type CronScheduleRow,
} from "@/lib/api";


/**
 * Cron schedules (django-q2) — édition de la cadence pour la recette.
 *
 * L'admin peut :
 *   • Modifier l'expression cron d'un job (ex. cadence toutes les 15 min
 *     pour boucler en test rapide).
 *   • Exécuter un job immédiatement (run-now) sans attendre l'occurrence.
 *   • Restaurer toutes les cadences au seed initial.
 *
 * À utiliser en environnement de recette/staging uniquement.
 */
export default function CronSchedulesPage() {
  return <Inner />;
}


function Inner() {
  const [rows, setRows] = useState<CronScheduleRow[]>([]);
  const [presets, setPresets] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState<CronScheduleRow | null>(null);
  const [editCron, setEditCron] = useState("");
  const [saving, setSaving] = useState(false);
  const [busy, setBusy] = useState<string | null>(null); // name of row being run
  const [message, setMessage] = useState<{
    tone: "ok" | "err";
    text: string;
  } | null>(null);

  async function reload() {
    setLoading(true);
    try {
      adminApi.primeCsrf().catch(() => undefined);
      const data = await adminApi.cronSchedules.list();
      setRows(data.results);
      setPresets(data.presets);
    } catch (err) {
      const apiErr = err as ApiError;
      setMessage({
        tone: "err",
        text: apiErr.detail ?? "Chargement impossible.",
      });
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    reload();
  }, []);

  function openEdit(row: CronScheduleRow) {
    setEditing(row);
    setEditCron(row.cron);
  }

  async function saveEdit() {
    if (!editing) return;
    setSaving(true);
    try {
      await adminApi.cronSchedules.update(editing.name, editCron.trim());
      setMessage({ tone: "ok", text: `${editing.name} mis à jour.` });
      setEditing(null);
      await reload();
    } catch (err) {
      const apiErr = err as ApiError;
      setMessage({
        tone: "err",
        text: apiErr.detail ?? "Échec de la mise à jour.",
      });
    } finally {
      setSaving(false);
    }
  }

  async function runNow(row: CronScheduleRow) {
    setBusy(row.name);
    try {
      const res = await adminApi.cronSchedules.runNow(row.name);
      const summary = JSON.stringify(res.summary, null, 0).slice(0, 200);
      setMessage({
        tone: "ok",
        text: `${row.name} exécuté · ${summary}`,
      });
    } catch (err) {
      const apiErr = err as ApiError;
      setMessage({
        tone: "err",
        text: apiErr.detail ?? "Échec d'exécution.",
      });
    } finally {
      setBusy(null);
    }
  }

  async function resetDefaults() {
    if (!confirm("Restaurer toutes les cadences cron à leur valeur d'origine ?"))
      return;
    try {
      const res = await adminApi.cronSchedules.resetDefaults();
      setMessage({
        tone: "ok",
        text: `${res.count} cadence(s) restaurée(s).`,
      });
      await reload();
    } catch (err) {
      const apiErr = err as ApiError;
      setMessage({
        tone: "err",
        text: apiErr.detail ?? "Échec du reset.",
      });
    }
  }

  return (
    <main className="space-y-6 p-8">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div className="space-y-1">
          <h1 className="font-display text-2xl text-ink-900">
            Cron schedules (recette)
          </h1>
          <p className="max-w-2xl text-sm text-ink-500">
            Modifie la cadence des jobs automatiques pour boucler en test rapide
            (ex. faire passer les intérêts épargne mensuels à toutes les 2h).
            Chaque job émet ses notifications/emails normalement.{" "}
            <strong className="text-terra-700">
              À ne pas laisser modifié en prod réelle.
            </strong>
          </p>
        </div>
        <button
          type="button"
          onClick={resetDefaults}
          className={`${buttonClasses({ variant: "secondary", size: "sm" })} gap-2`}
        >
          <RotateCcw className="h-4 w-4" />
          Restaurer les valeurs par défaut
        </button>
      </header>

      {message && (
        <div
          className={`rounded-md border p-3 text-sm ${
            message.tone === "ok"
              ? "border-emerald/30 bg-emerald/10 text-emerald-900"
              : "border-red-300 bg-red-50 text-red-900"
          }`}
        >
          {message.text}
        </div>
      )}

      {loading ? (
        <div className="rounded-md border border-line-200 bg-paper p-8 text-center text-sm text-ink-500">
          Chargement…
        </div>
      ) : (
        <div className="overflow-hidden rounded-md border border-line-200 bg-paper">
          <table className="w-full text-left text-sm">
            <thead className="bg-cream text-[11px] font-semibold uppercase tracking-wider text-ink-600">
              <tr>
                <th className="px-4 py-3">Job</th>
                <th className="px-4 py-3">Cadence</th>
                <th className="px-4 py-3">Prochaine exécution</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line-200">
              {rows.map((r) => (
                <tr key={r.name}>
                  <td className="px-4 py-3 align-top">
                    <p className="font-mono text-ink-900">{r.name}</p>
                    <p className="text-[11px] text-ink-500">{r.func}</p>
                  </td>
                  <td className="px-4 py-3 align-top">
                    <p className="font-mono text-blue-700">{r.cron}</p>
                    {r.is_admin_edited && (
                      <p className="mt-0.5 flex items-center gap-1 text-[11px] text-terra-700">
                        <AlertCircle className="h-3 w-3" />
                        modifié (défaut :{" "}
                        <code className="font-mono">{r.default_cron}</code>)
                      </p>
                    )}
                    {!r.is_admin_edited && r.default_cron && (
                      <p className="mt-0.5 flex items-center gap-1 text-[11px] text-ink-500">
                        <CheckCircle2 className="h-3 w-3 text-emerald" />
                        valeur par défaut
                      </p>
                    )}
                  </td>
                  <td className="px-4 py-3 align-top text-ink-700">
                    {r.next_run ? (
                      <time className="font-mono text-[12px]">
                        {new Date(r.next_run).toLocaleString("fr-FR", {
                          dateStyle: "short",
                          timeStyle: "short",
                        })}
                      </time>
                    ) : (
                      <span className="text-ink-400">—</span>
                    )}
                  </td>
                  <td className="px-4 py-3 align-top">
                    <div className="flex justify-end gap-2">
                      <button
                        type="button"
                        onClick={() => openEdit(r)}
                        className={`${buttonClasses({ variant: "secondary", size: "sm" })} gap-1.5`}
                      >
                        <Edit3 className="h-3.5 w-3.5" />
                        Modifier
                      </button>
                      <button
                        type="button"
                        onClick={() => runNow(r)}
                        disabled={busy === r.name}
                        className={`${buttonClasses({ variant: "primary", size: "sm" })} gap-1.5`}
                      >
                        <Play className="h-3.5 w-3.5" />
                        {busy === r.name ? "Exécution…" : "Run-now"}
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
              {rows.length === 0 && (
                <tr>
                  <td colSpan={4} className="p-6 text-center text-ink-500">
                    Aucun schedule. Lancer{" "}
                    <code>python manage.py seed_q_schedules</code> sur le serveur.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      <Modal
        open={!!editing}
        onClose={() => setEditing(null)}
        title={editing ? `Modifier ${editing.name}` : ""}
      >
        {editing && (
          <div className="space-y-4 p-1">
            <div>
              <label
                htmlFor="cron-input"
                className="mb-1 block text-xs font-semibold uppercase tracking-wider text-ink-600"
              >
                Expression cron (minute heure jour mois jour-semaine)
              </label>
              <input
                id="cron-input"
                type="text"
                value={editCron}
                onChange={(e) => setEditCron(e.target.value)}
                className="w-full rounded-md border border-line-200 bg-paper px-3 py-2 font-mono text-sm focus:border-blue-700 focus:outline-none"
                placeholder="*/15 * * * *"
              />
              <p className="mt-1 text-[11px] text-ink-500">
                Défaut :{" "}
                <code className="font-mono">{editing.default_cron ?? "—"}</code>
              </p>
            </div>

            <div>
              <p className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-ink-600">
                Presets rapides
              </p>
              <div className="flex flex-wrap gap-2">
                {Object.entries(presets).map(([label, cron]) => (
                  <button
                    key={label}
                    type="button"
                    onClick={() => setEditCron(cron)}
                    className="rounded-md border border-line-200 bg-cream px-2 py-1 text-[11px] text-ink-700 transition hover:border-blue-700 hover:text-blue-700"
                    title={cron}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setEditing(null)}
                className={buttonClasses({ variant: "secondary", size: "sm" })}
                disabled={saving}
              >
                Annuler
              </button>
              <button
                type="button"
                onClick={saveEdit}
                className={buttonClasses({ variant: "primary", size: "sm" })}
                disabled={saving || !editCron.trim()}
              >
                {saving ? "Sauvegarde…" : "Sauvegarder"}
              </button>
            </div>
          </div>
        )}
      </Modal>
    </main>
  );
}
