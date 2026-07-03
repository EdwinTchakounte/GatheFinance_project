"use client";

import { useEffect, useState } from "react";
import { Check, Loader2, RotateCcw } from "lucide-react";

import {
  adminApi,
  type ApiError,
  type CostsConfig,
  type FeeConfig,
  type RateConfig,
} from "@/lib/api";


export default function CostsPage() {
  const [config, setConfig] = useState<CostsConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function reload() {
    setLoading(true);
    setError(null);
    try {
      setConfig(await adminApi.costs.config());
    } catch (err) {
      setError((err as ApiError).detail ?? "Chargement impossible.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="px-8 py-8 lg:px-12 lg:py-10">
      <header className="mb-6">
        <p className="font-display text-[0.7rem] font-semibold uppercase tracking-[0.18em] text-terra-600">
          Coûts
        </p>
        <h1 className="mt-2 font-editorial text-3xl font-medium text-ink-900">
          Frais &amp; taux
        </h1>
        <p className="mt-1 max-w-2xl text-sm text-ink-600">
          Les montants et pourcentages appliqués par la coopérative. Toute
          modification est immédiate et s&apos;applique aux nouveaux calculs
          (crédits, intérêts d&apos;épargne, reconductions, pénalités). Tracé
          dans le journal d&apos;audit.
        </p>
      </header>

      {/* Rappel métier — les intérêts de crédit sont prélevés à la source. */}
      <div className="mb-6 rounded-md border border-emerald/30 bg-emerald/5 p-4">
        <p className="text-sm font-medium text-ink-900">
          Intérêts de crédit prélevés à la source
        </p>
        <p className="mt-1 max-w-3xl text-sm text-ink-700">
          Le taux d&apos;intérêt du crédit est appliqué <strong>une seule fois, au moment
          du prêt</strong> : les intérêts sont retenus dès le décaissement (le membre
          reçoit le capital net des intérêts). Ce ne sont donc pas des intérêts qui
          courent au fil des échéances — le taux ci-dessous sert au calcul unique
          effectué à l&apos;octroi du crédit.
        </p>
      </div>

      {error ? (
        <div className="mb-5 rounded-md border border-terra-400/40 bg-terra-50/60 px-4 py-2.5 text-sm text-terra-700">
          {error}
        </div>
      ) : null}

      {loading ? (
        <p className="text-ink-600">Chargement…</p>
      ) : config ? (
        <div className="grid gap-8 lg:grid-cols-2">
          <section>
            <h2 className="mb-3 font-display text-xs font-semibold uppercase tracking-wider text-ink-500">
              Frais administratifs (FCFA)
            </h2>
            <div className="overflow-hidden rounded-md border border-line-200 bg-paper">
              <table className="table-admin">
                <thead>
                  <tr>
                    <th>Frais</th>
                    <th className="text-right">Montant</th>
                    <th className="w-px" />
                  </tr>
                </thead>
                <tbody>
                  {config.fees.map((fee) => (
                    <FeeRow key={fee.code} fee={fee} />
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section>
            <h2 className="mb-3 font-display text-xs font-semibold uppercase tracking-wider text-ink-500">
              Taux métier (%)
            </h2>
            <div className="overflow-hidden rounded-md border border-line-200 bg-paper">
              <table className="table-admin">
                <thead>
                  <tr>
                    <th>Taux</th>
                    <th className="text-right">Valeur</th>
                    <th className="w-px" />
                  </tr>
                </thead>
                <tbody>
                  {config.rates.map((rate) => (
                    <RateRow key={rate.code} rate={rate} />
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </div>
      ) : null}
    </div>
  );
}


/** État d'édition commun à une ligne (frais ou taux). */
function useRowEdit(initial: string) {
  const [value, setValue] = useState(initial);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [rowError, setRowError] = useState<string | null>(null);
  const dirty = value.trim() !== initial.trim();

  return { value, setValue, saving, setSaving, saved, setSaved, rowError, setRowError, dirty };
}


function FeeRow({ fee }: { fee: FeeConfig }) {
  // Montant affiché en entier (les frais sont des sommes rondes en FCFA).
  const initial = String(Math.round(Number(fee.montant)));
  const e = useRowEdit(initial);

  async function save() {
    const montant = Number(e.value);
    if (!Number.isFinite(montant) || montant < 0) {
      e.setRowError("Montant ≥ 0 requis.");
      return;
    }
    e.setSaving(true);
    e.setRowError(null);
    try {
      const res = await adminApi.costs.updateFee(fee.code, { montant });
      e.setValue(String(Math.round(Number(res.montant))));
      e.setSaved(true);
      setTimeout(() => e.setSaved(false), 2000);
    } catch (err) {
      e.setRowError((err as ApiError).detail ?? "Échec.");
    } finally {
      e.setSaving(false);
    }
  }

  return (
    <tr>
      <td>
        <p className="font-medium text-ink-900">{fee.libelle}</p>
        <p className="font-mono text-[10px] uppercase tracking-wide text-ink-400">
          {fee.code}
        </p>
        {e.rowError ? (
          <p className="mt-1 text-xs text-terra-700">{e.rowError}</p>
        ) : null}
      </td>
      <td className="text-right">
        <div className="inline-flex items-center gap-1">
          <input
            type="number"
            min={0}
            step={500}
            value={e.value}
            onChange={(ev) => e.setValue(ev.target.value)}
            onKeyDown={(ev) => ev.key === "Enter" && e.dirty && save()}
            className="w-28 rounded-md border border-line-200 bg-paper py-1.5 px-2 text-right font-mono text-sm focus:border-blue-700 focus:outline-none focus:ring-1 focus:ring-blue-700"
          />
          <span className="text-xs text-ink-500">XAF</span>
        </div>
      </td>
      <td>
        <SaveButton dirty={e.dirty} saving={e.saving} saved={e.saved} onSave={save} />
      </td>
    </tr>
  );
}


function RateRow({ rate }: { rate: RateConfig }) {
  // Le backend stocke un ratio (0–1) ; on édite en pourcentage pour l'admin.
  const initialPct = trimZeros(String(Number(rate.valeur) * 100));
  const e = useRowEdit(initialPct);

  async function save() {
    const pct = Number(e.value);
    if (!Number.isFinite(pct) || pct < 0 || pct > 100) {
      e.setRowError("Pourcentage entre 0 et 100.");
      return;
    }
    e.setSaving(true);
    e.setRowError(null);
    try {
      const res = await adminApi.costs.updateRate(rate.code, {
        valeur: Number((pct / 100).toFixed(4)),
      });
      e.setValue(trimZeros(String(Number(res.valeur) * 100)));
      e.setSaved(true);
      setTimeout(() => e.setSaved(false), 2000);
    } catch (err) {
      e.setRowError((err as ApiError).detail ?? "Échec.");
    } finally {
      e.setSaving(false);
    }
  }

  return (
    <tr>
      <td>
        <p className="font-medium text-ink-900">{rate.libelle}</p>
        <p className="font-mono text-[10px] uppercase tracking-wide text-ink-400">
          {rate.code}
        </p>
        {e.rowError ? (
          <p className="mt-1 text-xs text-terra-700">{e.rowError}</p>
        ) : null}
      </td>
      <td className="text-right">
        <div className="inline-flex items-center gap-1">
          <input
            type="number"
            min={0}
            max={100}
            step={0.5}
            value={e.value}
            onChange={(ev) => e.setValue(ev.target.value)}
            onKeyDown={(ev) => ev.key === "Enter" && e.dirty && save()}
            className="w-24 rounded-md border border-line-200 bg-paper py-1.5 px-2 text-right font-mono text-sm focus:border-blue-700 focus:outline-none focus:ring-1 focus:ring-blue-700"
          />
          <span className="text-xs text-ink-500">%</span>
        </div>
      </td>
      <td>
        <SaveButton dirty={e.dirty} saving={e.saving} saved={e.saved} onSave={save} />
      </td>
    </tr>
  );
}


function SaveButton({
  dirty,
  saving,
  saved,
  onSave,
}: {
  dirty: boolean;
  saving: boolean;
  saved: boolean;
  onSave: () => void;
}) {
  if (saved) {
    return (
      <span className="inline-flex items-center gap-1 whitespace-nowrap text-xs font-medium text-emerald">
        <Check className="size-3.5" /> Enregistré
      </span>
    );
  }
  return (
    <button
      type="button"
      disabled={!dirty || saving}
      onClick={onSave}
      className={[
        "inline-flex items-center gap-1.5 whitespace-nowrap rounded-md px-3 py-1.5 text-xs font-medium transition-colors",
        dirty && !saving
          ? "bg-blue-700 text-white hover:bg-blue-800"
          : "cursor-not-allowed bg-cream text-ink-400",
      ].join(" ")}
    >
      {saving ? (
        <>
          <Loader2 className="size-3.5 animate-spin" /> …
        </>
      ) : dirty ? (
        "Enregistrer"
      ) : (
        <>
          <RotateCcw className="size-3.5" /> À jour
        </>
      )}
    </button>
  );
}


/** "10.0000" → "10", "1.5000" → "1.5" (affichage de pourcentage propre). */
function trimZeros(s: string): string {
  return s.includes(".") ? s.replace(/\.?0+$/, "") : s;
}
