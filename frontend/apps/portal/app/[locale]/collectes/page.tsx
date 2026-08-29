"use client";

import { useCallback, useEffect, useState } from "react";

import { Container, buttonClasses } from "@gathe/ui";

import {
  portalApi,
  type ApiError,
  type SpecialCollectionOpen,
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
  tontine_alimentaire: { label: "Tontine", hint: "Collecte de groupe (nom libre)" },
};

// Type de collecte → type de paiement du carnet dédié (payant, prérequis).
const CARNET_PAYMENT_TYPE: Record<
  SpecialCollectionType,
  "frais_carnet_tontine" | "frais_carnet_caisse"
> = {
  tontine_alimentaire: "frais_carnet_tontine",
  caisse_scolaire: "frais_carnet_caisse",
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
          Caisse scolaire et tontine : achète le carnet du type, demande
          à participer à une collecte, puis alimente-la (Mobile Money ou depuis ton
          épargne). Plusieurs collectes peuvent être ouvertes en même temps.
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

  return (
    <section className="rounded-lg border border-line-200 bg-paper p-5">
      <div className="flex items-start justify-between gap-2">
        <div>
          <h2 className="font-editorial text-lg text-ink-900">{meta.label}</h2>
          <p className="text-xs text-ink-500">{meta.hint}</p>
        </div>
        <span
          className={
            "rounded-full px-2 py-0.5 text-[11px] font-medium " +
            (slot.has_carnet
              ? "bg-emerald-100 text-emerald-700"
              : "bg-amber-100 text-amber-700")
          }
        >
          {slot.has_carnet ? "Carnet OK" : "Carnet requis"}
        </span>
      </div>

      {!slot.has_carnet ? (
        <BuyCarnet slot={slot} onChanged={onChanged} onError={onError} />
      ) : null}

      {slot.cycles.length === 0 ? (
        <p className="mt-4 rounded-md bg-cream px-3 py-3 text-sm text-ink-600">
          Aucune collecte en cours. La coopérative n’a pas encore ouvert de collecte
          de ce type — reviens dès qu’une nouvelle sera lancée.
        </p>
      ) : (
        <div className="mt-4 space-y-4">
          {slot.cycles.map((open) => (
            <CycleBlock
              key={open.cycle.id}
              type={slot.type}
              hasCarnet={slot.has_carnet}
              open={open}
              onChanged={onChanged}
              onError={onError}
            />
          ))}
        </div>
      )}
    </section>
  );
}

function BuyCarnet({
  slot,
  onChanged,
  onError,
}: {
  slot: SpecialCollectionSlot;
  onChanged: () => void;
  onError: (m: string) => void;
}) {
  const [phone, setPhone] = useState("");
  const [busy, setBusy] = useState(false);
  const [pending, setPending] = useState(false);

  async function buy() {
    if (phone.replace(/\D/g, "").length < 8) {
      onError("Numéro Mobile Money invalide.");
      return;
    }
    setBusy(true);
    try {
      // Montant omis : tarif officiel (FeeType) imposé par le serveur.
      await portalApi.payments.init({
        type: CARNET_PAYMENT_TYPE[slot.type],
        phone,
        network: inferNetwork(phone),
      });
      setPending(true);
    } catch (err) {
      onError((err as ApiError).detail ?? "Achat du carnet impossible.");
    } finally {
      setBusy(false);
    }
  }

  if (pending) {
    return (
      <div className="mt-3 rounded-md bg-emerald-50 px-3 py-3 text-sm text-emerald-800">
        Achat du carnet initié. Confirme sur ton téléphone, puis actualise.
        <button
          type="button"
          onClick={() => {
            setPending(false);
            onChanged();
          }}
          className={buttonClasses({ variant: "ghost", size: "sm", fullWidth: true }) + " mt-3"}
        >
          Actualiser
        </button>
      </div>
    );
  }

  return (
    <div className="mt-3 space-y-2 rounded-md border border-amber-200 bg-amber-50/50 px-3 py-3">
      <p className="text-xs text-amber-800">
        Tu dois d’abord acheter le carnet {META[slot.type].label.toLowerCase()} pour
        pouvoir verser. Ce carnet est distinct de ton carnet d’épargne / collecte.
      </p>
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
        onClick={buy}
        className={buttonClasses({ variant: "success", size: "sm", fullWidth: true })}
      >
        {busy ? "Achat…" : "Acheter le carnet"}
      </button>
    </div>
  );
}

