"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { Container } from "@gathe/ui";

import {
  portalApi,
  type ApiError,
  type SavingsTransaction,
} from "@/lib/api";


type TypeOp = "" | "depot" | "retrait" | "interet";


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


function typeBadge(typeOp: string): { bg: string; text: string; label: string } {
  switch (typeOp) {
    case "depot":
      return { bg: "bg-emerald-50", text: "text-emerald-700", label: "Dépôt" };
    case "retrait":
      return { bg: "bg-rose-50", text: "text-rose-700", label: "Retrait" };
    case "interet":
      return { bg: "bg-blue-50", text: "text-blue-700", label: "Intérêt" };
    // Distinction des intérêts prêteur (part 50% reversée par un crédit
    // financé sur le placement) vs intérêt classique épargne.
    case "interet_preteur":
      return { bg: "bg-emerald-50", text: "text-emerald-800", label: "Intérêt prêteur" };
    case "interet_placement":
      return { bg: "bg-blue-50", text: "text-blue-700", label: "Intérêt placement" };
    case "restitution_maturite":
      return { bg: "bg-blue-50", text: "text-blue-700", label: "Restitution maturité" };
    case "frais_renouvellement":
      return { bg: "bg-amber-50", text: "text-amber-700", label: "Frais renouvellement" };
    case "retrait_force":
      return { bg: "bg-rose-100", text: "text-rose-800", label: "Saisie crédit" };
    default:
      return { bg: "bg-line-100", text: "text-ink-700", label: typeOp };
  }
}


// Produit d'épargne — dissocié : cotisation collecte vs épargne classique.
// Chaque produit a son propre ledger (endpoint distinct côté backend).
type Product = "collecte" | "classique";

