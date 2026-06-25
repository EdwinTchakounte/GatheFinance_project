"use client";

import { useEffect, useState } from "react";
import Image from "next/image";
import { useRouter } from "next/navigation";

import { portalApi, type ApiError } from "@/lib/api";


export default function PortalLoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPwd, setShowPwd] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    portalApi.primeCsrf().catch(() => undefined);
  }, []);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (submitting) return;
    setError(null);
    setSubmitting(true);
    try {
      await portalApi.login(email.trim(), password);
      router.push("/");
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
    <main className="min-h-svh bg-cream">
      <div className="grid min-h-svh lg:grid-cols-2">
        {/* ─── Image / branding (gauche en desktop, masqué en mobile) ─── */}
        <aside className="relative hidden lg:block">
          <Image
            src="/images/login-hero.jpg"
            alt="Gathé Finance"
            fill
            sizes="50vw"
            priority
            className="object-cover"
          />
          <div className="absolute inset-0 bg-gradient-to-tr from-blue-900/85 via-blue-800/55 to-blue-700/25" />
          <div className="absolute inset-0 flex flex-col justify-between p-12 text-white">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src="/images/logo.jpg"
              alt="Gathé Finance"
              className="h-12 w-auto rounded-md ring-1 ring-white/20"
            />
            <div className="max-w-md space-y-5">
              <p className="font-display text-xs font-semibold uppercase tracking-[0.22em] text-white/70">
                Espace membre
              </p>
              <h2 className="font-editorial text-4xl leading-tight">
                Pilote ton épargne, tes crédits et tes cotisations en
                quelques clics.
              </h2>
              <p className="text-base leading-relaxed text-white/80">
                Tout ton parcours coopératif, accessible depuis ton
                navigateur. Visualise tes soldes, paie tes cotisations
                journalières, suis tes échéances.
              </p>
              <div className="flex items-center gap-3 pt-2 text-sm text-white/80">
                <span className="inline-flex size-2 rounded-full bg-emerald-400" />
                Connexion sécurisée. Cookies session uniquement.
              </div>
            </div>
            <p className="text-xs text-white/60">
              © Gathé Finance · Coopérative d'épargne et de crédit
            </p>
          </div>
        </aside>

        {/* ─── Formulaire (droite en desktop, plein écran en mobile) ─── */}
        <section className="flex items-center justify-center px-5 py-10 sm:px-8 lg:px-16">
          <div className="w-full max-w-md">
            {/* Logo affiché seulement en mobile (l'aside cache les visuels en lg) */}
            <div className="mb-8 flex items-center gap-3 lg:hidden">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src="/images/logo.jpg"
                alt="Gathé Finance"
                className="h-10 w-auto rounded-md"
              />
              <span className="font-display text-[0.7rem] font-semibold uppercase tracking-[0.18em] text-blue-700">
                Gathé Finance
              </span>
            </div>

            <header className="mb-7">
              <p className="font-display text-[0.7rem] font-semibold uppercase tracking-[0.18em] text-blue-700">
                Espace membre
              </p>
              <h1 className="mt-2 font-editorial text-3xl font-medium leading-tight text-ink-900 sm:text-4xl">
                Bon retour parmi nous.
              </h1>
              <p className="mt-2 text-sm text-ink-600">
                Connecte-toi pour suivre ton activité coopérative.
              </p>
            </header>

            <form onSubmit={onSubmit} className="space-y-4">
              <div>
                <label
                  className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-700"
                  htmlFor="email"
                >
                  Adresse e-mail
                </label>
                <input
                  id="email"
                  name="email"
                  type="email"
                  required
                  autoComplete="email"
                  autoFocus
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="block w-full rounded-lg border border-line-200 bg-paper px-3.5 py-2.5 text-ink-900 outline-none transition-all placeholder:text-ink-400 focus:border-blue-700 focus:ring-2 focus:ring-blue-700/15"
                  placeholder="prenom@exemple.com"
                />
              </div>

              <div>
                <div className="mb-1.5 flex items-baseline justify-between">
                  <label
                    className="text-xs font-semibold uppercase tracking-wide text-ink-700"
                    htmlFor="password"
                  >
                    Mot de passe
                  </label>
                  <a
                    href="/mot-de-passe-oublie"
                    className="text-xs text-blue-700 hover:underline"
                  >
                    Oublié ?
                  </a>
                </div>
                <div className="relative">
                  <input
                    id="password"
                    name="password"
                    type={showPwd ? "text" : "password"}
                    required
                    autoComplete="current-password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="block w-full rounded-lg border border-line-200 bg-paper px-3.5 py-2.5 pr-12 text-ink-900 outline-none transition-all placeholder:text-ink-400 focus:border-blue-700 focus:ring-2 focus:ring-blue-700/15"
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
                  className="rounded-lg border border-terra-400/40 bg-terra-50/60 px-3 py-2.5 text-sm text-terra-700"
                >
                  {error}
                </p>
              ) : null}

              <button
                type="submit"
                disabled={submitting}
                className="mt-2 inline-flex w-full items-center justify-center rounded-lg bg-blue-700 px-4 py-3 text-sm font-semibold text-white shadow-sm transition-all hover:bg-blue-800 focus:outline-none focus:ring-2 focus:ring-blue-700/40 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {submitting ? "Connexion…" : "Se connecter"}
              </button>
            </form>

            <p className="mt-8 text-center text-sm text-ink-600">
              Pas encore membre ?{" "}
              <a
                href="/devenir-membre"
                className="font-semibold text-blue-700 hover:underline"
              >
                Faire une demande d'adhésion
              </a>
            </p>
          </div>
        </section>
      </div>
    </main>
  );
}
