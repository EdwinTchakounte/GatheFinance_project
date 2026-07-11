"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { Container, buttonClasses } from "@gathe/ui";

import {
  portalApi,
  type ApiError,
  type LenderInterestPayout,
  type LenderState,
  type LenderTranche,
} from "@/lib/api";


/**
 * Espace prêteur (épargne-prêteur §6).
 *
 * Le membre signe la convention (mode A global ou B par tranches) et gère
 * ses tranches d'épargne prêtables. L'engagement d'une tranche dans un
 * crédit est effectué par l'administrateur ; le prêteur est notifié et les
 * intérêts sont crédités automatiquement sur son compte épargne classique.
 * Aucun consentement par-funding-request n'est demandé au prêteur.
 */
export default function LenderPage() {
  const router = useRouter();
  const [state, setState] = useState<LenderState | null>(null);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState<{
    tone: "ok" | "err";
    text: string;
  } | null>(null);

  async function reload() {
    setLoading(true);
    try {
      await portalApi.primeCsrf();
      const data = await portalApi.lender.me();
      setState(data);
    } catch (err) {
      const apiErr = err as ApiError;
      if (apiErr.status === 401 || apiErr.status === 403) {
        router.replace("/connexion");
        return;
      }
      setMessage({
        tone: "err",
        text: apiErr.detail ?? "Impossible de charger ton espace prêteur.",
      });
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    reload();
    /* eslint-disable-next-line react-hooks/exhaustive-deps */
  }, []);

  if (loading || !state) {
    return (
      <main className="py-16">
        <Container>
          <p className="text-center text-ink-600">Chargement…</p>
        </Container>
      </main>
    );
  }

  const consent = state.consent;
  const isActive = !!consent?.is_active;

  return (
    <main className="py-12 lg:py-16">
      <Container className="max-w-3xl">
        <header className="mb-8">
          <button
            type="button"
            onClick={() => router.push("/credit")}
            className="text-sm text-ink-600 transition-colors hover:text-blue-700"
          >
            ← Retour à mes crédits
          </button>
          <h1 className="mt-3 font-editorial text-3xl font-medium text-ink-900">
            Espace prêteur
          </h1>
          <p className="mt-2 text-sm text-ink-600">
            Mets ton épargne classique à disposition pour financer les crédits
            de la coopérative. La coopérative partage à 50/50 les intérêts
            perçus avec les prêteurs (§6 BUSINESS_RULES_2026).
          </p>
        </header>

        {message && (
          <div
            className={`mb-4 rounded-md border px-4 py-3 text-sm ${
              message.tone === "ok"
                ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                : "border-terra-400/40 bg-terra-50/60 text-terra-700"
            }`}
          >
            {message.text}
          </div>
        )}

        {/* Convention */}
        {!isActive ? (
          <OptInBlock
            onDone={(text) => {
              setMessage({ tone: "ok", text });
              reload();
            }}
            onError={(text) => setMessage({ tone: "err", text })}
          />
        ) : (
          <ActiveLenderBlock
            state={state}
            onChange={(text) => {
              setMessage({ tone: "ok", text });
              reload();
            }}
            onError={(text) => setMessage({ tone: "err", text })}
          />
        )}
      </Container>
    </main>
  );
}


// ---------------------------------------------------------------------------
// Onboarding — opt-in
// ---------------------------------------------------------------------------


