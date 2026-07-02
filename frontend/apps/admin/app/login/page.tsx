"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { adminApi, type ApiError } from "@/lib/api";

const PORTAL_URL = process.env.NEXT_PUBLIC_PORTAL_URL ?? "http://localhost:3201";


export default function AdminLoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPwd, setShowPwd] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    adminApi.primeCsrf().catch(() => undefined);
  }, []);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (submitting) return;
    setError(null);
    setSubmitting(true);
    try {
      const me = await adminApi.login(email.trim(), password);
      if (!me.is_staff && !me.is_superuser) {
        setError("Ce compte n'a pas les droits administrateur.");
        return;
      }
      router.push("/dashboard");
    } catch (err) {
      const apiErr = err as ApiError;
      setError(
        apiErr.detail
          ?? (apiErr.status === 401 ? "Identifiants invalides." : "Connexion impossible."),
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="relative min-h-svh bg-cream">
      {/* Fond doux institutionnel : un seul gradient ink-tinted. */}
      <div aria-hidden className="pointer-events-none absolute inset-0 -z-0 overflow-hidden">
        <div className="absolute -top-32 left-1/2 size-[28rem] -translate-x-1/2 rounded-full bg-ink-200/20 blur-3xl" />
      </div>

      {/* Top bar discret. */}
      <div className="relative z-10 mx-auto flex max-w-5xl items-center justify-between px-5 pt-5 sm:px-8">
        <p className="font-display text-[0.7rem] font-semibold uppercase tracking-[0.22em] text-ink-500">
          Administration
        </p>
        <a
          href={`${PORTAL_URL}/connexion`}
          className="text-xs font-medium text-ink-600 hover:text-blue-700"
        >
          Espace membre →
        </a>
      </div>

      {/* Card centree. */}
      <div className="relative z-10 mx-auto flex min-h-[calc(100svh-3.5rem)] max-w-md items-center justify-center px-5 py-12 sm:px-0">
        <div className="w-full">
          {/* Logo discret. */}
          <div className="mb-8 flex flex-col items-center">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src="/images/logo.jpg"
              alt="Gathé Finance"
              className="h-12 w-auto rounded-xl ring-1 ring-ink-900/5"
            />
            <p className="mt-3 font-display text-[0.65rem] font-semibold uppercase tracking-[0.22em] text-terra-600">
              Back-office
            </p>
          </div>

          {/* Card form. */}
          <div className="rounded-2xl border border-line-200/80 bg-paper p-7 shadow-[0_8px_30px_-12px_rgba(15,23,42,0.08)] sm:p-9">
            <header className="mb-7">
              <h1 className="font-editorial text-2xl font-medium leading-tight text-ink-900 sm:text-3xl">
                Connexion
              </h1>
              <p className="mt-1.5 text-sm text-ink-600">
                Réservé au personnel de la coopérative.
              </p>
            </header>

            <form onSubmit={onSubmit} className="space-y-4">
              <div>
                <label
                  className="mb-1.5 block text-xs font-semibold text-ink-700"
                  htmlFor="email"
                >
                  Adresse e-mail
                </label>
                <input
                  id="email"
                  type="email"
                  required
                  autoComplete="email"
                  autoFocus
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="block w-full rounded-xl border border-line-200 bg-paper px-3.5 py-2.5 text-ink-900 outline-none transition-all placeholder:text-ink-400 focus:border-blue-700 focus:ring-2 focus:ring-blue-700/15"
                  placeholder="admin@gathe-finance.com"
                />
              </div>

              <div>
                <label
                  className="mb-1.5 block text-xs font-semibold text-ink-700"
                  htmlFor="password"
                >
                  Mot de passe
                </label>
                <div className="relative">
                  <input
                    id="password"
                    type={showPwd ? "text" : "password"}
                    required
                    autoComplete="current-password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="block w-full rounded-xl border border-line-200 bg-paper px-3.5 py-2.5 pr-14 text-ink-900 outline-none transition-all placeholder:text-ink-400 focus:border-blue-700 focus:ring-2 focus:ring-blue-700/15"
                    placeholder="••••••••"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPwd((v) => !v)}
                    aria-label={showPwd ? "Masquer" : "Afficher"}
                    className="absolute inset-y-0 right-0 flex items-center px-3 text-xs font-medium text-ink-500 hover:text-ink-900"
                  >
                    {showPwd ? "Masquer" : "Afficher"}
                  </button>
                </div>
              </div>

              {error ? (
                <p
                  role="alert"
                  className="rounded-xl border border-terra-400/40 bg-terra-50/60 px-3 py-2.5 text-sm text-terra-700"
                >
                  {error}
                </p>
              ) : null}

              <button
                type="submit"
                disabled={submitting}
                className="mt-2 inline-flex w-full items-center justify-center rounded-xl bg-ink-900 px-4 py-3 text-sm font-semibold text-white shadow-sm transition-all hover:bg-ink-800 focus:outline-none focus:ring-2 focus:ring-ink-900/40 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {submitting ? "Connexion…" : "Se connecter"}
              </button>

              <div className="pt-1 text-center">
                <a
                  href="/mot-de-passe-oublie"
                  className="text-xs font-medium text-ink-500 hover:text-blue-700"
                >
                  Mot de passe oublié ?
                </a>
              </div>
            </form>
          </div>

          <p className="mt-6 text-center text-[0.7rem] text-ink-500">
            © {new Date().getFullYear()} Gathé Finance · Back-office sécurisé
          </p>
        </div>
      </div>
    </main>
  );
}