function CycleBlock({
  type,
  hasCarnet,
  open,
  onChanged,
  onError,
}: {
  type: SpecialCollectionType;
  hasCarnet: boolean;
  open: SpecialCollectionOpen;
  onChanged: () => void;
  onError: (m: string) => void;
}) {
  const m = open.membership;

  return (
    <div className="rounded-md border border-line-200 p-3">
      <div className="flex items-baseline justify-between gap-2">
        <p className="font-medium text-ink-900">{open.cycle.nom}</p>
        {Number(open.cycle.montant_minimal ?? 0) > 0 ? (
          <span className="text-[11px] text-ink-500">
            min {fmtXAF(open.cycle.montant_minimal)}/versement
          </span>
        ) : null}
      </div>
      {open.cycle.description ? (
        <p className="mt-1 whitespace-pre-wrap text-xs text-ink-500">
          {open.cycle.description}
        </p>
      ) : null}

      {m && m.statut === "valide" ? (
        <ActiveView
          type={type}
          hasCarnet={hasCarnet}
          open={open}
          onChanged={onChanged}
          onError={onError}
        />
      ) : m && m.statut === "en_attente" ? (
        <p className="mt-3 rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-800">
          Ta demande est en attente de validation. Tu pourras verser dès qu’elle sera
          validée.
        </p>
      ) : (
        <RequestForm
          type={type}
          open={open}
          onChanged={onChanged}
          onError={onError}
          previousRejet={m?.motif_rejet}
        />
      )}
    </div>
  );
}

function RequestForm({
  type,
  open,
  onChanged,
  onError,
  previousRejet,
}: {
  type: SpecialCollectionType;
  open: SpecialCollectionOpen;
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
        type,
        cycle_id: open.cycle.id,
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
    <div className="mt-3 space-y-3">
      {previousRejet ? (
        <p className="rounded-md bg-amber-50 px-3 py-2 text-xs text-amber-800">
          Demande précédente refusée : {previousRejet}
        </p>
      ) : null}
      <label className="block text-sm">
        <span className="mb-1 block text-xs font-semibold text-ink-600">Ton objectif</span>
        <textarea
          value={objectif}
          onChange={(e) => setObjectif(e.target.value)}
          rows={2}
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
  type,
  hasCarnet,
  open,
  onChanged,
  onError,
}: {
  type: SpecialCollectionType;
  hasCarnet: boolean;
  open: SpecialCollectionOpen;
  onChanged: () => void;
  onError: (m: string) => void;
}) {
  const m = open.membership!;
  const minVersement = Number(open.cycle.montant_minimal ?? 0);
  const [tab, setTab] = useState<"verser" | "transferer">("verser");
  const [montant, setMontant] = useState("");
  const [phone, setPhone] = useState("");
  const [busy, setBusy] = useState(false);
  const [pending, setPending] = useState(false);

  function checkAmount(): number | null {
    const amount = Number(montant.replace(/\D/g, ""));
    const floor = Math.max(minVersement, 1000);
    if (!amount || amount < floor) {
      onError(`Montant minimum : ${floor.toLocaleString("fr-FR")} XAF.`);
      return null;
    }
    return amount;
  }

  async function verser() {
    const amount = checkAmount();
    if (amount === null) return;
    if (phone.replace(/\D/g, "").length < 8) {
      onError("Numéro Mobile Money invalide.");
      return;
    }
    setBusy(true);
    try {
      await portalApi.payments.init({
        type,
        cycle_id: open.cycle.id,
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
    const amount = checkAmount();
    if (amount === null) return;
    setBusy(true);
    try {
      await portalApi.specialCollections.transfer({
        type,
        cycle_id: open.cycle.id,
        montant: amount,
      });
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
      <div className="mt-3 rounded-md bg-emerald-50 px-3 py-3 text-sm text-emerald-800">
        Paiement initié. Confirme la demande sur ton téléphone (Mobile Money), puis
        actualise pour voir ton solde mis à jour.
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
    <div className="mt-3 space-y-3">
      <div className="rounded-md bg-cream px-3 py-3">
        <p className="text-xs text-ink-500">Mon solde</p>
        <p className="text-xl font-semibold text-ink-900">{fmtXAF(m.solde)}</p>
        {m.montant_cible ? (
          <p className="text-xs text-ink-500">Objectif : {fmtXAF(m.montant_cible)}</p>
        ) : null}
      </div>

      {!hasCarnet ? (
        <p className="rounded-md bg-amber-50 px-3 py-2 text-xs text-amber-800">
          Achète d’abord le carnet ci-dessus pour pouvoir verser.
        </p>
      ) : null}

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
            disabled={busy || !hasCarnet}
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
            disabled={busy || !hasCarnet}
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
