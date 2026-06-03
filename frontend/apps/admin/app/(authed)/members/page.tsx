"use client";

import { useEffect, useState } from "react";
import { Mail, Phone, Search } from "lucide-react";

import { adminApi, type ApiError, type Member } from "@/lib/api";


type StatutFilter = "" | "actif" | "suspendu" | "radie";


export default function MembersPage() {
  return (
    
      <Inner />
    
  );
}


function Inner() {
  const [statut, setStatut] = useState<StatutFilter>("");
  const [q, setQ] = useState("");
  const [items, setItems] = useState<Member[]>([]);
  const [count, setCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function reload() {
    setLoading(true);
    setError(null);
    try {
      const res = await adminApi.members.list({
        statut: statut || undefined,
        q: q.trim() || undefined,
      });
      setItems(res.results);
      setCount(res.count);
    } catch (err) {
      const apiErr = err as ApiError;
      setError(apiErr.detail ?? "Chargement impossible.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [statut]);

  return (
    <div className="px-8 py-8 lg:px-12 lg:py-10">
      <header className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="font-display text-[0.7rem] font-semibold uppercase tracking-[0.18em] text-terra-600">
            Membres
          </p>
          <h1 className="mt-2 font-editorial text-3xl font-medium text-ink-900">
            Annuaire des membres
          </h1>
          <p className="mt-1 text-sm text-ink-600">
            Liste filtrable et recherchable du registre des membres.
          </p>
        </div>

        <div className="flex items-center gap-3 text-sm text-ink-600">
          <span className="font-mono text-ink-900 font-medium">{count}</span>
          <span>membre{count > 1 ? "s" : ""} (vue actuelle)</span>
        </div>
      </header>

      <div className="mb-5 grid grid-cols-1 gap-3 md:grid-cols-[auto_1fr]">
        <div className="flex items-center gap-2">
          <span className="text-[0.65rem] font-semibold uppercase tracking-wider text-ink-500">
            Statut
          </span>
          <div className="flex items-center gap-1 rounded-md border border-line-200 bg-paper p-1">
            {[
              { v: "", l: "Tous" },
              { v: "actif", l: "Actifs" },
              { v: "suspendu", l: "Suspendus" },
              { v: "radie", l: "Radiés" },
            ].map((opt) => (
              <button
                key={opt.v || "all"}
                type="button"
                onClick={() => setStatut(opt.v as StatutFilter)}
                className={[
                  "rounded px-2.5 py-1 text-xs font-medium transition-colors",
                  statut === opt.v
                    ? "bg-blue-700 text-white"
                    : "text-ink-700 hover:text-blue-700",
                ].join(" ")}
              >
                {opt.l}
              </button>
            ))}
          </div>
        </div>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            reload();
          }}
          className="flex items-center gap-2"
        >
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-ink-400" />
            <input
              type="search"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Recherche (n° membre, nom, prénom, téléphone, email)"
              className="w-full rounded-md border border-line-200 bg-paper py-2 pl-9 pr-3 text-sm placeholder:text-ink-400 focus:border-blue-700 focus:outline-none focus:ring-1 focus:ring-blue-700"
            />
          </div>
          <button
            type="submit"
            className="rounded-md border border-line-200 bg-paper px-3 py-2 text-xs font-medium text-ink-700 hover:border-blue-700 hover:text-blue-700"
          >
            Rechercher
          </button>
        </form>
      </div>

      {error ? (
        <div className="mb-5 rounded-md border border-terra-400/40 bg-terra-50/60 px-4 py-2.5 text-sm text-terra-700">
          {error}
        </div>
      ) : null}

      {loading ? (
        <p className="text-ink-600">Chargement…</p>
      ) : items.length === 0 ? (
        <p className="rounded-md border border-dashed border-line-200 bg-paper/70 p-12 text-center text-sm text-ink-600">
          Aucun membre ne correspond à ces filtres.
        </p>
      ) : (
        <div className="overflow-hidden rounded-md border border-line-200 bg-paper">
          <table className="table-admin">
            <thead>
              <tr>
                <th>N° membre</th>
                <th>Membre</th>
                <th>Contact</th>
                <th>Statut</th>
                <th>Adhésion</th>
              </tr>
            </thead>
            <tbody>
              {items.map((m) => (
                <tr key={m.id}>
                  <td className="font-mono text-sm font-medium text-ink-900">
                    {m.numero_membre}
                  </td>
                  <td>
                    <p className="font-medium text-ink-900">
                      {m.prenom} {m.nom}
                    </p>
                  </td>
                  <td className="space-y-1">
                    {m.email ? (
                      <p className="flex items-center gap-1.5 text-sm text-ink-700">
                        <Mail className="size-3.5 text-ink-400" aria-hidden="true" />
                        {m.email}
                      </p>
                    ) : null}
                    {m.phone ? (
                      <p className="flex items-center gap-1.5 text-xs text-ink-600">
                        <Phone className="size-3 text-ink-400" aria-hidden="true" />
                        {m.phone}
                      </p>
                    ) : null}
                  </td>
                  <td>
                    <div className="flex flex-wrap items-center gap-1">
                      <span
                        className={
                          "pill " +
                          (m.statut === "actif"
                            ? "pill-success"
                            : m.statut === "suspendu"
                              ? "pill-warning"
                              : "pill-muted")
                        }
                      >
                        {m.statut_display}
                      </span>
                      {/* Refonte 2026 — badges BRC + ancienneté. */}
                      {m.is_brc_member ? (
                        <span
                          className="pill pill-success"
                          title={
                            m.brc_validated_at
                              ? `Validé le ${new Date(m.brc_validated_at).toLocaleDateString("fr-FR")}`
                              : "Statut BRC validé"
                          }
                        >
                          BRC
                        </span>
                      ) : null}
                      {m.is_senior ? (
                        <span
                          className="pill pill-muted"
                          title={`Ancienneté ${m.seniority_months ?? "?"} mois`}
                        >
                          Ancien
                        </span>
                      ) : null}
                    </div>
                  </td>
                  <td className="whitespace-nowrap text-sm text-ink-600">
                    {new Date(m.date_adhesion).toLocaleDateString("fr-FR", {
                      day: "2-digit",
                      month: "short",
                      year: "numeric",
                    })}
                    {typeof m.seniority_months === "number" ? (
                      <span className="ml-1 text-xs text-ink-400">
                        ({m.seniority_months} m.)
                      </span>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {!loading && count > items.length ? (
        <p className="mt-4 text-xs text-ink-500">
          Vue limitée aux {items.length} entrées les plus récentes sur {count}.
          Affine via le filtre statut ou la recherche.
        </p>
      ) : null}
    </div>
  );
}
