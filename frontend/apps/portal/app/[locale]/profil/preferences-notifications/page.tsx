"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { Container } from "@gathe/ui";


// P4 . Parite mobile NotifCategory / NotifChannel.
// Les preferences sont stockees localement (localStorage) cote portail comme
// cote mobile (SharedPreferences). Comportement : si toggle off, l'app
// n'affiche pas la notif in-app pour cette categorie. Email backend continue
// (controle par EventConfig.active cote admin).
type Category = "epargne" | "credit" | "carnet" | "reconduction" | "securite";
type Channel = "push" | "email" | "sms";


const CATEGORIES: { key: Category; label: string; subtitle: string }[] = [
  {
    key: "epargne",
    label: "Épargne",
    subtitle: "Dépôts validés, intérêts crédités, alertes solde.",
  },
  {
    key: "credit",
    label: "Crédit",
    subtitle: "Demande, décision comité, décaissement, échéances.",
  },
  {
    key: "carnet",
    label: "Carnet",
    subtitle: "Commande, retrait à l'agence.",
  },
  {
    key: "reconduction",
    label: "Reconduction",
    subtitle: "Comité, frais à régler, validation.",
  },
  {
    key: "securite",
    label: "Sécurité",
    subtitle: "Connexions, changements de mot de passe, accès suspects.",
  },
];

const CHANNELS: { key: Channel; label: string }[] = [
  { key: "push", label: "Notifications in-app" },
  { key: "email", label: "Email" },
  { key: "sms", label: "SMS" },
];


function storageKey(cat: Category, chan: Channel): string {
  return `notif_pref_${cat}_${chan}`;
}


function readPref(cat: Category, chan: Channel): boolean {
  if (typeof window === "undefined") return true;
  const v = window.localStorage.getItem(storageKey(cat, chan));
  return v === null ? true : v === "true";
}


function writePref(cat: Category, chan: Channel, value: boolean): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(storageKey(cat, chan), value ? "true" : "false");
}


export default function NotificationPreferencesPage() {
  const router = useRouter();
  const [prefs, setPrefs] = useState<Record<string, boolean>>({});
  const [flash, setFlash] = useState<string | null>(null);

  useEffect(() => {
    const initial: Record<string, boolean> = {};
    for (const cat of CATEGORIES) {
      for (const chan of CHANNELS) {
        initial[`${cat.key}_${chan.key}`] = readPref(cat.key, chan.key);
      }
    }
    setPrefs(initial);
  }, []);

  function onToggle(cat: Category, chan: Channel, value: boolean) {
    writePref(cat, chan, value);
    setPrefs((prev) => ({ ...prev, [`${cat}_${chan}`]: value }));
    setFlash("Préférence enregistrée.");
    setTimeout(() => setFlash(null), 2200);
  }

  return (
    <Container>
      <header className="border-b border-line-200 pb-6 pt-10">
        <button
          type="button"
          onClick={() => router.push("/profil")}
          className="text-sm text-ink-600 hover:text-blue-700"
        >
          ← Retour au profil
        </button>
        <h1 className="mt-3 font-editorial text-3xl font-medium text-ink-900">
          Préférences de notifications
        </h1>
        <p className="mt-2 text-sm text-ink-600">
          Choisis ce que tu veux recevoir et par quel canal. Les paramètres
          sont sauvegardés sur cet appareil.
        </p>
      </header>

      <section className="mt-8 space-y-4">
        {CATEGORIES.map((cat) => (
          <div
            key={cat.key}
            className="rounded-md border border-line-200 bg-paper p-5"
          >
            <header className="mb-4">
              <h2 className="font-display text-base font-semibold text-ink-900">
                {cat.label}
              </h2>
              <p className="mt-0.5 text-xs text-ink-600">{cat.subtitle}</p>
            </header>
            <ul className="space-y-2.5">
              {CHANNELS.map((chan) => {
                const checked = prefs[`${cat.key}_${chan.key}`] ?? true;
                return (
                  <li
                    key={chan.key}
                    className="flex items-center justify-between"
                  >
                    <span className="text-sm text-ink-700">{chan.label}</span>
                    <label className="relative inline-flex cursor-pointer items-center">
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={(e) =>
                          onToggle(cat.key, chan.key, e.target.checked)
                        }
                        className="peer sr-only"
                      />
                      <span className="h-5 w-9 rounded-full bg-line-200 transition-colors peer-checked:bg-emerald-600"></span>
                      <span className="absolute left-0.5 top-0.5 size-4 rounded-full bg-paper shadow-sm transition-transform peer-checked:translate-x-4"></span>
                    </label>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}

        <p className="rounded-md border border-blue-200 bg-blue-50/50 p-3 text-xs text-blue-800">
          ℹ️ Les notifications par e-mail et SMS dépendent aussi de la
          configuration côté coopérative. Si tu ne reçois pas un type
          d'événement, contacte l'agence pour vérifier l'activation côté
          serveur.
        </p>
      </section>

      {flash ? (
        <div className="fixed bottom-6 left-1/2 z-40 -translate-x-1/2 rounded-md bg-emerald-700 px-4 py-2 text-sm font-medium text-white shadow-lg">
          {flash}
        </div>
      ) : null}
    </Container>
  );
}
