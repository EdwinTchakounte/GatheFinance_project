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
 * Espace prêteur (épargne-prêteur §6) — VUE LECTURE SEULE.
 *
 * Depuis 2026-07-24, le financement placement est piloté côté administrateur
 * (sélection manuelle des parts + crédit des intérêts automatique). Le membre
 * devient prêteur en plaçant son épargne via « Épargne › Placement » ; il n'y
 * a plus d'opt-in explicite, d'ajout de tranche ni de révocation en self-service
 * (parité avec le mobile, où l'écran de gestion a été retiré). Cette page
 * présente donc l'état de ses tranches et les intérêts perçus, en lecture seule.
 *
 * Rémunération : chaque prêteur perçoit un intérêt égal à un pourcentage fixé
 * par la coopérative (réglage `loans.lender.interest_rate`) appliqué au montant
 * qu'il a réellement prêté — versé au décaissement (retenue à la source) ou
 * réparti au fil des remboursements.
 */
export default function LenderPage() {
  const router = useRouter();
  const [state, setState] = useState<LenderState | null>(null);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState<{
    tone: "ok" | "err";
    text: string;
  } | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        await portalApi.primeCsrf();
        const data = await portalApi.lender.me();
        if (!cancelled) setState(data);
      } catch (err) {
        const apiErr = err as ApiError;
        if (apiErr.status === 401 || apiErr.status === 403) {
          router.replace("/connexion");
          return;
        }
        if (!cancelled) {
          setMessage({
            tone: "err",
            text: apiErr.detail ?? "Impossible de charger ton espace prêteur.",
          });
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
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
            En plaçant ton épargne, tu aides à financer les crédits de la
            coopérative. En retour, tu perçois un intérêt fixé par la
            coopérative sur les montants réellement prêtés.
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

        {!isActive ? (
          <InactiveBlock onPlace={() => router.push("/epargne")} />
        ) : (
          <ActiveLenderBlock state={state} />
        )}

        {/* Historique des intérêts perçus — parité avec le mobile. */}
        <div className="mt-5">
          <PayoutsSection />
        </div>
      </Container>
    </main>
  );
}


// ---------------------------------------------------------------------------
// Pas encore prêteur — orienter vers le placement (le seul point d'entrée)
// ---------------------------------------------------------------------------


function InactiveBlock({ onPlace }: { onPlace: () => void }) {
  return (
    <section className="rounded-md border border-line-200 bg-paper p-7">
      <h2 className="font-display text-xl font-medium text-ink-900">
        Devenir prêteur
      </h2>
      <p className="mt-2 text-sm text-ink-600">
        Tu deviens prêteur simplement en plaçant une partie de ton épargne
        classique en « Placement ». Le montant placé devient prêtable ; son
        engagement dans un crédit est géré par la coopérative, et les intérêts
        te sont crédités automatiquement sur ton compte épargne.
      </p>
      <button
        onClick={onPlace}
        className={
          buttonClasses({ variant: "success", size: "lg", fullWidth: true }) +
          " mt-5"
        }
      >
        Placer mon épargne
      </button>
    </section>
  );
}


// ---------------------------------------------------------------------------
// Membre prêteur actif — état lecture seule (totaux + tranches)
// ---------------------------------------------------------------------------


function ActiveLenderBlock({ state }: { state: LenderState }) {
  const consent = state.consent!;
  return (
    <div className="space-y-5">
      <section className="rounded-md border border-line-200 bg-paper p-6">
        <div>
          <h2 className="font-display text-lg font-medium text-ink-900">
            Ma convention prêteur
          </h2>
          <p className="mt-0.5 text-xs text-ink-600">
            Mode {consent.is_global ? "A (solde global)" : "B (tranches explicites)"}{" "}
            · signée le {formatDate(consent.convention_signed_at)}
          </p>
        </div>

        <dl className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-4 text-xs">
          <Stat label="Disponible" value={state.totals.disponible} tone="emerald" />
          <Stat label="Engagé" value={state.totals.engagee} tone="terra" />
          <Stat label="Libérée" value={state.totals.liberee} tone="ink" />
          <Stat label="Annulée" value={state.totals.annulee} tone="ink" />
        </dl>

        <p className="mt-4 rounded-md border border-blue-700/20 bg-cream p-3 text-[11px] text-ink-600">
          ℹ️ L'engagement et la restitution de tes tranches sont pilotés par la
          coopérative. Tu es notifié à chaque mouvement.
        </p>
      </section>

      {!consent.is_global && state.tranches.length > 0 && (
        <TranchesReadOnly tranches={state.tranches} />
      )}
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


function TranchesReadOnly({ tranches }: { tranches: LenderTranche[] }) {
  return (
    <section className="rounded-md border border-line-200 bg-paper p-6">
      <h2 className="font-display text-lg font-medium text-ink-900">
        Mes tranches
      </h2>
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
                {t.engaged_in_loan_id && <> · Crédit #{t.engaged_in_loan_id}</>}
              </p>
            </div>
          </li>
        ))}
      </ul>
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
