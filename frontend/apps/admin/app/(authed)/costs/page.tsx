"use client";

import { useEffect, useState } from "react";
import { Check, Loader2, RotateCcw } from "lucide-react";

import {
  adminApi,
  type ApiError,
  type BusinessRate,
  type CostsConfig,
  type FeeConfig,
  type FeePayinTypes,
  type RateConfig,
} from "@/lib/api";
import { PageHeader } from "@/components/page-header";


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
    <div className="space-y-6">
      <PageHeader
        eyebrow="Coûts"
        title="Frais &amp; taux"
        description="Les montants et pourcentages appliqués par la coopérative. Toute modification est immédiate et s&apos;applique aux nouveaux calculs (crédits, intérêts d&apos;épargne, reconductions, pénalités). Tracé dans le journal d&apos;audit."
      />

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
        <>
        <div className="grid gap-8 lg:grid-cols-2">
          <section>
            <h2 className="mb-3 font-display text-xs font-semibold uppercase tracking-wider text-ink-500">
              Frais administratifs (FCFA)
            </h2>
            <div className="overflow-x-auto rounded-xl border border-line-100 bg-paper shadow-xs">
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
            <div className="overflow-x-auto rounded-xl border border-line-100 bg-paper shadow-xs">
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
                  {(config.business_rates ?? []).map((br) => (
                    <BusinessRateRow key={br.key} rate={br} />
                  ))}
                </tbody>
              </table>
            </div>
            {config.business_rates && config.business_rates.length > 0 ? (
              <p className="mt-2 text-xs text-ink-500">
                La commission de collecte et l&apos;intérêt prêteur sont aussi
                modifiables depuis <strong>Réglages</strong> ; ils sont surfacés ici
                pour regrouper tous les taux au même endroit.
              </p>
            ) : null}
          </section>
        </div>
        <TransactionFeeOperations initial={config.transaction_fee_operations} />
        <TransactionFeePayinTypes initial={config.transaction_fee_payin_types} />
        </>
      ) : null}
    </div>
  );
}


