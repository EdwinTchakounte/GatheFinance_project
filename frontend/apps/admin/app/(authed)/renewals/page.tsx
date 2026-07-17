"use client";

import { useEffect, useState } from "react";
import { CheckCircle2, AlertTriangle, CalendarClock } from "lucide-react";

import { buttonClasses } from "@gathe/ui";

import { Modal } from "@/components/modal";
import { adminApi, type ApiError, type RenewalRow } from "@/lib/api";


/**
 * Refonte 2026 — LOT 5 — Renouvellements d'épargne classique.
 *
 * Queue des ``ClassicSavingsAccount`` en attente de paiement des frais de
 * ré-inscription. Action admin = "Encaisser frais" → appelle
 * ``renew_classic_savings_account`` (cycle++, nouvelle maturité, ACTIF).
 */
export default function RenewalsPage() {
  return <Inner />;
}

type StatutKey =
  | "en_attente_paiement"
  | "urgence"
  | "notifie"
  | "actif"
  | "archive";

function Inner() {
  const [filter, setFilter] = useState<StatutKey>("en_attente_paiement");
  const [items, setItems] = useState<RenewalRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [actingId, setActingId] = useState<number | null>(null);
  const [message, setMessage] = useState<{
    tone: "ok" | "err";
    text: string;
  } | null>(null);
  const [confirmTarget, setConfirmTarget] = useState<RenewalRow | null>(null);

  async function reload() {
    setLoading(true);
    try {
      adminApi.primeCsrf().catch(() => undefined);
      const data = await adminApi.renewals.list(filter);
      setItems(data.results);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    reload();
    /* eslint-disable-next-line react-hooks/exhaustive-deps */
  }, [filter]);

  async function onProcess(row: RenewalRow) {
    setActingId(row.id);
    try {
      const result = await adminApi.renewals.process(row.id);
      setMessage({
        tone: "ok",
        text: `Compte de ${row.member_prenom} ${row.member_nom} renouvelé (cycle ${result.cycle_courant}).`,
      });
      setConfirmTarget(null);
      await reload();
    } catch (err) {
      const apiErr = err as ApiError;
      setMessage({
        tone: "err",
        text: apiErr.detail ?? "Renouvellement impossible.",
      });
    } finally {
      setActingId(null);
    }
  }

  return (
    <main className="space-y-6 p-8">
      <header className="space-y-1">
        <h1 className="font-display text-2xl text-ink-900">
          Renouvellements épargne
        </h1>
        <p className="text-sm text-ink-500">
          Comptes d&apos;épargne classique dont la maturité 12 mois est
          atteinte. Encaissez les frais de ré-inscription pour démarrer un
          nouveau cycle.
        </p>
      </header>

      <div className="flex flex-wrap items-center gap-2">
        {(
          [
            ["en_attente_paiement", "À encaisser"],
            ["urgence", "Échéance ≤ 7j"],
            ["notifie", "Échéance ≤ 30j"],
            ["actif", "Actifs"],
            ["archive", "Archivés"],
          ] as const
        ).map(([key, label]) => (
          <button
            key={key}
            onClick={() => setFilter(key)}
            className={`rounded-full border px-4 py-1.5 text-sm transition ${
              filter === key
                ? "border-terra-600 bg-terra-50 text-terra-700"
                : "border-line-200 text-ink-500 hover:bg-paper-soft"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {message && (
        <div
          className={`rounded-lg border px-4 py-3 text-sm ${
            message.tone === "ok"
              ? "border-emerald-200 bg-emerald-50 text-emerald-700"
              : "border-red-200 bg-red-50 text-red-700"
          }`}
        >
          {message.text}
        </div>
      )}

      <section className="rounded-2xl border border-line-200 bg-paper">
        {loading && (
          <p className="px-6 py-12 text-center text-sm text-ink-500">
            Chargement…
          </p>
        )}
        {!loading && items.length === 0 && (
          <p className="px-6 py-12 text-center text-sm text-ink-500">
            Aucun compte avec ce statut.
          </p>
        )}
        {!loading && items.length > 0 && (
          <ul className="divide-y divide-line-200">
            {items.map((row) => (
              <li
                key={row.id}
                className="flex flex-wrap items-start gap-4 px-6 py-5"
              >
                <div className="flex-1 min-w-[280px] space-y-1.5">
                  <div className="flex flex-wrap items-center gap-2 text-sm font-semibold text-ink-900">
                    {row.member_prenom} {row.member_nom}
                    <span className="rounded-full bg-paper-soft px-2 py-0.5 text-xs font-medium text-ink-500">
                      {row.member_numero}
                    </span>
                    <StatusBadge statut={row.statut_renouvellement} />
                    <span className="rounded-full bg-paper-soft px-2 py-0.5 text-xs font-medium text-ink-500">
                      Cycle {row.cycle_courant}
                    </span>
                  </div>
                  <div className="flex flex-wrap items-center gap-3 text-xs text-ink-500">
                    <span className="inline-flex items-center gap-1">
                      <CalendarClock className="h-3.5 w-3.5" />
                      Maturité :{" "}
                      {row.date_prochaine_maturite
                        ? new Date(
                            row.date_prochaine_maturite,
                          ).toLocaleDateString("fr-FR")
                        : ""}
                    </span>
                    <span>
                      Solde :{" "}
                      <strong className="text-ink-900">
                        {formatXaf(row.solde)} FCFA
                      </strong>
                    </span>
                  </div>
                </div>

                {(row.statut_renouvellement === "en_attente_paiement" ||
                  row.statut_renouvellement === "urgence" ||
                  row.statut_renouvellement === "notifie") && (
                  <button
                    onClick={() => setConfirmTarget(row)}
                    disabled={actingId === row.id}
                    className={buttonClasses({
                      variant: "primary",
                      size: "sm",
                    })}
                  >
                    <CheckCircle2 className="mr-1 h-4 w-4" />
                    Encaisser frais
                  </button>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>

      {confirmTarget && (
        <ConfirmModal
          target={confirmTarget}
          onClose={() => setConfirmTarget(null)}
          onConfirm={() => onProcess(confirmTarget)}
          submitting={actingId === confirmTarget.id}
        />
      )}
    </main>
  );
}


function StatusBadge({ statut }: { statut: RenewalRow["statut_renouvellement"] }) {
  const cls: Record<RenewalRow["statut_renouvellement"], string> = {
    actif: "bg-emerald-100 text-emerald-700",
    notifie: "bg-amber-100 text-amber-700",
    urgence: "bg-orange-100 text-orange-700",
    en_attente_paiement: "bg-rose-100 text-rose-700",
    archive: "bg-stone-200 text-stone-700",
  };
  const label: Record<RenewalRow["statut_renouvellement"], string> = {
    actif: "Actif",
    notifie: "Rappel envoyé",
    urgence: "Urgent",
    en_attente_paiement: "À encaisser",
    archive: "Archivé",
  };
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${cls[statut]}`}
    >
      {statut === "urgence" || statut === "en_attente_paiement" ? (
        <AlertTriangle className="h-3 w-3" />
      ) : null}
      {label[statut]}
    </span>
  );
}


function ConfirmModal({
  target,
  onClose,
  onConfirm,
  submitting,
}: {
  target: RenewalRow;
  onClose: () => void;
  onConfirm: () => void;
  submitting: boolean;
}) {
  return (
    <Modal
      open
      onClose={onClose}
      title={`Encaisser frais de ${target.member_prenom} ${target.member_nom}`}
    >
      <p className="text-sm text-ink-700">
        Confirmer le paiement des frais de ré-inscription va :
      </p>
      <ul className="list-disc space-y-1 pl-5 text-sm text-ink-500">
        <li>Avancer le cycle (n°{target.cycle_courant + 1})</li>
        <li>Repousser la maturité de 12 mois (configurable)</li>
        <li>
          Écrire une ligne <em>FRAIS_RENOUVELLEMENT</em> dans le ledger
        </li>
        <li>
          Remettre le statut à <strong>Actif</strong>
        </li>
      </ul>
      <p className="text-xs text-ink-400">
        Le montant des frais est lu de <code>epargne.renewal_fee</code>{" "}
        (AppSetting).
      </p>
      <div className="flex justify-end gap-2 pt-3">
        <button
          onClick={onClose}
          className={buttonClasses({ variant: "ghost", size: "sm" })}
        >
          Annuler
        </button>
        <button
          onClick={onConfirm}
          disabled={submitting}
          className={buttonClasses({ variant: "primary", size: "sm" })}
        >
          {submitting ? "En cours…" : "Confirmer l'encaissement"}
        </button>
      </div>
    </Modal>
  );
}


function formatXaf(amount: string): string {
  const n = parseFloat(amount);
  if (Number.isNaN(n)) return amount;
  return Math.round(n).toLocaleString("fr-FR");
}
