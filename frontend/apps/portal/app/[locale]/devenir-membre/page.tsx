"use client";

import { useEffect, useState } from "react";


// P5 . Le formulaire devenir-membre vit cote vitrine (deja maintenu), pas
// cote portail. Pour eviter la duplication de la sequence FormSchema +
// uploads CNI/justif/photo, on redirige le visiteur vers la vitrine.
// En prod : portail.gathe-finance.horus-lab.com -> gathe-finance.horus-lab.com
// En dev  : http://localhost:3200 -> http://localhost:3000


function resolveVitrineUrl(): string {
  if (typeof window === "undefined") {
    return "https://gathe-finance.horus-lab.com/devenir-membre";
  }
  const host = window.location.hostname;
  // Prod : enleve le sous-domaine "portail." (et autres) pour pointer vitrine.
  if (host.endsWith(".gathe-finance.horus-lab.com")) {
    return "https://gathe-finance.horus-lab.com/devenir-membre";
  }
  // Dev local : suppose la vitrine sur le meme host mais port 3000.
  if (host === "localhost" || host === "127.0.0.1") {
    return `${window.location.protocol}//${host}:3000/devenir-membre`;
  }
  // Fallback : tape sur le domaine root sans sous-domaine.
  const parts = host.split(".");
  if (parts.length >= 2) {
    const rootDomain = parts.slice(-2).join(".");
    return `${window.location.protocol}//${rootDomain}/devenir-membre`;
  }
  return "https://gathe-finance.horus-lab.com/devenir-membre";
}


export default function DevenirMembreRedirectPage() {
  const [target, setTarget] = useState<string | null>(null);

  useEffect(() => {
    const url = resolveVitrineUrl();
    setTarget(url);
    // Redirection immediate.
    window.location.replace(url);
  }, []);

  return (
    <main className="relative min-h-svh bg-cream">
      <div className="mx-auto flex max-w-md flex-col items-center justify-center px-5 py-24 text-center">
        <p className="font-display text-[0.7rem] font-semibold uppercase tracking-[0.18em] text-emerald-700">
          Devenir membre
        </p>
        <h1 className="mt-3 font-editorial text-3xl font-medium text-ink-900">
          On t'envoie sur le bon formulaire…
        </h1>
        <p className="mt-3 text-sm text-ink-600">
          Le formulaire d'adhésion vit sur le site public. Si la redirection
          ne se fait pas automatiquement, clique ici :
        </p>
        {target ? (
          <a
            href={target}
            className="mt-6 inline-flex items-center gap-2 rounded-xl bg-blue-700 px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-blue-800"
          >
            Aller au formulaire →
          </a>
        ) : (
          <p className="mt-6 text-xs text-ink-500">Chargement…</p>
        )}
        <a
          href="/connexion"
          className="mt-3 text-xs text-ink-500 hover:text-ink-900"
        >
          ou retourner à la connexion
        </a>
      </div>
    </main>
  );
}
