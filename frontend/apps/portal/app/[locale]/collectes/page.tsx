"use client";

import { useCallback, useEffect, useState } from "react";

import { Container, buttonClasses } from "@gathe/ui";

import {
  portalApi,
  type ApiError,
  type SpecialCollectionSlot,
  type SpecialCollectionType,
} from "@/lib/api";

function inferNetwork(phone: string): "MTN" | "ORANGE" {
  const d = phone.replace(/\D/g, "");
  // Orange CM : 655-659, 69x ; sinon MTN par défaut.
  return /^(?:\+?237)?6(5[5-9]|9)/.test(d) ? "ORANGE" : "MTN";
}

function fmtXAF(v: string | number | null | undefined): string {
  return `${Math.round(Number(v ?? 0)).toLocaleString("fr-FR")} XAF`;
}

const META: Record<SpecialCollectionType, { label: string; hint: string }> = {
  caisse_scolaire: { label: "Caisse scolaire", hint: "Épargne dédiée à la scolarité" },
  tontine_alimentaire: { label: "Tontine alimentaire", hint: "Collecte alimentaire" },
};

export default function CollectesPage() {
  const [slots, setSlots] = useState<SpecialCollectionSlot[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    try {
      setSlots(await portalApi.specialCollections.mine());
    } catch (err) {
      setError((err as ApiError).detail ?? "Chargement impossible.");
    }
  }, []);

  useEffect(() => {
    reload();
  }, [reload]);

  return (
    <Container className="py-8">
      <header className="mb-6">
        <h1 className="font-editorial text-2xl text-ink-900">Collectes particulières</h1>
        <p className="mt-1 text-sm text-ink-600">
          Caisse scolaire et tontine alimentaire : demande une participation au cycle
          en cours, puis alimente ta collecte (Mobile Money ou depuis ton épargne).
        </p>
      </header>

      {error ? (
        <div className="mb-4 rounded-md border border-red-200 bg-red-50 px-4 py-2.5 text-sm text-red-700">
          {error}
        </div>
      ) : null}

      {slots === null ? (
        <p className="text-ink-500">Chargement…</p>
      ) : (
        <div className="grid gap-5 md:grid-cols-2">
          {slots.map((slot) => (
            <CollectionCard key={slot.type} slot={slot} onChanged={reload} onError={setError} />
          ))}
        </div>
      )}
    </Container>
  );
}

function CollectionCard({
  slot,
  onChanged,
  onError,
}: {
  slot: SpecialCollectionSlot;
  onChanged: () => void;
  onError: (m: string) => void;
}) {
  const meta = META[slot.type];
  const m = slot.membership;

  return (
    <section className="rounded-lg border border-line-200 bg-paper p-5">
      <h2 className="font-editorial text-lg text-ink-900">{meta.label}</h2>
      <p className="text-xs text-ink-500">{meta.hint}</p>

      {!slot.cycle || !slot.cycle.is_open ? (
        <p className="mt-4 rounded-md bg-cream px-3 py-3 text-sm text-ink-600">
          Aucun cycle en cours. La coopérative n’a pas encore ouvert de cycle pour cette
          collecte — reviens dès qu’un nouveau cycle sera lancé.
        </p>
      ) : m && m.statut === "valide" ? (
        <ActiveView slot={slot} onChanged={onChanged} onError={onError} />
      ) : m && m.statut === "en_attente" ? (
        <p className="mt-4 rounded-md bg-amber-50 px-3 py-3 text-sm text-amber-800">
          Ta demande pour « {slot.cycle.nom} » est en attente de validation par la
          coopérative. Tu pourras verser dès qu’elle sera validée.
        </p>
      ) : (
        <RequestForm slot={slot} onChanged={onChanged} onError={onError} previousRejet={m?.motif_rejet} />
      )}
    </section>
  );
}

