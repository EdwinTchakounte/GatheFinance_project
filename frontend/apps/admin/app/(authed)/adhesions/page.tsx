"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import { adminApi, type AdhesionPipeline, type ApiError } from "@/lib/api";


function formatXAF(s: string): string {
  return Number(s).toLocaleString("fr-FR") + " XAF";
}


export default function AdhesionsPipelinePage() {
  const [data, setData] = useState<AdhesionPipeline | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    adminApi.adhesions
      .pipeline()
      .then((res) => { if (!cancelled) setData(res); })
      .catch((err: ApiError) => {
        if (!cancelled) setError(err.detail ?? "Impossible de charger le pipeline.");
      })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, []);

  if (loading) return <p className="text-sm text-ink-600">Chargement…</p>;
  if (error) return <p className="rounded-lg border border-terra-400/40 bg-terra-50/60 p-3 text-sm text-terra-700">{error}</p>;
  if (!data) return null;

  const f = data.funnel;

  return (
    <div className="space-y-8">
      <header>
        <p className="font-display text-[0.7rem] font-semibold uppercase tracking-[0.18em] text-blue-700">
          Adhésions · Pipeline
        </p>
        <h1 className="mt-2 font-editorial text-2xl font-medium text-ink-900 sm:text-3xl">
          Suivi des adhésions
        </h1>
        <p className="mt-1 text-sm text-ink-600">
          De la demande publique à l'activation complète des 3 frais (Article 3).
        </p>
      </header>

      {/* ─── KPIs funnel ─── */}
      <section>
        <h2 className="mb-3 font-display text-[0.7rem] font-semibold uppercase tracking-[0.18em] text-ink-600">
          Funnel
        </h2>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Kpi
            tone="amber"
            label="En attente d'entretien"
            value={f.requests_en_attente}
            hint="MembershipRequest statut en_attente"
            href="/membership-requests?statut=en_attente"
          />
          <Kpi
            tone="blue"
            label="Approuvés, paiement en cours"
            value={f.requests_approved_pending_payment}
            hint="Member SUSPENDU, attend les 3 frais"
            href="#suspendus"
          />
          <Kpi
            tone="emerald"
            label="Membres actifs"
            value={f.members_actifs}
            hint="3 frais payés → Member ACTIF"
            href="/members?statut=actif"
          />
          <Kpi
            tone="ink"
            label="Bénéficiaires temporaires"
            value={f.members_temporaires}
            hint="Voie campagne — accès limité"
            href="/members?statut=temporaire"
          />
        </div>

        <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <Mini label="Demandes rejetées" value={f.requests_rejected} />
          <Mini label="Membres radiés" value={f.members_radies} />
          <div className="flex items-center justify-between rounded-xl border border-blue-200 bg-blue-50/40 px-4 py-3">
            <div>
              <p className="text-xs uppercase tracking-wide text-blue-800">
                À encaisser sur SUSPENDU
              </p>
              <p className="mt-1 font-editorial text-lg font-semibold text-blue-900">
                {formatXAF(data.expected_revenue.total_remaining_from_suspended)}
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* ─── Diagramme funnel visuel ─── */}
      <section>
        <h2 className="mb-3 font-display text-[0.7rem] font-semibold uppercase tracking-[0.18em] text-ink-600">
          Parcours d'un membre
        </h2>
        <div className="overflow-x-auto rounded-xl border border-line-200 bg-paper p-4 shadow-sm">
          <div className="flex min-w-[640px] items-center gap-2 text-xs">
            <Step
              n={1}
              label="Soumission"
              detail={`${f.requests_en_attente} en attente`}
              tone="amber"
            />
            <Chev />
            <Step
              n={2}
              label="Entretien (Art. 3)"
              detail="Guard admin"
              tone="amber"
            />
            <Chev />
            <Step
              n={3}
              label="Approbation"
              detail={`${f.requests_approved_pending_payment} SUSPENDU`}
              tone="blue"
            />
            <Chev />
            <Step
              n={4}
              label="Paiement 3 frais"
              detail="Adhésion + Inscription + Carnet"
              tone="blue"
            />
            <Chev />
            <Step
              n={5}
              label="Membre actif"
              detail={`${f.members_actifs} ACTIF`}
              tone="emerald"
            />
          </div>
        </div>
      </section>

      {/* ─── Table membres SUSPENDU ─── */}
      <section id="suspendus">
        <div className="mb-3 flex items-baseline justify-between">
          <h2 className="font-display text-[0.7rem] font-semibold uppercase tracking-[0.18em] text-ink-600">
            Membres SUSPENDU — progression des frais
          </h2>
          <span className="text-xs text-ink-500">
            {data.suspended_members.length} membre{data.suspended_members.length > 1 ? "s" : ""}
          </span>
        </div>

        {data.suspended_members.length === 0 ? (
          <p className="rounded-xl border border-line-200 bg-paper p-8 text-center text-sm text-ink-500">
            Aucun membre SUSPENDU. Tous les approuvés ont payé leurs frais.
          </p>
        ) : (
          <div className="overflow-x-auto rounded-xl border border-line-200 bg-paper shadow-sm">
            <table className="w-full text-sm">
              <thead className="bg-cream/60 text-xs uppercase tracking-wide text-ink-600">
                <tr>
                  <th className="px-4 py-3 text-left">Membre</th>
                  <th className="px-4 py-3 text-left">Contact</th>
                  <th className="px-4 py-3 text-left">Progression</th>
                  <th className="px-4 py-3 text-left">Frais</th>
                  <th className="px-4 py-3 text-right">Reste</th>
                  <th className="px-4 py-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line-200">
                {data.suspended_members.map((m) => {
                  const pct = m.fees_total > 0 ? Math.round((m.fees_paid_count / m.fees_total) * 100) : 0;
                  return (
                    <tr key={m.member_id} className="hover:bg-cream/30">
                      <td className="px-4 py-3">
                        <p className="font-medium text-ink-900">{m.prenom} {m.nom}</p>
                        <p className="font-mono text-xs text-ink-500">{m.numero_membre}</p>
                      </td>
                      <td className="px-4 py-3 text-ink-700">
                        <p className="truncate text-xs">{m.email || "—"}</p>
                        <p className="text-xs text-ink-500">{m.phone || "—"}</p>
                      </td>
                      <td className="px-4 py-3">
                        <p className="text-xs font-medium text-ink-700">
                          {m.fees_paid_count} / {m.fees_total} frais
                        </p>
                        <div className="mt-1.5 h-1.5 w-32 overflow-hidden rounded-full bg-line-200">
                          <div
                            className={`h-full rounded-full transition-all ${
                              pct === 100 ? "bg-emerald-500" : pct >= 66 ? "bg-blue-500" : pct >= 33 ? "bg-amber-500" : "bg-terra-500"
                            }`}
                            style={{ width: `${pct}%` }}
                          />
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex flex-wrap gap-1">
                          {m.fees_status.map((fee) => (
                            <span
                              key={fee.code}
                              className={`inline-flex items-center rounded-full px-2 py-0.5 text-[0.65rem] font-medium ring-1 ring-inset ${
                                fee.statut === "valide"
                                  ? "bg-emerald-50 text-emerald-700 ring-emerald-200"
                                  : "bg-line-100 text-ink-500 ring-line-200"
                              }`}
                            >
                              {fee.label}
                            </span>
                          ))}
                        </div>
                      </td>
                      <td className="px-4 py-3 text-right">
                        <p className="font-mono text-sm font-semibold text-ink-900">
                          {Number(m.amount_remaining).toLocaleString("fr-FR")} XAF
                        </p>
                        <p className="text-xs text-ink-500">
                          /{Number(m.amount_target).toLocaleString("fr-FR")}
                        </p>
                      </td>
                      <td className="px-4 py-3 text-right">
                        {m.email ? (
                          <a
                            href={`mailto:${m.email}?subject=${encodeURIComponent("Rappel des frais d'adhésion - Gathé Finance")}&body=${encodeURIComponent(
                              `Bonjour ${m.prenom} ${m.nom},\n\nNous notons que vous n'avez pas encore complété le paiement de vos frais d'adhésion (${Number(m.amount_remaining).toLocaleString("fr-FR")} XAF restants).\n\nVotre compte deviendra actif dès que les 3 frais (adhésion + inscription + carnet) seront réglés via l'app mobile ou le portail.\n\nL'équipe Gathé Finance`,
                            )}`}
                            className="rounded-lg bg-blue-700 px-3 py-1.5 text-xs font-semibold text-white hover:bg-blue-800"
                          >
                            Relancer
                          </a>
                        ) : (
                          <span className="text-xs text-ink-500">—</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}


function Kpi({
  tone, label, value, hint, href,
}: {
  tone: "amber" | "blue" | "emerald" | "ink";
  label: string;
  value: number;
  hint: string;
  href: string;
}) {
  const TONES: Record<string, string> = {
    amber: "border-amber-200 bg-amber-50/40 text-amber-900",
    blue: "border-blue-200 bg-blue-50/40 text-blue-900",
    emerald: "border-emerald-200 bg-emerald-50/40 text-emerald-900",
    ink: "border-line-200 bg-paper text-ink-900",
  };
  return (
    <Link
      href={href}
      className={`block rounded-xl border p-4 transition-all hover:shadow ${TONES[tone]}`}
    >
      <p className="text-xs font-semibold uppercase tracking-wide opacity-70">{label}</p>
      <p className="mt-2 font-editorial text-3xl font-semibold">{value}</p>
      <p className="mt-1 text-xs opacity-60">{hint}</p>
    </Link>
  );
}

function Mini({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-xl border border-line-200 bg-paper p-3">
      <p className="text-xs uppercase tracking-wide text-ink-500">{label}</p>
      <p className="mt-1 font-editorial text-lg font-semibold text-ink-900">{value}</p>
    </div>
  );
}

function Step({
  n, label, detail, tone,
}: {
  n: number;
  label: string;
  detail: string;
  tone: "amber" | "blue" | "emerald";
}) {
  const TONES: Record<string, string> = {
    amber: "bg-amber-50 ring-amber-200 text-amber-900",
    blue: "bg-blue-50 ring-blue-200 text-blue-900",
    emerald: "bg-emerald-50 ring-emerald-200 text-emerald-900",
  };
  return (
    <div className={`flex flex-1 min-w-[100px] flex-col items-start rounded-lg px-3 py-2.5 ring-1 ring-inset ${TONES[tone]}`}>
      <span className="text-[0.65rem] font-mono opacity-70">étape {n}</span>
      <span className="text-xs font-semibold">{label}</span>
      <span className="mt-0.5 text-[0.65rem] opacity-70">{detail}</span>
    </div>
  );
}

function Chev() {
  return <span className="text-ink-400" aria-hidden>→</span>;
}
