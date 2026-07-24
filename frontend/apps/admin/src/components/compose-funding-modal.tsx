"use client";

import { useEffect, useMemo, useState } from "react";
import { X, Coins, AlertCircle, CheckCircle2, Landmark } from "lucide-react";

import { buttonClasses } from "@gathe/ui";

import {
  adminApi,
  type ApiError,
  type LenderTranche,
} from "@/lib/api";


type Selection = {
  trancheId: number;
  checked: boolean;
  montant: string;
};


export type ComposeFundingTarget = {
  id: number;
  numero_dossier: string;
  member_label: string;
  capital: string;
};


export function ComposeFundingModal({
  target,
  onClose,
  onSuccess,
}: {
  target: ComposeFundingTarget | null;
  onClose: () => void;
  onSuccess: (msg: string) => void;
}) {
  const [tranches, setTranches] = useState<LenderTranche[]>([]);
  const [selections, setSelections] = useState<Map<number, Selection>>(new Map());
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Charger les tranches DISPONIBLE a chaque ouverture du modal.
  useEffect(() => {
    if (!target) return;
    setLoading(true);
    setError(null);
    setSelections(new Map());
    adminApi.lenderTranches
      .list({ statut: "disponible" })
      .then((res) => {
        setTranches(res.items);
        // Pre-init : checkbox false + montant default = montant tranche
        const init = new Map<number, Selection>();
        res.items.forEach((t) =>
          init.set(t.id, { trancheId: t.id, checked: false, montant: t.montant }),
        );
        setSelections(init);
      })
      .catch((err) => {
        const apiErr = err as ApiError;
        setError(apiErr.detail ?? "Chargement des tranches impossible.");
      })
      .finally(() => setLoading(false));
  }, [target]);

  const totals = useMemo(() => {
    let total = 0;
    let count = 0;
    selections.forEach((sel) => {
      if (sel.checked) {
        total += Number(sel.montant) || 0;
        count += 1;
      }
    });
    return { total, count };
  }, [selections]);

  const capital = target ? Number(target.capital) : 0;
  const isOver = totals.total > capital;
  // Caisse interne (coop) : appoint qui comble toujours le reste jusqu'à 100 %.
  // Ce n'est PAS un prêteur → aucune allocation, aucun intérêt prêteur (k %) :
  // la coop finance ce résidu sur ses fonds propres et garde son intérêt. Non
  // persisté (le résidu coop est implicite, comme aujourd'hui).
  const caisseInterne = Math.max(0, capital - totals.total);
  // La couverture est toujours à 100 % (prêteurs + caisse) sauf dépassement.
  const isComplete = !isOver && capital > 0;

  function toggle(trancheId: number) {
    const current = selections.get(trancheId);
    if (!current) return;
    const next = new Map(selections);
    next.set(trancheId, { ...current, checked: !current.checked });
    setSelections(next);
  }

  function setMontant(trancheId: number, value: string) {
    const current = selections.get(trancheId);
    if (!current) return;
    const next = new Map(selections);
    next.set(trancheId, { ...current, montant: value });
    setSelections(next);
  }

  function autoFill() {
    // Auto-fill : prendre les tranches disponibles dans l'ordre jusqu'a
    // atteindre le capital cible, en splittant la derniere si besoin.
    if (!target) return;
    const next = new Map(selections);
    let restant = capital;
    for (const t of tranches) {
      const sel = next.get(t.id);
      if (!sel || restant <= 0) {
        if (sel) next.set(t.id, { ...sel, checked: false, montant: t.montant });
        continue;
      }
      const trancheMontant = Number(t.montant);
      const take = Math.min(restant, trancheMontant);
      next.set(t.id, { ...sel, checked: true, montant: String(take) });
      restant -= take;
    }
    setSelections(next);
  }

  async function submit() {
    if (!target) return;
    if (isOver) {
      setError("Le total des prêteurs dépasse le capital du crédit.");
      return;
    }
    const picks = Array.from(selections.values())
      .filter((s) => s.checked && Number(s.montant) > 0)
      .map((s) => ({ tranche_id: s.trancheId, montant: s.montant }));
    // Aucun prêteur sélectionné : la caisse interne (coop) finance 100 % du
    // crédit. Rien à engager côté prêteurs → pas d'appel API, le résidu coop
    // reste implicite (le crédit est décaissable tel quel).
    if (picks.length === 0) {
      onSuccess(
        `Crédit financé intégralement par la caisse interne (coop) — ` +
          `aucun prêteur à engager.`,
      );
      onClose();
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const res = await adminApi.lenderTranches.composeFunding(target.id, {
        selections: picks,
      });
      const caisseMsg =
        caisseInterne > 0
          ? ` Reste ${formatXAF(caisseInterne)} XAF via la caisse interne (coop).`
          : "";
      onSuccess(
        `Funding compose : ${res.n_tranches_engagees} tranches engagees ` +
          `(${res.n_tranches_splittees} splittees). Total ${res.total_engage} XAF.` +
          caisseMsg,
      );
      onClose();
    } catch (err) {
      const apiErr = err as ApiError;
      setError(apiErr.detail ?? "Composition impossible.");
    } finally {
      setSubmitting(false);
    }
  }

  if (!target) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-ink-900/40 backdrop-blur-sm md:items-center">
      <div className="flex h-[90vh] w-full max-w-4xl flex-col rounded-t-2xl bg-paper shadow-2xl md:h-[80vh] md:rounded-md">
        {/* Header */}
        <header className="flex items-start justify-between border-b border-line-200 px-6 py-4">
          <div>
            <p className="font-display text-[0.7rem] font-semibold uppercase tracking-[0.18em] text-terra-600">
              Composer le funding
            </p>
            <h2 className="mt-1 font-editorial text-xl font-medium text-ink-900">
              Crédit {target.numero_dossier}
            </h2>
            <p className="mt-0.5 text-sm text-ink-600">
              {target.member_label} · capital{" "}
              <strong className="text-ink-900">{formatXAF(target.capital)} XAF</strong>
            </p>
            <p className="mt-1.5 text-xs text-ink-500">
              Engagement direct : les prêteurs sont notifiés et les intérêts
              seront crédités automatiquement sur leur compte épargne classique.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-full p-1.5 text-ink-500 hover:bg-line-100 hover:text-ink-900"
          >
            <X className="size-5" aria-hidden="true" />
          </button>
        </header>

        {/* Sticky totalisateur */}
        <div
          className={[
            "border-b px-6 py-3",
            isComplete
              ? "border-emerald/30 bg-emerald/5"
              : isOver
                ? "border-terra-400/40 bg-terra-50/40"
                : "border-line-200 bg-paper",
          ].join(" ")}
        >
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <Coins
                className={
                  "size-5 " +
                  (isComplete
                    ? "text-emerald"
                    : isOver
                      ? "text-terra-700"
                      : "text-ink-500")
                }
                aria-hidden="true"
              />
              <div>
                <p className="font-mono text-base font-semibold text-ink-900">
                  {formatXAF(totals.total)} <span className="text-ink-500">/ {formatXAF(capital)}</span> XAF
                </p>
                <p className="text-xs text-ink-600">
                  {totals.count} prêteur{totals.count > 1 ? "s" : ""} ·{" "}
                  {isOver
                    ? `dépassement ${formatXAF(-(capital - totals.total))} XAF`
                    : caisseInterne > 0
                      ? `caisse interne (coop) ${formatXAF(caisseInterne)} XAF · couverture 100 %`
                      : "couverture exacte (100 % prêteurs)"}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={autoFill}
                disabled={loading || submitting || tranches.length === 0}
                className={buttonClasses({ variant: "ghost", size: "sm" })}
              >
                Auto-remplir
              </button>
              {isComplete ? (
                <span className="inline-flex items-center gap-1 rounded-full bg-emerald/10 px-2.5 py-0.5 text-[0.7rem] font-medium text-emerald ring-1 ring-inset ring-emerald/30">
                  <CheckCircle2 className="size-3" aria-hidden="true" /> Pret a engager
                </span>
              ) : null}
              {isOver ? (
                <span className="inline-flex items-center gap-1 rounded-full bg-terra-50/60 px-2.5 py-0.5 text-[0.7rem] font-medium text-terra-700 ring-1 ring-inset ring-terra-400/40">
                  <AlertCircle className="size-3" aria-hidden="true" /> Depassement
                </span>
              ) : null}
            </div>
          </div>
        </div>

        {/* Liste tranches */}
        <div className="flex-1 overflow-y-auto px-6 py-4">
          {error ? (
            <div className="mb-4 rounded-md border border-terra-400/40 bg-terra-50/60 px-3 py-2 text-sm text-terra-700">
              {error}
            </div>
          ) : null}

          {loading ? (
            <p className="text-ink-600">Chargement des tranches...</p>
          ) : (
            <div className="space-y-2">
              {/* Caisse interne (coop) — toujours en 1re position, à côté des
                  prêteurs. Comble automatiquement le reste jusqu'à 100 %. */}
              <div className="flex items-center gap-3 rounded-md border border-emerald/30 bg-emerald/5 p-3">
                <Landmark className="size-5 shrink-0 text-emerald" aria-hidden="true" />
                <div className="flex-1">
                  <p className="font-medium text-ink-900">
                    Caisse interne (coopérative)
                  </p>
                  <p className="text-xs text-ink-600">
                    Fonds propres · comble le reste jusqu&apos;à 100 % · sans
                    intérêt prêteur (la coop garde son intérêt)
                  </p>
                </div>
                <div className="text-right">
                  <p className="font-mono text-sm font-semibold text-emerald">
                    {formatXAF(caisseInterne)} XAF
                  </p>
                  <p className="font-mono text-[0.7rem] text-ink-500">appoint auto</p>
                </div>
              </div>

              {tranches.length === 0 ? (
                <p className="rounded-md border border-dashed border-line-200 bg-paper/70 p-8 text-center text-sm text-ink-600">
                  Aucune tranche placement DISPONIBLE — la caisse interne
                  finance l&apos;intégralité du crédit.
                </p>
              ) : (
                tranches.map((t) => {
                const sel = selections.get(t.id);
                if (!sel) return null;
                return (
                  <div
                    key={t.id}
                    className={[
                      "flex items-center gap-3 rounded-md border p-3 transition-colors",
                      sel.checked
                        ? "border-blue-300 bg-blue-50/40"
                        : "border-line-200 bg-paper hover:border-line-400",
                    ].join(" ")}
                  >
                    <input
                      type="checkbox"
                      checked={sel.checked}
                      onChange={() => toggle(t.id)}
                      className="size-4 cursor-pointer accent-blue-700"
                    />
                    <div className="flex-1">
                      <p className="font-medium text-ink-900">
                        {t.member.prenom} {t.member.nom}
                      </p>
                      <p className="font-mono text-xs text-ink-600">
                        {t.member.numero_membre} · depot{" "}
                        {new Date(t.created_at).toLocaleDateString("fr-FR", {
                          day: "2-digit",
                          month: "short",
                          year: "2-digit",
                        })}
                      </p>
                    </div>
                    <div className="text-right">
                      <p className="font-mono text-xs text-ink-500">
                        max {formatXAF(t.montant)}
                      </p>
                    </div>
                    <div>
                      <input
                        type="number"
                        value={sel.montant}
                        onChange={(e) => setMontant(t.id, e.target.value)}
                        disabled={!sel.checked}
                        max={t.montant}
                        min={0}
                        className={[
                          "w-32 rounded-md border px-3 py-1.5 text-right font-mono text-sm",
                          "focus:border-blue-700 focus:outline-none",
                          sel.checked
                            ? "border-blue-300 bg-white text-ink-900"
                            : "border-line-200 bg-paper/50 text-ink-400",
                        ].join(" ")}
                      />
                    </div>
                  </div>
                );
                })
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <footer className="flex items-center justify-end gap-2 border-t border-line-200 bg-paper/50 px-6 py-3">
          <button
            type="button"
            onClick={onClose}
            disabled={submitting}
            className={buttonClasses({ variant: "ghost", size: "md" })}
          >
            Annuler
          </button>
          <button
            type="button"
            onClick={submit}
            disabled={submitting || isOver}
            title={
              isOver
                ? "Le total des prêteurs dépasse le capital"
                : totals.count === 0
                  ? "Financer 100 % via la caisse interne (coop)"
                  : `Engager ${totals.count} prêteur${totals.count > 1 ? "s" : ""} · reste caisse interne`
            }
            className={buttonClasses({ variant: "primary", size: "md" })}
          >
            {submitting
              ? "Engagement..."
              : totals.count === 0
                ? "Financer via caisse interne"
                : `Engager ${totals.count} prêteur${totals.count > 1 ? "s" : ""}`}
          </button>
        </footer>
      </div>
    </div>
  );
}


function formatXAF(value: string | number): string {
  const n = typeof value === "string" ? Number(value) : value;
  if (Number.isNaN(n)) return "0";
  return new Intl.NumberFormat("fr-FR").format(Math.round(n));
}
