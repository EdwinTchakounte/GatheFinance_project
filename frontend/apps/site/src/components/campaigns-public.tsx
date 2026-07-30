"use client";

import { useEffect, useState } from "react";

import { fmtDate, fmtXAF, type Campaign } from "@/lib/campaign-format";

export type { Campaign };

const inputCls =
  "mt-1 block w-full rounded-md border border-line-200 bg-paper px-3 py-2 text-ink-900 outline-none transition-colors focus:border-emerald focus:ring-1 focus:ring-emerald";

export function ApplyForm({ campaign }: { campaign: Campaign }) {
  const [form, setForm] = useState({
    nom: "",
    prenom: "",
    phone: "",
    email: "",
    montant: campaign.montant_min,
    motif: "",
  });
  const [state, setState] = useState<"idle" | "sending" | "done" | "error">("idle");
  const [error, setError] = useState<string | null>(null);
  const docsRequis = campaign.documents_requis ?? [];
  const [files, setFiles] = useState<Record<number, File | null>>({});

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (state === "sending") return;
    // Vérifie que chaque pièce exigée a bien un fichier sélectionné.
    const missing = docsRequis.findIndex((_, i) => !files[i]);
    if (docsRequis.length > 0 && missing !== -1) {
      setError(`Merci de joindre : ${docsRequis[missing]}.`);
      setState("error");
      return;
    }
    setState("sending");
    setError(null);
    try {
      let res: Response;
      if (docsRequis.length > 0) {
        const fd = new FormData();
        fd.append("campaign_id", String(campaign.id));
        Object.entries(form).forEach(([k, v]) => fd.append(k, String(v)));
        docsRequis.forEach((_, i) => {
          const f = files[i];
          if (f) fd.append(`doc_${i}`, f);
        });
        res = await fetch("/api/campaigns/apply", { method: "POST", body: fd });
      } else {
        res = await fetch("/api/campaigns/apply", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ campaign_id: campaign.id, ...form }),
        });
      }
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        setError(data?.detail ?? "Impossible d'envoyer ta candidature.");
        setState("error");
        return;
      }
      setState("done");
    } catch {
      setError("Réseau indisponible. Réessaie.");
      setState("error");
    }
  }

  if (state === "done") {
    return (
      <div className="rounded-md border border-emerald/40 bg-emerald/5 p-5 text-sm text-ink-700">
        ✓ Candidature envoyée. La coopérative l&apos;étudie et te recontactera
        par email. Si elle est acceptée, ton compte sera créé automatiquement
        (avec un lien pour définir ton mot de passe) — sans frais d&apos;adhésion.
      </div>
    );
  }

  return (
    <form onSubmit={submit} className="space-y-3">
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="block text-sm text-ink-700">
          Prénom
          <input
            required
            value={form.prenom}
            onChange={(e) => setForm({ ...form, prenom: e.target.value })}
            className={inputCls}
          />
        </label>
        <label className="block text-sm text-ink-700">
          Nom
          <input
            required
            value={form.nom}
            onChange={(e) => setForm({ ...form, nom: e.target.value })}
            className={inputCls}
          />
        </label>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="block text-sm text-ink-700">
          Téléphone
          <input
            required
            type="tel"
            value={form.phone}
            onChange={(e) => setForm({ ...form, phone: e.target.value })}
            className={inputCls}
            placeholder="6XX XX XX XX"
          />
        </label>
        <label className="block text-sm text-ink-700">
          Email
          <input
            required
            type="email"
            value={form.email}
            onChange={(e) => setForm({ ...form, email: e.target.value })}
            className={inputCls}
            placeholder="pour ton accès à l'app"
          />
        </label>
      </div>
      <label className="block text-sm text-ink-700">
        Montant souhaité (XAF)
        <input
          required
          type="number"
          min={Number(campaign.montant_min)}
          max={Number(campaign.montant_max)}
          value={form.montant}
          onChange={(e) => setForm({ ...form, montant: e.target.value })}
          className={inputCls}
        />
        <span className="mt-1 block text-xs text-ink-500">
          Entre {fmtXAF(campaign.montant_min)} et {fmtXAF(campaign.montant_max)}.
        </span>
      </label>
      <label className="block text-sm text-ink-700">
        Ton projet (facultatif)
        <textarea
          rows={3}
          value={form.motif}
          onChange={(e) => setForm({ ...form, motif: e.target.value })}
          className={inputCls}
        />
      </label>
      {docsRequis.length > 0 ? (
        <div className="space-y-2 rounded-md border border-line-200 bg-cream/50 p-3">
          <p className="text-xs font-semibold uppercase tracking-wide text-ink-600">
            Pièces justificatives à joindre
          </p>
          {docsRequis.map((label, i) => (
            <label key={i} className="block text-sm text-ink-700">
              {label}
              <input
                required
                type="file"
                accept="image/*,application/pdf"
                onChange={(e) =>
                  setFiles((prev) => ({ ...prev, [i]: e.target.files?.[0] ?? null }))
                }
                className="mt-1 block w-full text-xs text-ink-600 file:mr-3 file:rounded-md file:border-0 file:bg-emerald file:px-3 file:py-1.5 file:text-white"
              />
            </label>
          ))}
        </div>
      ) : null}
      {error ? (
        <p className="rounded-md border border-terra-400/40 bg-terra-50/60 px-3 py-2 text-sm text-terra-700">
          {error}
        </p>
      ) : null}
      <button
        type="submit"
        disabled={state === "sending"}
        className="w-full rounded-md bg-emerald px-4 py-2.5 text-sm font-semibold text-white transition-opacity hover:opacity-90 disabled:opacity-50"
      >
        {state === "sending" ? "Envoi…" : "Envoyer ma candidature"}
      </button>
    </form>
  );
}

