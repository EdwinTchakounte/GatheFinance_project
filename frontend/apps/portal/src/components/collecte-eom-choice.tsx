"use client";

import { useEffect, useRef, useState } from "react";
import { Store, Smartphone, PiggyBank, Check } from "lucide-react";

import { portalApi, type EomChoice } from "@/lib/api";

const NETWORKS = ["MTN", "ORANGE"] as const;

type Props = {
  /** Choix courant + destination (depuis le snapshot épargne). */
  initialPreference: EomChoice;
  initialPhone: string;
  initialNetwork: string;
};

/**
 * Carte « Fin de mois — que faire de ta collecte ? » (parité mobile).
 *
 * Trois destinations pour le solde restituable (après la commission mensuelle) :
 *  - `cash` : retrait en espèces à l'agence (ligne au grand livre)
 *  - `mobile_money` : versement Mobile Money — le membre renseigne sa
 *    destination ; la coopérative exécute le transfert manuellement
 *  - `epargne` : bascule vers l'épargne classique
 */
export function CollecteEomChoice({
  initialPreference,
  initialPhone,
  initialNetwork,
}: Props) {
  const [pref, setPref] = useState<EomChoice>(initialPreference);
  const [phone, setPhone] = useState(initialPhone);
  const [network, setNetwork] = useState(
    NETWORKS.includes(initialNetwork as (typeof NETWORKS)[number])
      ? initialNetwork
      : "MTN",
  );
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savedTick, setSavedTick] = useState(false);

  // Debounce de l'auto-enregistrement Mobile Money : dès que le numéro et le
  // réseau sont valides on persiste sans attendre le bouton (parité avec le tap
  // immédiat cash/épargne). On passe les valeurs explicitement pour éviter de
  // lire un état périmé dans le callback différé.
  const momoTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => {
    return () => {
      if (momoTimer.current) clearTimeout(momoTimer.current);
    };
  }, []);

  async function persist(
    next: EomChoice,
    momo?: { phone: string; network: string },
  ) {
    setError(null);
    setSaving(true);
    try {
      await portalApi.setCollecteEomPreference(
        next === "mobile_money"
          ? {
              preference: next,
              payout_phone: (momo?.phone ?? phone).trim(),
              payout_network: momo?.network ?? network,
            }
          : { preference: next },
      );
      setPref(next);
      setSavedTick(true);
      window.setTimeout(() => setSavedTick(false), 2000);
    } catch (err) {
      const detail = (err as { detail?: string }).detail;
      setError(detail ?? "Impossible d'enregistrer ton choix.");
    } finally {
      setSaving(false);
    }
  }

  function selectMomo() {
    // On déplie le formulaire ; l'auto-enregistrement se déclenche dès que la
    // destination est complète (le numéro reste requis côté serveur).
    setPref("mobile_money");
    setError(null);
    // Parité « tap » : si une destination valide est DÉJÀ renseignée (numéro
    // pré-rempli inchangé), on persiste le choix immédiatement — sinon
    // autoSaveMomo n'attendrait qu'une édition et le choix ne serait jamais
    // enregistré côté serveur.
    autoSaveMomo(phone, network);
  }

  /** Auto-enregistre la destination Mobile Money quand elle est valide. */
  function autoSaveMomo(nextPhone: string, nextNetwork: string) {
    if (momoTimer.current) clearTimeout(momoTimer.current);
    const digits = nextPhone.replace(/\D/g, "");
    if (digits.length < 9 || !nextNetwork) return;
    momoTimer.current = setTimeout(() => {
      void persist("mobile_money", { phone: nextPhone, network: nextNetwork });
    }, 600);
  }

  return (
    <section className="mt-8 rounded-md border border-line-200 bg-paper p-6">
      <h3 className="font-editorial text-lg font-medium text-ink-900">
        Fin de mois — que faire de ta collecte ?
      </h3>
      <p className="mt-1 text-sm text-ink-600">
        À la clôture mensuelle, la coopérative retient sa commission. Choisis ce
        qui arrive au solde restituable.
      </p>

      <div className="mt-5 grid gap-3">
        <Option
          selected={pref === "cash"}
          disabled={saving}
          icon={<Store className="h-5 w-5" />}
          title="Retirer à l'agence"
          desc="Tu récupères ton solde en espèces au guichet."
          onClick={() => persist("cash")}
        />
        <Option
          selected={pref === "mobile_money"}
          disabled={saving}
          icon={<Smartphone className="h-5 w-5" />}
          title="Verser sur mon compte"
          desc="La coopérative t'envoie ton solde par Mobile Money."
          onClick={selectMomo}
        />

        {pref === "mobile_money" ? (
          <div className="rounded-md border border-line-200 bg-cream/60 p-4">
            <label className="block text-xs font-semibold text-ink-600">
              Numéro Mobile Money
            </label>
            <input
              type="tel"
              value={phone}
              onChange={(e) => {
                setPhone(e.target.value);
                autoSaveMomo(e.target.value, network);
              }}
              placeholder="Ex : 690 00 00 00"
              className="mt-1.5 w-full rounded-md border border-line-300 bg-paper px-3 py-2 text-sm text-ink-900 outline-none focus:border-blue-400"
            />
            <label className="mt-3 block text-xs font-semibold text-ink-600">
              Réseau
            </label>
            <div className="mt-1.5 flex gap-2">
              {NETWORKS.map((net) => (
                <button
                  key={net}
                  type="button"
                  onClick={() => {
                    setNetwork(net);
                    // Réseau = choix discret : on enregistre tout de suite si le
                    // numéro est déjà valide.
                    autoSaveMomo(phone, net);
                  }}
                  className={
                    "rounded-full px-4 py-1.5 text-sm font-medium transition " +
                    (network === net
                      ? "bg-blue-600 text-white"
                      : "bg-blue-50 text-blue-700 hover:bg-blue-100")
                  }
                >
                  {net}
                </button>
              ))}
            </div>
            <button
              type="button"
              disabled={saving || phone.trim().length === 0}
              onClick={() => persist("mobile_money")}
              className="mt-4 w-full rounded-md bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-blue-700 disabled:opacity-50"
            >
              {saving ? "Enregistrement…" : "Enregistrer ma destination"}
            </button>
          </div>
        ) : null}

        <Option
          selected={pref === "epargne"}
          disabled={saving}
          icon={<PiggyBank className="h-5 w-5" />}
          title="Basculer en épargne"
          desc="Ta collecte est virée sur ton épargne classique."
          onClick={() => persist("epargne")}
        />
      </div>

      {error ? <p className="mt-3 text-sm text-terra-700">{error}</p> : null}
      {savedTick ? (
        <p className="mt-3 flex items-center gap-1.5 text-sm text-emerald">
          <Check className="h-4 w-4" /> Choix enregistré.
        </p>
      ) : null}
    </section>
  );
}

function Option({
  selected,
  disabled,
  icon,
  title,
  desc,
  onClick,
}: {
  selected: boolean;
  disabled: boolean;
  icon: React.ReactNode;
  title: string;
  desc: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className={
        "flex items-center gap-3 rounded-md border p-3.5 text-left transition disabled:opacity-60 " +
        (selected
          ? "border-blue-400 bg-blue-50/60"
          : "border-line-200 bg-paper hover:border-line-300")
      }
    >
      <span
        className={
          "shrink-0 " + (selected ? "text-blue-600" : "text-ink-500")
        }
      >
        {icon}
      </span>
      <span className="flex-1">
        <span
          className={
            "block text-sm font-semibold " +
            (selected ? "text-blue-800" : "text-ink-900")
          }
        >
          {title}
        </span>
        <span className="block text-xs text-ink-600">{desc}</span>
      </span>
      {selected ? <Check className="h-5 w-5 shrink-0 text-blue-600" /> : null}
    </button>
  );
}
