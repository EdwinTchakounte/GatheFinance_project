"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { portalApi, type ApiError } from "@/lib/api";


type Phase = "verifying" | "form" | "expired" | "unknown" | "done";


function SetupPasswordInner() {
  const router = useRouter();
  const params = useSearchParams();
  const token = params.get("token")?.trim() ?? "";

  const [phase, setPhase] = useState<Phase>("verifying");
  const [emailMask, setEmailMask] = useState<string>("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [showPwd, setShowPwd] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    portalApi.primeCsrf().catch(() => undefined);
  }, []);

  useEffect(() => {
    if (!token) {
      setPhase("unknown");
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const res = await portalApi.verifyPasswordSetup(token);
        if (cancelled) return;
        setEmailMask(res.email_mask);
        setPhase("form");
      } catch (err) {
        if (cancelled) return;
        const apiErr = err as ApiError;
        if (apiErr.status === 410) setPhase("expired");
        else setPhase("unknown");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [token]);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (submitting) return;
    setError(null);
    if (password.length < 8) {
      setError("Le mot de passe doit faire au moins 8 caracteres.");
      return;
    }
    if (password !== confirm) {
      setError("Les deux mots de passe ne correspondent pas.");
      return;
    }
    setSubmitting(true);
    try {
      await portalApi.confirmPasswordSetup({ token, password });
      setPhase("done");
    } catch (err) {
      const apiErr = err as ApiError;
      if (apiErr.status === 410) {
        setPhase("expired");
      } else if (apiErr.status === 404) {
        setPhase("unknown");
      } else {
        setError(apiErr.detail ?? "Mot de passe invalide. Reessaie.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="relative min-h-svh bg-cream">
      <div aria-hidden className="pointer-events-none absolute inset-0 -z-0 overflow-hidden">
        <div className="absolute -top-32 -left-32 size-96 rounded-full bg-blue-100/40 blur-3xl" />
        <div className="absolute -bottom-32 -right-32 size-96 rounded-full bg-emerald-100/30 blur-3xl" />
      </div>

      <div className="relative z-10 mx-auto flex max-w-5xl items-center justify-between px-5 pt-5 sm:px-8">
        <a
          href="/connexion"
          className="inline-flex items-center gap-2 text-xs font-medium text-ink-600 hover:text-ink-900"
        >
          <span aria-hidden>←</span>
          Aller a la connexion
        </a>
      </div>

      <section className="relative z-10 mx-auto mt-10 max-w-md px-5 sm:px-8">
        <header className="mb-7 text-center">
          <p className="font-display text-[0.7rem] font-semibold uppercase tracking-[0.18em] text-emerald-700">
            Bienvenue chez GATHE Finance
          </p>
          <h1 className="mt-2 font-editorial text-3xl font-medium text-ink-900">
            {phase === "form"
              ? "Definis ton mot de passe"
              : phase === "done"
                ? "C'est fait !"
                : phase === "expired"
                  ? "Lien expire"
                  : phase === "unknown"
                    ? "Lien invalide"
                    : "Verification du lien..."}
          </h1>
          {phase === "form" && emailMask ? (
            <p className="mt-2 text-sm text-ink-600">
              Compte associe a <strong>{emailMask}</strong>. Choisis un mot de
              passe d'au moins 8 caracteres.
            </p>
          ) : null}
          {phase === "expired" ? (
            <p className="mt-2 text-sm text-ink-600">
              Ce lien n'est plus valide (expire au bout de 72h ou deja utilise).
              Contacte l'agence pour qu'un nouveau lien te soit envoye.
            </p>
          ) : null}
          {phase === "unknown" ? (
            <p className="mt-2 text-sm text-ink-600">
              Ce lien est introuvable. Verifie que tu as bien clique sur celui
              recu par e-mail, ou contacte l'agence.
            </p>
          ) : null}
        </header>

        <div className="rounded-2xl border border-line-200 bg-paper/95 p-6 shadow-sm backdrop-blur-sm">
          {error ? (
            <div className="mb-4 rounded-md border border-rose-300 bg-rose-50/70 px-3 py-2 text-xs text-rose-700">
              {error}
            </div>
          ) : null}

          {phase === "verifying" ? (
            <p className="text-center text-sm text-ink-600">
              Verification en cours...
            </p>
          ) : null}

          {phase === "form" ? (
            <form onSubmit={onSubmit} className="space-y-4">
              <div>
                <label
                  htmlFor="password"
                  className="mb-1.5 block text-xs font-semibold text-ink-700"
                >
                  Mot de passe
                </label>
                <div className="relative">
                  <input
                    id="password"
                    type={showPwd ? "text" : "password"}
                    required
                    autoComplete="new-password"
                    minLength={8}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="Au moins 8 caracteres"
                    className="block w-full rounded-xl border border-line-200 bg-paper px-3.5 py-2.5 pr-14 text-ink-900 outline-none transition-all placeholder:text-ink-400 focus:border-blue-700 focus:ring-2 focus:ring-blue-700/15"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPwd((v) => !v)}
                    className="absolute right-2 top-1/2 -translate-y-1/2 rounded-md px-2 py-1 text-xs font-medium text-ink-500 hover:bg-line-100 hover:text-ink-900"
                  >
                    {showPwd ? "Masquer" : "Afficher"}
                  </button>
                </div>
              </div>
              <div>
                <label
                  htmlFor="confirm"
                  className="mb-1.5 block text-xs font-semibold text-ink-700"
                >
                  Confirmer le mot de passe
                </label>
                <input
                  id="confirm"
                  type={showPwd ? "text" : "password"}
                  required
                  autoComplete="new-password"
                  minLength={8}
                  value={confirm}
                  onChange={(e) => setConfirm(e.target.value)}
                  placeholder="Repete le meme mot de passe"
                  className="block w-full rounded-xl border border-line-200 bg-paper px-3.5 py-2.5 text-ink-900 outline-none transition-all placeholder:text-ink-400 focus:border-blue-700 focus:ring-2 focus:ring-blue-700/15"
                />
              </div>
              <button
                type="submit"
                disabled={submitting || !password || !confirm}
                className="w-full rounded-xl bg-blue-700 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-blue-800 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {submitting ? "Validation..." : "Definir mon mot de passe"}
              </button>
            </form>
          ) : null}

          {phase === "done" ? (
            <div className="space-y-4 text-center">
              <div className="mx-auto inline-flex size-12 items-center justify-center rounded-full bg-emerald-100 text-emerald-700">
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  width="22"
                  height="22"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  aria-hidden
                >
                  <polyline points="20 6 9 17 4 12" />
                </svg>
              </div>
              <p className="text-sm text-ink-700">
                Ton mot de passe est defini. Tu peux maintenant te connecter au
                portail ou a l'application mobile, puis regler tes frais
                d'adhesion pour activer ton compte.
              </p>
              <button
                type="button"
                onClick={() => router.push("/connexion")}
                className="inline-block rounded-xl bg-blue-700 px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-blue-800"
              >
                Aller a la connexion
              </button>
            </div>
          ) : null}

          {phase === "expired" || phase === "unknown" ? (
            <div className="text-center">
              <a
                href="/connexion"
                className="inline-block rounded-xl bg-blue-700 px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-blue-800"
              >
                Aller a la connexion
              </a>
            </div>
          ) : null}
        </div>
      </section>
    </main>
  );
}


export default function SetupPasswordPage() {
  return (
    <Suspense fallback={null}>
      <SetupPasswordInner />
    </Suspense>
  );
}