function OptInBlock({
  onDone,
  onError,
}: {
  onDone: (msg: string) => void;
  onError: (msg: string) => void;
}) {
  const [mode, setMode] = useState<"global" | "tranches">("tranches");
  const [submitting, setSubmitting] = useState(false);

  async function onSign() {
    setSubmitting(true);
    try {
      await portalApi.lender.optIn(mode === "global");
      onDone("Convention signée — tu es maintenant prêteur actif.");
    } catch (err) {
      const apiErr = err as ApiError;
      onError(apiErr.detail ?? "Signature impossible.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="rounded-md border border-line-200 bg-paper p-7">
      <h2 className="font-display text-xl font-medium text-ink-900">
        Devenir prêteur
      </h2>
      <p className="mt-2 text-sm text-ink-600">
        Choisis le mode qui te convient. Tu pourras changer à tout moment.
      </p>

      <div className="mt-5 space-y-2">
        <RadioCard
          checked={mode === "global"}
          onClick={() => setMode("global")}
          title="Mode A — Solde global"
          hint="L'ensemble de mon épargne classique est prêtable. Plus simple."
        />
        <RadioCard
          checked={mode === "tranches"}
          onClick={() => setMode("tranches")}
          title="Mode B — Tranches explicites"
          hint="Je décide tranche par tranche les montants que je rends prêtables."
        />
      </div>

      <div className="mt-6 rounded-md bg-cream p-4 text-xs text-ink-700">
        <p className="font-medium text-ink-900">⚠️ Engagement</p>
        <p className="mt-1">
          En signant la convention, tu acceptes que tes montants prêtables
          soient temporairement bloqués au financement de crédits validés. Les
          intérêts perçus sont partagés à 50/50 avec la coopérative.
        </p>
      </div>

      <button
        onClick={onSign}
        disabled={submitting}
        className={
          buttonClasses({
            variant: "success",
            size: "lg",
            fullWidth: true,
          }) + " mt-5"
        }
      >
        {submitting ? "Signature…" : "Signer la convention"}
      </button>
    </section>
  );
}


// ---------------------------------------------------------------------------
// Membre actif — tranches + révocation
// ---------------------------------------------------------------------------


function ActiveLenderBlock({
  state,
  onChange,
  onError,
}: {
  state: LenderState;
  onChange: (msg: string) => void;
  onError: (msg: string) => void;
}) {
  const consent = state.consent!;
  return (
    <div className="space-y-5">
      {/* Convention info */}
      <section className="rounded-md border border-line-200 bg-paper p-6">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="font-display text-lg font-medium text-ink-900">
              Convention active
            </h2>
            <p className="mt-0.5 text-xs text-ink-600">
              Mode {consent.is_global ? "A (solde global)" : "B (tranches explicites)"}{" "}
              · signée le {formatDate(consent.convention_signed_at)}
            </p>
          </div>
          <RevokeButton
            disabled={Decimal(state.totals.engagee) > 0}
            onDone={onChange}
            onError={onError}
          />
        </div>

        <dl className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-4 text-xs">
          <Stat label="Disponible" value={state.totals.disponible} tone="emerald" />
          <Stat label="Engagé" value={state.totals.engagee} tone="terra" />
          <Stat label="Libérée" value={state.totals.liberee} tone="ink" />
          <Stat label="Annulée" value={state.totals.annulee} tone="ink" />
        </dl>
      </section>

      {/* Tranches */}
      {!consent.is_global && (
        <TranchesSection
          tranches={state.tranches}
          onChange={onChange}
          onError={onError}
        />
      )}

      {consent.is_global && (
        <p className="rounded-md border border-blue-700/30 bg-cream p-4 text-xs text-ink-700">
          ℹ️ En mode A (global), tu n'as pas besoin de gérer des tranches : tout
          ton solde épargne classique est automatiquement disponible pour le
          funding. Les tranches sont créées par le système à chaque engagement.
        </p>
      )}

      {/* A6 . Historique des interets percus (parite mobile). */}
      <PayoutsSection />
    </div>
  );
}


function PayoutsSection() {
  const [payouts, setPayouts] = useState<LenderInterestPayout[] | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    portalApi.lender
      .payouts()
      .then((res) => {
        if (!cancelled) setPayouts(res.results);
      })
      .catch(() => {
        if (!cancelled) setPayouts([]);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const total = (payouts ?? []).reduce(
    (acc, p) => acc + Number(p.montant || 0),
    0,
  );

  return (
    <section className="rounded-lg border border-line-200 bg-paper p-5 shadow-sm">
      <div className="flex items-end justify-between gap-3">
        <div>
          <h2 className="font-display text-base font-semibold text-ink-900">
            Mes intérêts perçus
          </h2>
          <p className="mt-0.5 text-xs text-ink-600">
            Versements reçus sur les crédits financés par mon épargne placement.
          </p>
        </div>
        {payouts !== null && payouts.length > 0 ? (
          <span className="rounded-md bg-emerald-50 px-2.5 py-1 text-xs font-semibold text-emerald-700">
            Total {total.toLocaleString("fr-FR")} XAF
          </span>
        ) : null}
      </div>

      {loading ? (
        <p className="mt-4 text-sm text-ink-600">Chargement…</p>
      ) : !payouts || payouts.length === 0 ? (
        <p className="mt-4 rounded-md border border-dashed border-line-200 bg-paper/70 p-6 text-center text-xs text-ink-600">
          Aucun intérêt perçu pour le moment. Tu en recevras dès qu'un crédit
          financé par ton épargne placement sera décaissé ou remboursé.
        </p>
      ) : (
        <ul className="mt-4 divide-y divide-line-200">
          {payouts.slice(0, 10).map((p) => (
            <li key={p.id} className="flex items-center justify-between py-2.5">
              <div className="min-w-0">
                <p className="truncate text-sm font-medium text-ink-900">
                  Crédit {p.loan.numero_dossier}
                </p>
                <p className="text-[11px] text-ink-500">
                  {p.kind === "at_source"
                    ? "Versé à la source (décaissement)"
                    : `Échéance #${p.installment_numero ?? "?"}`}{" "}
                  ·{" "}
                  {new Date(p.date).toLocaleDateString("fr-FR", {
                    day: "2-digit",
                    month: "short",
                    year: "2-digit",
                  })}
                </p>
              </div>
              <p className="font-mono text-sm font-semibold text-emerald-700">
                +{Number(p.montant).toLocaleString("fr-FR")} XAF
              </p>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}


function RevokeButton({
  disabled,
  onDone,
  onError,
}: {
  disabled: boolean;
  onDone: (msg: string) => void;
  onError: (msg: string) => void;
}) {
  const [confirming, setConfirming] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  async function onConfirm() {
    setSubmitting(true);
    try {
      await portalApi.lender.revoke();
      onDone("Convention révoquée.");
    } catch (err) {
      const apiErr = err as ApiError;
      onError(apiErr.detail ?? "Révocation impossible.");
    } finally {
      setSubmitting(false);
      setConfirming(false);
    }
  }

  if (disabled) {
    return (
      <span className="text-xs text-ink-500">
        Révocation impossible — des tranches sont encore engagées dans un crédit.
      </span>
    );
  }

  if (!confirming) {
    return (
      <button
        onClick={() => setConfirming(true)}
        className={buttonClasses({ variant: "ghost", size: "sm" })}
      >
        Révoquer
      </button>
    );
  }

  return (
    <div className="flex gap-2">
      <button
        onClick={() => setConfirming(false)}
        className={buttonClasses({ variant: "ghost", size: "sm" })}
      >
        Annuler
      </button>
      <button
        onClick={onConfirm}
        disabled={submitting}
        className={buttonClasses({ variant: "secondary", size: "sm" })}
      >
        {submitting ? "…" : "Confirmer la révocation"}
      </button>
    </div>
  );
}


function TranchesSection({
  tranches,
  onChange,
  onError,
}: {
  tranches: LenderTranche[];
  onChange: (msg: string) => void;
  onError: (msg: string) => void;
}) {
  const [adding, setAdding] = useState(false);
  const [amount, setAmount] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function onAdd() {
    if (!amount) return;
    setSubmitting(true);
    try {
      await portalApi.lender.addTranche(Number(amount));
      onChange(`Tranche de ${formatXaf(amount)} créée.`);
      setAdding(false);
      setAmount("");
    } catch (err) {
      const apiErr = err as ApiError;
      onError(apiErr.detail ?? "Création impossible.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="rounded-md border border-line-200 bg-paper p-6">
      <div className="flex items-center justify-between">
        <h2 className="font-display text-lg font-medium text-ink-900">
          Mes tranches
        </h2>
        {!adding && (
          <button
            onClick={() => setAdding(true)}
            className={buttonClasses({ variant: "primary", size: "sm" })}
          >
            + Nouvelle tranche
          </button>
        )}
      </div>

      {adding && (
        <div className="mt-4 flex gap-2 rounded-md border border-line-200 bg-cream/40 p-3">
          <input
            type="number"
            min={100}
            step={1000}
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            placeholder="Montant (XAF)"
            className="flex-1 rounded-md border border-line-200 bg-paper px-3 py-2 text-sm text-ink-900 outline-none focus:border-blue-700 focus:ring-1 focus:ring-blue-700"
          />
          <button
            onClick={onAdd}
            disabled={submitting || !amount}
            className={buttonClasses({ variant: "success", size: "sm" })}
          >
            {submitting ? "…" : "Ajouter"}
          </button>
          <button
            onClick={() => {
              setAdding(false);
              setAmount("");
            }}
            className={buttonClasses({ variant: "ghost", size: "sm" })}
          >
            Annuler
          </button>
        </div>
      )}

      {tranches.length === 0 ? (
        <p className="mt-4 rounded-md border border-dashed border-line-200 px-4 py-6 text-center text-xs text-ink-500">
          Aucune tranche pour le moment.
        </p>
      ) : (
        <ul className="mt-4 divide-y divide-line-200 rounded-md border border-line-200">
          {tranches.map((t) => (
            <li
              key={t.id}
              className="flex items-center justify-between px-4 py-3"
            >
              <div>
                <p className="text-sm font-medium text-ink-900">
                  {formatXaf(t.montant)}
                </p>
                <p className="text-xs text-ink-500">
                  <TrancheBadge statut={t.statut} display={t.statut_display} />
                  {t.engaged_in_loan_id && (
                    <> · Crédit #{t.engaged_in_loan_id}</>
                  )}
                </p>
              </div>
              {/* La récupération d'une tranche est pilotée par l'ADMIN — le
                  membre place son argent délibérément et n'annule pas lui-même
                  ses tranches (il est seulement notifié). */}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}


function TrancheBadge({
  statut,
  display,
}: {
  statut: LenderTranche["statut"];
  display: string;
}) {
  const cls: Record<LenderTranche["statut"], string> = {
    disponible: "bg-emerald-100 text-emerald-700",
    engagee: "bg-terra-100 text-terra-700",
    liberee: "bg-blue-100 text-blue-700",
    annulee: "bg-stone-200 text-stone-700",
  };
  return (
    <span
      className={`inline-block rounded-full px-2 py-0.5 text-[10px] font-medium ${cls[statut]}`}
    >
      {display}
    </span>
  );
}


// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------


function RadioCard({
  checked,
  onClick,
  title,
  hint,
}: {
  checked: boolean;
  onClick: () => void;
  title: string;
  hint: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`block w-full rounded-md border p-3 text-left transition-colors ${
        checked
          ? "border-blue-700 bg-blue-50/40 ring-1 ring-blue-700"
          : "border-line-200 bg-paper hover:bg-cream"
      }`}
    >
      <div className="flex items-center gap-2">
        <span
          className={`inline-block size-3.5 rounded-full border ${
            checked
              ? "border-blue-700 bg-blue-700"
              : "border-ink-400 bg-paper"
          }`}
          aria-hidden="true"
        />
        <span className="text-sm font-medium text-ink-900">{title}</span>
      </div>
      <p className="ml-5.5 mt-1 text-xs text-ink-600">{hint}</p>
    </button>
  );
}


function Stat({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone: "emerald" | "terra" | "ink";
}) {
  const cls = {
    emerald: "text-emerald",
    terra: "text-terra-700",
    ink: "text-ink-900",
  }[tone];
  return (
    <div>
      <p className="font-medium uppercase tracking-wide text-ink-500">{label}</p>
      <p className={`mt-0.5 font-editorial text-base font-medium ${cls}`}>
        {formatXaf(value)}
      </p>
    </div>
  );
}


function Decimal(s: string): number {
  const n = parseFloat(s);
  return Number.isNaN(n) ? 0 : n;
}


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
