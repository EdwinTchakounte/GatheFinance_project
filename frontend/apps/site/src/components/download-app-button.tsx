"use client";

import { useState } from "react";
import { Download, CheckCircle2, RefreshCw } from "lucide-react";

function fmtMo(bytes: number): string {
  return (bytes / (1024 * 1024)).toFixed(1).replace(".", ",");
}

type State = "idle" | "downloading" | "done" | "error";

/**
 * Téléchargement de l'APK avec VRAI indicateur de progression : on streame
 * le fichier statique auto-hébergé `/downloads/Gathe-Finance.apk` (servi par
 * le site, donc Content-Length natif — contrairement à Drive qui refuse de
 * servir un binaire > 25 Mo par programme), on cumule les octets reçus pour
 * afficher un pourcentage + une barre, puis on enregistre le fichier.
 * Objectif : le membre VOIT la progression et n'est pas tenté de relancer.
 */
export function DownloadAppButton({
  label,
  retryLabel = "Réessayer",
}: {
  label: string;
  retryLabel?: string;
}) {
  const [state, setState] = useState<State>("idle");
  const [pct, setPct] = useState(0);
  const [loaded, setLoaded] = useState(0);
  const [total, setTotal] = useState(0);

  async function start() {
    setState("downloading");
    setPct(0);
    setLoaded(0);
    setTotal(0);
    try {
      const res = await fetch("/downloads/Gathe-Finance.apk");
      if (!res.ok || !res.body) throw new Error("download failed");
      const totalBytes = Number(res.headers.get("Content-Length") ?? 0);
      setTotal(totalBytes);

      const reader = res.body.getReader();
      const chunks: Uint8Array[] = [];
      let received = 0;
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        if (value) {
          chunks.push(value);
          received += value.length;
          setLoaded(received);
          if (totalBytes > 0) {
            setPct(Math.min(100, Math.round((received / totalBytes) * 100)));
          }
        }
      }

      const blob = new Blob(chunks as BlobPart[], {
        type: "application/vnd.android.package-archive",
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "Gathe-Finance.apk";
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      setPct(100);
      setState("done");
    } catch {
      setState("error");
    }
  }

  if (state === "downloading") {
    return (
      <div className="mt-6 w-full max-w-md">
        <div className="mb-2 flex items-center justify-between text-sm">
          <span className="font-medium text-ink-800">Téléchargement…</span>
          <span className="font-mono text-ink-700">
            {total > 0 ? `${pct} %` : `${fmtMo(loaded)} Mo`}
          </span>
        </div>
        <div className="h-2.5 w-full overflow-hidden rounded-full bg-line-200">
          <div
            className="h-full rounded-full bg-emerald-600 transition-[width] duration-200"
            style={{ width: total > 0 ? `${pct}%` : "40%" }}
          />
        </div>
        <p className="mt-2 text-xs text-ink-500">
          {total > 0
            ? `${fmtMo(loaded)} / ${fmtMo(total)} Mo — merci de patienter, ne relance pas le téléchargement.`
            : "Téléchargement en cours — merci de patienter, ne relance pas."}
        </p>
      </div>
    );
  }

  if (state === "done") {
    return (
      <div className="mt-6 w-full max-w-md">
        <div className="flex items-center gap-2 rounded-lg border border-emerald-200 bg-emerald-50/60 px-4 py-3 text-sm text-emerald-800">
          <CheckCircle2 className="h-5 w-5 shrink-0" aria-hidden="true" />
          <span>
            Téléchargement terminé. Ouvre le fichier{" "}
            <span className="font-mono">Gathe-Finance.apk</span> pour installer
            la mise à jour.
          </span>
        </div>
        <button
          type="button"
          onClick={start}
          className="mt-3 inline-flex items-center gap-2 text-sm font-medium text-emerald-700 hover:text-emerald-800"
        >
          <RefreshCw className="h-4 w-4" aria-hidden="true" /> Télécharger à
          nouveau
        </button>
      </div>
    );
  }

  return (
    <>
      <button
        type="button"
        onClick={start}
        className="mt-6 inline-flex w-full items-center justify-center gap-2 rounded-lg bg-emerald-700 px-6 py-3.5 text-sm font-semibold text-white shadow-sm transition-all hover:bg-emerald-800 sm:w-auto"
      >
        <Download className="h-5 w-5" aria-hidden="true" />
        {label}
      </button>
      {state === "error" ? (
        <div className="mt-3 w-full max-w-md">
          <p className="rounded-lg border border-rose-200 bg-rose-50/60 px-4 py-2.5 text-sm text-rose-700">
            Le téléchargement a échoué. Vérifie ta connexion et réessaie.
          </p>
          <button
            type="button"
            onClick={start}
            className="mt-2 inline-flex items-center gap-2 text-sm font-medium text-emerald-700 hover:text-emerald-800"
          >
            <RefreshCw className="h-4 w-4" aria-hidden="true" /> {retryLabel}
          </button>
        </div>
      ) : null}
    </>
  );
}
