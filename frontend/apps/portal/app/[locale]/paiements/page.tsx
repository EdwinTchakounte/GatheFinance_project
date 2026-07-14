"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { Receipt } from "lucide-react";

import { Container, EmptyState, SkeletonList } from "@gathe/ui";

import { portalApi, type ApiError, type PaymentRead } from "@/lib/api";


function fmtAmount(value: string): string {
  const n = Number(value);
  if (!Number.isFinite(n)) return value;
  return n.toLocaleString("fr-FR");
}

function fmtDate(iso: string): string {
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

function statutBadge(statut: PaymentRead["statut"]): {
  bg: string;
  text: string;
  label: string;
} {
  switch (statut) {
    case "valide":
      return { bg: "bg-emerald-50", text: "text-emerald-700", label: "Validé" };
    case "rejete":
      return { bg: "bg-rose-50", text: "text-rose-700", label: "Rejeté" };
    default:
      return { bg: "bg-amber-50", text: "text-amber-700", label: "En attente" };
  }
}

/**
 * « Mes reçus de versement » — liste tous les versements du membre. Chaque ligne
 * permet de télécharger la mini-facture PDF GATHE. Parité avec l'écran mobile.
 */
export default function ReceiptsPage() {
  const router = useRouter();
  const [items, setItems] = useState<PaymentRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await portalApi.payments.me();
        if (!cancelled) setItems(res.results);
      } catch (err) {
        if (!cancelled) setError((err as ApiError).detail ?? "Chargement impossible.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <Container>
      <header className="border-b border-line-200 pb-6 pt-10">
        <button
          type="button"
          onClick={() => router.push("/")}
          className="text-sm text-ink-600 hover:text-blue-700"
        >
          ← Retour au tableau de bord
        </button>
        <h1 className="mt-3 font-editorial text-3xl font-medium text-ink-900">
          Mes reçus de versement
        </h1>
        <p className="mt-2 text-sm text-ink-600">
          Télécharge le reçu (PDF) de chaque versement effectué. Opérations les
          plus récentes d&apos;abord.
        </p>
      </header>

      <div className="py-6">
        {loading ? (
          <SkeletonList count={5} cardClassName="h-16" />
        ) : error ? (
          <p className="rounded-md border border-rose-200 bg-rose-50/60 p-3 text-sm text-rose-700">
            {error}
          </p>
        ) : items.length === 0 ? (
          <EmptyState
            icon={Receipt}
            title="Aucun versement pour l'instant"
            message="Dès que tu effectues un versement, tu pourras télécharger ici son reçu."
          />
        ) : (
          <ul className="divide-y divide-line-200 rounded-md border border-line-200 bg-paper">
            {items.map((p) => {
              const badge = statutBadge(p.statut);
              return (
                <li
                  key={p.id}
                  className="flex flex-wrap items-center justify-between gap-3 px-4 py-3.5"
                >
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-ink-900">
                      {p.type_display || "Versement"}
                    </p>
                    <p className="mt-0.5 text-xs text-ink-500">
                      {fmtDate(p.date_versement)} ·{" "}
                      <span
                        className={`rounded px-1.5 py-0.5 text-[11px] font-medium ${badge.bg} ${badge.text}`}
                      >
                        {badge.label}
                      </span>
                    </p>
                  </div>
                  <div className="flex items-center gap-4">
                    <span className="text-sm font-semibold text-ink-900">
                      {fmtAmount(p.montant)} XAF
                    </span>
                    <a
                      href={portalApi.payments.receiptUrl(p.id)}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 text-xs font-medium text-blue-700 hover:underline"
                    >
                      📄 Reçu
                    </a>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </Container>
  );
}