export default function SavingsHistoryPage() {
  const router = useRouter();
  const [items, setItems] = useState<SavingsTransaction[]>([]);
  const [count, setCount] = useState(0);
  const [page, setPage] = useState(1);
  const [hasNext, setHasNext] = useState(false);
  const [filter, setFilter] = useState<TypeOp>("");
  const [product, setProduct] = useState<Product>("collecte");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const fetcher =
        product === "classique"
          ? portalApi.classicSavingsTransactions
          : portalApi.savingsTransactions;
      const res = await fetcher({
        page,
        type_op: filter || undefined,
      });
      setItems(res.results);
      setCount(res.count);
      setHasNext(!!res.next);
    } catch (err) {
      const apiErr = err as ApiError;
      setError(apiErr.detail ?? "Chargement impossible.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, filter, product]);

  return (
    <Container>
      <header className="border-b border-line-200 pb-6 pt-10">
        <button
          type="button"
          onClick={() => router.push("/epargne")}
          className="text-sm text-ink-600 hover:text-blue-700"
        >
          ← Retour à mon épargne
        </button>
        <h1 className="mt-3 font-editorial text-3xl font-medium text-ink-900">
          Historique de mes transactions
        </h1>
        <p className="mt-2 text-sm text-ink-600">
          Deux produits dissociés : choisis le compte à consulter. Opérations les
          plus récentes d'abord.
        </p>

        {/* Sélecteur de produit — dissocie cotisation collecte / épargne classique */}
        <div className="mt-5 inline-flex rounded-md border border-line-200 bg-paper p-1">
          {([
            { v: "collecte", l: "Collecte" },
            { v: "classique", l: "Épargne classique" },
          ] as { v: Product; l: string }[]).map((opt) => {
            const active = product === opt.v;
            const activeCls =
              opt.v === "collecte"
                ? "bg-blue-700 text-white"
                : "bg-emerald text-white";
            return (
              <button
                key={opt.v}
                type="button"
                onClick={() => {
                  setProduct(opt.v);
                  setFilter("");
                  setPage(1);
                }}
                className={
                  "rounded px-3.5 py-1.5 text-sm font-medium transition-colors " +
                  (active ? activeCls : "text-ink-700 hover:text-blue-700")
                }
              >
                {opt.l}
              </button>
            );
          })}
        </div>
      </header>

      <section className="mt-8">
        <div className="mb-5 flex items-center justify-between gap-3">
          <div className="flex items-center gap-1 rounded-md border border-line-200 bg-paper p-1">
            {[
              { v: "", l: "Toutes" },
              { v: "depot", l: "Dépôts" },
              { v: "retrait", l: "Retraits" },
              { v: "interet", l: "Intérêts" },
            ].map((opt) => (
              <button
                key={opt.v || "all"}
                type="button"
                onClick={() => {
                  setFilter(opt.v as TypeOp);
                  setPage(1);
                }}
                className={
                  "rounded px-2.5 py-1 text-xs font-medium transition-colors " +
                  (filter === opt.v
                    ? "bg-blue-700 text-white"
                    : "text-ink-700 hover:text-blue-700")
                }
              >
                {opt.l}
              </button>
            ))}
          </div>
          <p className="text-xs text-ink-500">
            <span className="font-mono text-ink-900">{count}</span> opération
            {count > 1 ? "s" : ""}
          </p>
        </div>

        {error ? (
          <div className="mb-5 rounded-md border border-rose-300 bg-rose-50/60 px-4 py-2.5 text-sm text-rose-700">
            {error}
          </div>
        ) : null}

        {loading ? (
          <p className="rounded-md border border-dashed border-line-200 bg-paper/70 p-12 text-center text-sm text-ink-600">
            Chargement…
          </p>
        ) : items.length === 0 ? (
          <p className="rounded-md border border-dashed border-line-200 bg-paper/70 p-12 text-center text-sm text-ink-600">
            Aucune opération à afficher.
          </p>
        ) : (
          <div className="overflow-hidden rounded-md border border-line-200 bg-paper">
            <table className="w-full text-sm">
              <thead className="bg-line-100/50 text-xs uppercase tracking-wide text-ink-600">
                <tr>
                  <th className="px-3 py-2 text-left">Date</th>
                  <th className="px-3 py-2 text-left">Type</th>
                  <th className="px-3 py-2 text-right">Montant</th>
                  <th className="px-3 py-2 text-right">Solde après</th>
                </tr>
              </thead>
              <tbody>
                {items.map((tx) => {
                  const badge = typeBadge(tx.type_op);
                  const isCredit =
                    tx.type_op === "depot" || tx.type_op === "interet";
                  return (
                    <tr key={tx.id} className="border-t border-line-200">
                      <td className="px-3 py-2 text-ink-700">{fmtDate(tx.date)}</td>
                      <td className="px-3 py-2">
                        <span
                          className={
                            "inline-block rounded-full px-2 py-0.5 text-[10px] font-medium " +
                            `${badge.bg} ${badge.text}`
                          }
                        >
                          {badge.label}
                        </span>
                      </td>
                      <td
                        className={
                          "px-3 py-2 text-right font-mono " +
                          (isCredit ? "text-emerald-700" : "text-rose-700")
                        }
                      >
                        {isCredit ? "+" : "−"}
                        {fmtAmount(tx.montant)} XAF
                      </td>
                      <td className="px-3 py-2 text-right font-mono text-ink-900">
                        {fmtAmount(tx.solde_apres)} XAF
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {!loading && (page > 1 || hasNext) ? (
          <div className="mt-5 flex items-center justify-between">
            <button
              type="button"
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1}
              className="rounded-md border border-line-200 bg-paper px-3 py-2 text-xs font-medium text-ink-700 hover:border-blue-700 hover:text-blue-700 disabled:cursor-not-allowed disabled:opacity-40"
            >
              ← Précédent
            </button>
            <p className="text-xs text-ink-500">
              Page <span className="font-mono">{page}</span>
            </p>
            <button
              type="button"
              onClick={() => setPage((p) => p + 1)}
              disabled={!hasNext}
              className="rounded-md border border-line-200 bg-paper px-3 py-2 text-xs font-medium text-ink-700 hover:border-blue-700 hover:text-blue-700 disabled:cursor-not-allowed disabled:opacity-40"
            >
              Suivant →
            </button>
          </div>
        ) : null}
      </section>
    </Container>
  );
}