function RequestForm({
  slot,
  onChanged,
  onError,
  previousRejet,
}: {
  slot: SpecialCollectionSlot;
  onChanged: () => void;
  onError: (m: string) => void;
  previousRejet?: string;
}) {
  const [objectif, setObjectif] = useState("");
  const [cible, setCible] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit() {
    if (!objectif.trim()) {
      onError("Décris ton objectif pour cette collecte.");
      return;
    }
    setBusy(true);
    try {
      const montantCible = Number(cible.replace(/\D/g, "")) || null;
      await portalApi.specialCollections.request({
        type: slot.type,
        objectif: objectif.trim(),
        montant_cible: montantCible,
      });
      onChanged();
    } catch (err) {
      onError((err as ApiError).detail ?? "Envoi impossible.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mt-4 space-y-3">
      {previousRejet ? (
        <p className="rounded-md bg-amber-50 px-3 py-2 text-xs text-amber-800">
          Demande précédente refusée : {previousRejet}
        </p>
      ) : null}
      <p className="text-sm text-ink-600">
        Cycle : <strong>{slot.cycle?.nom}</strong>. Envoie une demande pour participer.
      </p>
      <label className="block text-sm">
        <span className="mb-1 block text-xs font-semibold text-ink-600">Ton objectif</span>
        <textarea
          value={objectif}
          onChange={(e) => setObjectif(e.target.value)}
          rows={3}
          placeholder="Ex. réunir la scolarité de mes enfants pour la rentrée…"
          className="w-full rounded-md border border-line-300 px-3 py-2 text-sm"
        />
      </label>
      <label className="block text-sm">
        <span className="mb-1 block text-xs font-semibold text-ink-600">
          Montant cible (optionnel)
        </span>
        <input
          value={cible}
          onChange={(e) => setCible(e.target.value)}
          inputMode="numeric"
          placeholder="Ex. 150000"
          className="w-full rounded-md border border-line-300 px-3 py-2 text-sm"
        />
      </label>
      <button
        type="button"
        disabled={busy}
        onClick={submit}
        className={buttonClasses({ variant: "success", size: "md", fullWidth: true })}
      >
        {busy ? "Envoi…" : "Envoyer ma demande"}
      </button>
    </div>
  );
}

function ActiveView({
  slot,
  onChanged,
  onError,
}: {
  slot: SpecialCollectionSlot;
  onChanged: () => void;
  onError: (m: string) => void;
}) {
  const m = slot.membership!;
  const [tab, setTab] = useState<"verser" | "transferer">("verser");
  const [montant, setMontant] = useState("");
  const [phone, setPhone] = useState("");
  const [busy, setBusy] = useState(false);
  const [pending, setPending] = useState(false);

  async function verser() {
    const amount = Number(montant.replace(/\D/g, ""));
    if (!amount || amount < 1000) {
      onError("Montant minimum : 1 000 XAF.");
      return;
    }
    if (phone.replace(/\D/g, "").length < 8) {
      onError("Numéro Mobile Money invalide.");
      return;
    }
    setBusy(true);
    try {
      await portalApi.payments.init({
        type: slot.type,
        montant: amount,
        phone,
        network: inferNetwork(phone),
      });
      setPending(true);
    } catch (err) {
      onError((err as ApiError).detail ?? "Paiement impossible.");
    } finally {
      setBusy(false);
    }
  }

  async function transferer() {
    const amount = Number(montant.replace(/\D/g, ""));
    if (!amount || amount <= 0) {
      onError("Saisis un montant valide.");
      return;
    }
    setBusy(true);
    try {
      await portalApi.specialCollections.transfer({ type: slot.type, montant: amount });
      setMontant("");
      onChanged();
    } catch (err) {
      onError((err as ApiError).detail ?? "Transfert impossible.");
    } finally {
      setBusy(false);
    }
  }

  if (pending) {
    return (
      <div className="mt-4 rounded-md bg-emerald-50 px-3 py-3 text-sm text-emerald-800">
        Paiement initié. Confirme la demande sur ton téléphone (Mobile Money), puis
        rafraîchis pour voir ton solde mis à jour.
        <button
          type="button"
          onClick={() => {
            setPending(false);
            onChanged();
          }}
          className={buttonClasses({ variant: "ghost", size: "sm", fullWidth: true }) + " mt-3"}
        >
          Actualiser mon solde
        </button>
      </div>
    );
  }

  return (
    <div className="mt-4 space-y-3">
      <div className="rounded-md bg-cream px-3 py-3">
        <p className="text-xs text-ink-500">Solde ({slot.cycle?.nom})</p>
        <p className="text-xl font-semibold text-ink-900">{fmtXAF(m.solde)}</p>
        {m.montant_cible ? (
          <p className="text-xs text-ink-500">Objectif : {fmtXAF(m.montant_cible)}</p>
        ) : null}
      </div>

      <div className="flex gap-2">
        {(["verser", "transferer"] as const).map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => setTab(t)}
            className={
              "flex-1 rounded-md px-3 py-1.5 text-sm font-medium " +
              (tab === t ? "bg-emerald-700 text-white" : "border border-line-300 text-ink-700")
            }
          >
            {t === "verser" ? "Verser (Mobile Money)" : "Depuis mon épargne"}
          </button>
        ))}
      </div>

      <input
        value={montant}
        onChange={(e) => setMontant(e.target.value)}
        inputMode="numeric"
        placeholder="Montant (XAF)"
        className="w-full rounded-md border border-line-300 px-3 py-2 text-sm"
      />
      {tab === "verser" ? (
        <>
          <input
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            inputMode="tel"
            placeholder="Numéro Mobile Money (+237…)"
            className="w-full rounded-md border border-line-300 px-3 py-2 text-sm"
          />
          <button
            type="button"
            disabled={busy}
            onClick={verser}
            className={buttonClasses({ variant: "success", size: "md", fullWidth: true })}
          >
            {busy ? "Paiement…" : "Payer"}
          </button>
        </>
      ) : (
        <>
          <p className="text-xs text-ink-500">
            Prélevé sur ton épargne classique disponible, crédité immédiatement (sans frais).
          </p>
          <button
            type="button"
            disabled={busy}
            onClick={transferer}
            className={buttonClasses({ variant: "secondary", size: "md", fullWidth: true })}
          >
            {busy ? "Transfert…" : "Transférer"}
          </button>
        </>
      )}
    </div>
  );
}