export function CampaignsPublic() {
  const [items, setItems] = useState<Campaign[]>([]);
  const [loading, setLoading] = useState(true);
  const [openId, setOpenId] = useState<number | null>(null);

  useEffect(() => {
    fetch("/api/campaigns")
      .then((r) => r.json())
      .then((d) => setItems(Array.isArray(d?.results) ? d.results : []))
      .catch(() => setItems([]))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return <p className="text-center text-sm text-ink-500">Chargement…</p>;
  }
  if (items.length === 0) {
    return (
      <div className="rounded-md border border-dashed border-line-200 bg-paper/70 p-10 text-center">
        <p className="font-editorial text-lg font-medium text-ink-900">
          Aucune campagne ouverte pour le moment
        </p>
        <p className="mt-2 text-sm text-ink-600">
          Reviens plus tard, ou deviens membre pour accéder au crédit classique.
        </p>
      </div>
    );
  }

  return (
    <div className="grid gap-6 md:grid-cols-2">
      {items.map((c) => (
        <article
          key={c.id}
          className="flex flex-col overflow-hidden rounded-lg border border-line-200 bg-paper"
        >
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={c.flyer_url}
            alt={c.nom}
            loading="lazy"
            decoding="async"
            className="h-44 w-full object-cover"
          />
          <div className="flex flex-1 flex-col p-6">
            <span className="inline-block w-fit rounded-full bg-emerald/15 px-2.5 py-0.5 text-[11px] font-semibold uppercase tracking-wide text-emerald">
              {c.profil_cible || "Tous profils"}
            </span>
            <h3 className="mt-2 font-editorial text-xl font-medium text-ink-900">
              {c.nom}
            </h3>
            <p className="mt-2 text-sm text-ink-600">
              {fmtXAF(c.montant_min)} – {fmtXAF(c.montant_max)} ·{" "}
              {(Number(c.taux_interet) * 100).toFixed(0)} % · clôture le{" "}
              {fmtDate(c.date_fin)}
            </p>
            {openId === c.id ? (
              <div className="mt-5 border-t border-line-200 pt-5">
                <ApplyForm campaign={c} />
              </div>
            ) : (
              <button
                type="button"
                onClick={() => setOpenId(c.id)}
                className="mt-5 w-full rounded-md bg-emerald px-4 py-2.5 text-sm font-semibold text-white transition-opacity hover:opacity-90"
              >
                Postuler à cette campagne
              </button>
            )}
          </div>
        </article>
      ))}
    </div>
  );
}