/** Périmètre du frais de transaction (%) : cases par opération. */
function TransactionFeeOperations({
  initial,
}: {
  initial?: { versement: boolean; retrait: boolean; transfert: boolean };
}) {
  const base = initial ?? { versement: true, retrait: true, transfert: true };
  const [ops, setOps] = useState(base);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [rowError, setRowError] = useState<string | null>(null);
  const dirty =
    ops.versement !== base.versement ||
    ops.retrait !== base.retrait ||
    ops.transfert !== base.transfert;

  const LABELS: { key: keyof typeof ops; label: string; hint: string }[] = [
    { key: "versement", label: "Versement", hint: "Dépôt d’épargne / collecte (Mobile Money)" },
    { key: "retrait", label: "Retrait", hint: "Retrait d’épargne (débité au paiement)" },
    { key: "transfert", label: "Transfert", hint: "Transfert de l’épargne vers un crédit" },
  ];

  async function save() {
    setSaving(true);
    setRowError(null);
    setSaved(false);
    try {
      await adminApi.costs.updateTransactionFeeOperations(ops);
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } catch (err) {
      setRowError((err as ApiError).detail ?? "Enregistrement impossible.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="mt-8 max-w-2xl rounded-xl border border-line-100 bg-paper p-5 shadow-xs">
      <h2 className="font-display text-xs font-semibold uppercase tracking-wider text-ink-500">
        Frais de transaction — opérations concernées
      </h2>
      <p className="mt-1 text-sm text-ink-600">
        Coche les opérations sur lesquelles le <strong>frais de transaction (%)</strong>
        {" "}s’applique. Le frais est prélevé <strong>en plus</strong> (le solde est débité du
        montant + frais ; le bénéficiaire reçoit le montant plein). Il reste nul tant que le
        taux « Frais de transaction » ci-dessus est à 0 %.
      </p>
      <div className="mt-4 space-y-2">
        {LABELS.map((o) => (
          <label
            key={o.key}
            className="flex cursor-pointer items-start gap-3 rounded-lg border border-line-100 px-3 py-2 hover:bg-line-50"
          >
            <input
              type="checkbox"
              checked={ops[o.key]}
              onChange={(e) => setOps({ ...ops, [o.key]: e.target.checked })}
              className="mt-0.5 size-4 accent-blue-700"
            />
            <span>
              <span className="text-sm font-medium text-ink-900">{o.label}</span>
              <span className="block text-xs text-ink-500">{o.hint}</span>
            </span>
          </label>
        ))}
      </div>
      {rowError ? (
        <p className="mt-2 text-xs text-terra-700">{rowError}</p>
      ) : null}
      <div className="mt-4 flex items-center gap-3">
        <button
          type="button"
          onClick={save}
          disabled={!dirty || saving}
          className="inline-flex items-center gap-2 rounded-lg bg-blue-700 px-4 py-2 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-blue-800 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {saving ? <Loader2 className="size-4 animate-spin" /> : <Check className="size-4" />}
          Enregistrer
        </button>
        {saved ? <span className="text-xs font-medium text-emerald-700">Enregistré ✓</span> : null}
      </div>
    </section>
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


/** Taux métier stocké en AppSetting (ratio 0–1) — édité en % comme un RateRow,
 *  mais sauvegardé via l'API générique appSettings (clé → valeur). */
function BusinessRateRow({ rate }: { rate: BusinessRate }) {
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
      const res = await adminApi.appSettings.update(
        rate.key,
        Number((pct / 100).toFixed(4)),
      );
      // La réponse renvoie la valeur normalisée (string) ; on réaffiche en %.
      const raw = (res as { value?: string | number }).value ?? rate.valeur;
      e.setValue(trimZeros(String(Number(raw) * 100)));
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
          {rate.key}
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


/** Types de paiement ENTRANT frappés par le frais (%) — admin-configurable. */
function TransactionFeePayinTypes({
  initial,
}: {
  initial?: FeePayinTypes;
}) {
  // Ordre + libellés d'affichage (les clés correspondent aux Payment.Type).
  const LABELS: { key: string; label: string; hint: string }[] = [
    { key: "epargne", label: "Épargne (collecte journalière)", hint: "Dépôt de cotisation" },
    { key: "epargne_classique", label: "Épargne classique", hint: "Dépôt libre / placement" },
    { key: "caisse_scolaire", label: "Caisse scolaire", hint: "Versement collecte particulière" },
    { key: "tontine_alimentaire", label: "Tontine alimentaire", hint: "Versement collecte particulière" },
    { key: "frais_carnet", label: "Carnet", hint: "Achat / renouvellement de carnet" },
    { key: "frais_adhesion", label: "Adhésion", hint: "Frais d'adhésion" },
    { key: "frais_inscription", label: "Inscription", hint: "Frais d'inscription" },
    { key: "frais_demande_credit", label: "Étude de crédit", hint: "Frais de demande de crédit" },
    { key: "frais_reconduction", label: "Reconduction", hint: "Frais de reconduction crédit" },
    { key: "remboursement", label: "Remboursement de crédit", hint: "Remboursement (désactivé par défaut)" },
  ];

  const base: FeePayinTypes = {};
  for (const o of LABELS) base[o.key] = initial?.[o.key] ?? false;
  const [types, setTypes] = useState<FeePayinTypes>(base);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [rowError, setRowError] = useState<string | null>(null);
  const dirty = LABELS.some((o) => types[o.key] !== base[o.key]);

  async function save() {
    setSaving(true);
    setRowError(null);
    setSaved(false);
    try {
      await adminApi.costs.updateTransactionFeePayinTypes(types);
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } catch (err) {
      setRowError((err as ApiError).detail ?? "Enregistrement impossible.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="mt-8 max-w-2xl rounded-xl border border-line-100 bg-paper p-5 shadow-xs">
      <h2 className="font-display text-xs font-semibold uppercase tracking-wider text-ink-500">
        Frais de transaction — paiements entrants concernés
      </h2>
      <p className="mt-1 text-sm text-ink-600">
        Coche chaque <strong>paiement que le membre effectue</strong> (via Mobile Money) sur
        lequel le frais (%) s’ajoute. Ex. carnet à 1&nbsp;000 avec 2&nbsp;% → le membre paie
        <strong> 1&nbsp;020</strong>. Nécessite que « Versement » soit coché ci-dessus et un
        taux &gt; 0. La saisie manuelle en agence n’est jamais frappée.
      </p>
      <div className="mt-4 grid gap-2 sm:grid-cols-2">
        {LABELS.map((o) => (
          <label
            key={o.key}
            className="flex cursor-pointer items-start gap-3 rounded-lg border border-line-100 px-3 py-2 hover:bg-line-50"
          >
            <input
              type="checkbox"
              checked={types[o.key]}
              onChange={(e) => setTypes({ ...types, [o.key]: e.target.checked })}
              className="mt-0.5 size-4 accent-blue-700"
            />
            <span>
              <span className="text-sm font-medium text-ink-900">{o.label}</span>
              <span className="block text-xs text-ink-500">{o.hint}</span>
            </span>
          </label>
        ))}
      </div>
      {rowError ? <p className="mt-2 text-xs text-terra-700">{rowError}</p> : null}
      <div className="mt-4 flex items-center gap-3">
        <button
          type="button"
          onClick={save}
          disabled={!dirty || saving}
          className="inline-flex items-center gap-2 rounded-lg bg-blue-700 px-4 py-2 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-blue-800 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {saving ? <Loader2 className="size-4 animate-spin" /> : null}
          Enregistrer
        </button>
        {saved ? (
          <span className="inline-flex items-center gap-1 text-sm text-emerald-700">
            <Check className="size-4" /> Enregistré
          </span>
        ) : null}
      </div>
    </section>
  );
}
