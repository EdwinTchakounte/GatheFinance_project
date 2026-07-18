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
    <main className="min-h-svh bg-cream lg:grid lg:grid-cols-[1.05fr_1fr]">
      {/* ── Panneau marque (desktop) — gradient bleu institutionnel ─────── */}
      <aside className="relative hidden overflow-hidden bg-blue-900 lg:flex lg:flex-col lg:justify-between lg:p-12">
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0"
          style={{
            background:
              "radial-gradient(120% 90% at 15% 0%, #0556ab 0%, #004ca4 42%, #002c5e 100%)",
          }}
        />
        <div
          aria-hidden
          className="pointer-events-none absolute -right-24 -top-24 size-96 rounded-full bg-white/5 blur-2xl"
        />
        <div className="relative z-10">
          {/* Logo officiel sur pastille claire (contraste sur le fond bleu). */}
          <span className="inline-flex items-center rounded-2xl bg-paper px-4 py-2.5 shadow-sm">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src="/images/logo.png"
              alt="GATHE Finance"
              className="h-8 w-auto"
            />
          </span>
        </div>
        <div className="relative z-10 max-w-md">
          <h2 className="font-editorial text-3xl font-medium leading-tight text-white">
            Le back-office de la coopérative.
          </h2>
          <p className="mt-3 text-sm leading-relaxed text-white/70">
            Pilotez les adhésions, le crédit, l&apos;épargne et les campagnes
            depuis un espace unique, sécurisé et réservé au personnel.
          </p>
        </div>
        <p className="relative z-10 text-xs text-white/50">
          © {new Date().getFullYear()} GATHE Finance · Back-office sécurisé
        </p>
      </aside>

      {/* ── Panneau formulaire ─────────────────────────────────────────── */}
      <div className="relative flex min-h-svh flex-col px-5 py-6 sm:px-8 lg:py-10">
        {/* Top bar discret. */}
        <div className="flex items-center justify-between">
          <p className="font-display text-[0.7rem] font-semibold uppercase tracking-[0.22em] text-ink-500 lg:hidden">
            Administration
          </p>
          <a
            href={`${PORTAL_URL}/connexion`}
            className="ml-auto text-xs font-medium text-ink-600 transition-colors hover:text-blue-700"
          >
            Espace membre →
          </a>
        </div>

        <div className="flex flex-1 items-center justify-center py-8">
          <div className="w-full max-w-md">
            {/* Logo (mobile : centré ; desktop : discret au-dessus du form). */}
            <div className="mb-8 flex flex-col items-center lg:items-start">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src="/images/logo.png"
                alt="GATHE Finance"
                className="h-11 w-auto lg:hidden"
              />
              <p className="mt-3 font-display text-[0.65rem] font-semibold uppercase tracking-[0.22em] text-terra-600 lg:mt-0">
                Back-office
              </p>
            </div>

            {/* Card form. */}
            <div className="rounded-2xl border border-line-100 bg-paper p-7 shadow-md sm:p-9">
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
                className="mt-2 inline-flex w-full items-center justify-center rounded-xl bg-blue-700 px-4 py-3 text-sm font-semibold text-white shadow-sm transition-all hover:bg-blue-800 focus:outline-none focus:ring-2 focus:ring-blue-700/40 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {submitting ? "Connexion…" : "Se connecter"}
              </button>

              <div className="pt-1 text-center">
                <a
                  href="/mot-de-passe-oublie"
                  className="text-xs font-medium text-ink-500 transition-colors hover:text-blue-700"
                >
                  Mot de passe oublié ?
                </a>
              </div>
              </form>
            </div>

            <p className="mt-6 text-center text-[0.7rem] text-ink-500 lg:hidden">
              © {new Date().getFullYear()} GATHE Finance · Back-office sécurisé
            </p>
          </div>
        </div>
      </div>
    </main>
  );
}
