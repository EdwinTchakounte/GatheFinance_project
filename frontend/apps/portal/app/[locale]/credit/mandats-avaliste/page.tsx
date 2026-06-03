"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { Container, buttonClasses } from "@gathe/ui";

import {
  portalApi,
  type ApiError,
  type AvalisteMandat,
} from "@/lib/api";


/**
 * Refonte 2026 — LOT 18 — Mes mandats d'avaliste.
 *
 * Le membre connecté voit la liste des demandes de crédit pour lesquelles
 * il est désigné comme garant. Il peut accepter (engagement définitif, Q13)
 * ou refuser avec motif.
 */
export default function AvalisteMandatsPage() {
  const router = useRouter();
  const [items, setItems] = useState<AvalisteMandat[]>([]);
  const [pendingCount, setPendingCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [active, setActive] = useState<AvalisteMandat | null>(null);
  const [message, setMessage] = useState<{
    tone: "ok" | "err";
    text: string;
  } | null>(null);

  async function reload() {
    setLoading(true);
    try {
      await portalApi.primeCsrf();
      const data = await portalApi.loans.avalisteMandats.list();
      setItems(data.results);
      setPendingCount(data.pending);
    } catch (err) {
      const apiErr = err as ApiError;
      if (apiErr.status === 401 || apiErr.status === 403) {
        router.replace("/connexion");
        return;
      }
      setMessage({
        tone: "err",
        text: apiErr.detail ?? "Impossible de charger les mandats.",
      });
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    reload();
    /* eslint-disable-next-line react-hooks/exhaustive-deps */
  }, []);

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
            Mes mandats d'avaliste
          </h1>
          <p className="mt-2 text-sm text-ink-600">
            Des membres t'ont désigné(e) comme garant pour leur demande de
            crédit.{" "}
            {pendingCount > 0 && (
              <strong className="text-terra-700">
                {pendingCount} en attente de ta réponse.
              </strong>
            )}
          </p>
        </header>

        <div className="rounded-md border border-amber-200 bg-amber-50/60 p-4 text-sm text-amber-800">
          <p className="font-semibold">Engagement non-rétractable (Q13)</p>
          <p className="mt-1 text-xs">
            Une acceptation est <strong>définitive</strong>. Si le demandeur
            ne rembourse pas, ton épargne pourra être saisie en couverture.
            Refuse si tu n'es pas sûr·e — un refus se motive simplement.
          </p>
        </div>

        {message && (
          <div
            className={`mt-4 rounded-md border px-4 py-3 text-sm ${
              message.tone === "ok"
                ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                : "border-terra-400/40 bg-terra-50/60 text-terra-700"
            }`}
          >
            {message.text}
          </div>
        )}

        <section className="mt-6 space-y-3">
          {loading && (
            <p className="rounded-md border border-line-200 bg-paper p-8 text-center text-sm text-ink-600">
              Chargement…
            </p>
          )}
          {!loading && items.length === 0 && (
            <p className="rounded-md border border-dashed border-line-200 bg-paper p-8 text-center text-sm text-ink-600">
              Aucun mandat pour le moment.
            </p>
          )}
          {!loading &&
            items.map((m) => (
              <MandatCard
                key={m.id}
                mandat={m}
                onAction={() => setActive(m)}
              />
            ))}
        </section>

        {active && (
          <RespondModal
            mandat={active}
            onClose={() => setActive(null)}
            onDone={(text) => {
              setMessage({ tone: "ok", text });
              setActive(null);
              reload();
            }}
            onError={(text) => setMessage({ tone: "err", text })}
          />
        )}
      </Container>
    </main>
  );
}


function MandatCard({
  mandat,
  onAction,
}: {
  mandat: AvalisteMandat;
  onAction: () => void;
}) {
  const tone =
    mandat.statut === "pending"
      ? "border-terra-400/40 bg-terra-50/40"
      : mandat.statut === "accepted"
        ? "border-emerald-300/40 bg-emerald-50/40"
        : "border-line-200 bg-cream/40";
  return (
    <article className={`rounded-md border p-5 ${tone}`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-ink-900">
            {mandat.demandeur.prenom} {mandat.demandeur.nom}
            <span className="ml-2 text-xs font-medium text-ink-500">
              {mandat.demandeur.numero_membre}
            </span>
          </p>
          <p className="mt-1 text-xs text-ink-600">
            Demande : <strong>{formatXaf(mandat.loan_request.montant_demande)}</strong>{" "}
            sur {mandat.loan_request.duree_mois} mois — soumise le{" "}
            {formatDate(mandat.loan_request.date_soumission)}
          </p>
        </div>
        <StatutBadge statut={mandat.statut} display={mandat.statut_display} />
      </div>

      {mandat.loan_request.motif && (
        <p className="mt-3 rounded-md bg-paper px-3 py-2 text-xs italic text-ink-700">
          "{mandat.loan_request.motif}"
        </p>
      )}

      <dl className="mt-3 grid grid-cols-2 gap-2 text-xs">
        <Info label="Mon épargne (snapshot)" value={formatXaf(mandat.couverture.epargne_avaliste)} />
        <Info label="Épargne demandeur" value={formatXaf(mandat.couverture.epargne_borrower)} />
        <Info
          label="Couverture"
          value={`${(parseFloat(mandat.couverture.ratio) * 100).toFixed(0)} %`}
        />
        {mandat.responded_at && (
          <Info label="Répondu le" value={formatDate(mandat.responded_at)} />
        )}
      </dl>

      {mandat.refus_motif && (
        <p className="mt-3 rounded-md border border-line-200 bg-paper px-3 py-2 text-xs text-ink-600">
          <strong>Motif refus :</strong> {mandat.refus_motif}
        </p>
      )}

      {mandat.statut === "pending" && (
        <div className="mt-4 flex justify-end">
          <button
            onClick={onAction}
            className={buttonClasses({ variant: "primary", size: "sm" })}
          >
            Répondre
          </button>
        </div>
      )}
    </article>
  );
}


function StatutBadge({
  statut,
  display,
}: {
  statut: AvalisteMandat["statut"];
  display: string;
}) {
  const cls: Record<AvalisteMandat["statut"], string> = {
    pending: "bg-amber-100 text-amber-800",
    accepted: "bg-emerald-100 text-emerald-700",
    refused: "bg-stone-200 text-stone-700",
  };
  return (
    <span
      className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-medium ${cls[statut]}`}
    >
      {display}
    </span>
  );
}


// ---------------------------------------------------------------------------
// Respond modal — accept / refuse
// ---------------------------------------------------------------------------


function RespondModal({
  mandat,
  onClose,
  onDone,
  onError,
}: {
  mandat: AvalisteMandat;
  onClose: () => void;
  onDone: (msg: string) => void;
  onError: (msg: string) => void;
}) {
  const [action, setAction] = useState<"accept" | "refuse" | null>(null);
  const [motif, setMotif] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit() {
    if (!action) return;
    setSubmitting(true);
    try {
      const payload = { accept: action === "accept", motif };
      await portalApi.loans.avalisteMandats.respond(mandat.id, payload);
      onDone(
        action === "accept"
          ? `Mandat accepté — la demande passe en instruction.`
          : `Mandat refusé — le demandeur a été informé.`,
      );
    } catch (err) {
      const apiErr = err as ApiError;
      onError(apiErr.detail ?? "Impossible d'enregistrer ta réponse.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      className="fixed inset-0 z-50 flex items-center justify-center bg-ink-900/40 px-4"
    >
      <div className="w-full max-w-md rounded-md border border-line-200 bg-paper p-6 shadow-lg">
        <h2 className="font-display text-lg font-medium text-ink-900">
          Répondre au mandat
        </h2>
        <p className="mt-1 text-xs text-ink-600">
          Demande de {mandat.demandeur.prenom} {mandat.demandeur.nom} —{" "}
          {formatXaf(mandat.loan_request.montant_demande)} sur{" "}
          {mandat.loan_request.duree_mois} mois.
        </p>

        {!action && (
          <div className="mt-5 grid grid-cols-2 gap-2">
            <button
              onClick={() => setAction("accept")}
              className={buttonClasses({ variant: "success", size: "md", fullWidth: true })}
            >
              ✓ Accepter
            </button>
            <button
              onClick={() => setAction("refuse")}
              className={buttonClasses({ variant: "secondary", size: "md", fullWidth: true })}
            >
              ✗ Refuser
            </button>
          </div>
        )}

        {action === "accept" && (
          <div className="mt-5 space-y-3">
            <div className="rounded-md border border-amber-200 bg-amber-50/60 p-3 text-xs text-amber-800">
              Tu acceptes de garantir cette demande. <strong>Cette décision
              est définitive</strong> et te lie tant que le crédit n'est pas
              entièrement remboursé.
            </div>
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setAction(null)}
                className={buttonClasses({ variant: "ghost", size: "sm" })}
              >
                Annuler
              </button>
              <button
                onClick={onSubmit}
                disabled={submitting}
                className={buttonClasses({ variant: "success", size: "sm" })}
              >
                {submitting ? "Envoi…" : "Je confirme l'engagement"}
              </button>
            </div>
          </div>
        )}

        {action === "refuse" && (
          <div className="mt-5 space-y-3">
            <label className="block text-xs font-medium text-ink-700">
              Motif (optionnel, communiqué au demandeur)
              <textarea
                value={motif}
                onChange={(e) => setMotif(e.target.value)}
                className="mt-2 block w-full rounded-md border border-line-200 bg-paper px-3 py-2 text-sm text-ink-900 outline-none focus:border-blue-700 focus:ring-1 focus:ring-blue-700"
                rows={3}
                placeholder="Ex: capacité de garantie déjà engagée ailleurs…"
              />
            </label>
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setAction(null)}
                className={buttonClasses({ variant: "ghost", size: "sm" })}
              >
                Annuler
              </button>
              <button
                onClick={onSubmit}
                disabled={submitting}
                className={buttonClasses({ variant: "secondary", size: "sm" })}
              >
                {submitting ? "Envoi…" : "Confirmer le refus"}
              </button>
            </div>
          </div>
        )}

        {!action && (
          <div className="mt-4 text-right">
            <button
              onClick={onClose}
              className="text-xs text-ink-600 hover:text-ink-900"
            >
              Fermer
            </button>
          </div>
        )}
      </div>
    </div>
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
