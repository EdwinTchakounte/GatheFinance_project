"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { buttonClasses } from "@gathe/ui";

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

  const year = new Date().getFullYear();
  const siteUrl = process.env.NEXT_PUBLIC_SITE_URL ?? "https://gathe-finance.com";

  return (
    <main className="min-h-svh bg-cream lg:grid lg:grid-cols-[1.08fr_1fr]">
      {/* ── Panneau marque (desktop) — gradient bleu institutionnel ─────── */}
      <aside className="relative hidden overflow-hidden bg-blue-900 lg:flex lg:flex-col lg:justify-between lg:p-14">
        {/* Photographie de marque en fond. */}
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src="/images/login-hero.jpg"
          alt=""
          aria-hidden
          className="pointer-events-none absolute inset-0 size-full object-cover"
        />
        {/* Voile dégradé bleu : sombre à gauche (texte lisible), l'image respire à droite. */}
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0"
          style={{
            background:
              "linear-gradient(118deg, rgba(0,28,60,0.92) 0%, rgba(0,44,94,0.82) 46%, rgba(6,72,150,0.40) 100%)",
          }}
        />
        <div aria-hidden className="pointer-events-none absolute -right-28 -top-28 size-[26rem] rounded-full bg-white/5 blur-3xl" />
        <div aria-hidden className="pointer-events-none absolute -bottom-24 -left-16 size-80 rounded-full bg-emerald-400/10 blur-3xl" />
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 opacity-[0.06]"
          style={{
            backgroundImage: "radial-gradient(circle at 1px 1px, #ffffff 1px, transparent 0)",
            backgroundSize: "22px 22px",
          }}
        />

        <div className="relative z-10">
          <span className="inline-flex items-center rounded-2xl bg-paper px-4 py-2.5 shadow-lg shadow-blue-950/20">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src="/images/logo.jpg" alt="GATHE Finance" className="h-8 w-auto rounded-md" />
          </span>
        </div>

        <div className="relative z-10 max-w-md">
          <p className="font-display text-[0.7rem] font-semibold uppercase tracking-[0.22em] text-emerald-300/90">
            Espace membre
          </p>
          <h2 className="mt-4 font-editorial text-[2.6rem] font-medium leading-[1.08] text-white">
            Votre coopérative, à portée de main.
          </h2>
          <p className="mt-4 text-sm leading-relaxed text-white/70">
            Suivez votre épargne, vos crédits et vos versements — en toute
            sécurité, où que vous soyez.
          </p>

          <ul className="mt-9 space-y-3.5">
            {[
              "Consulter votre épargne et vos crédits en temps réel",
              "Demander un crédit et suivre vos remboursements",
              "Recevoir vos notifications et documents officiels",
            ].map((line) => (
              <li key={line} className="flex items-center gap-3">
                <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-emerald-400/15 ring-1 ring-emerald-300/30">
                  <svg viewBox="0 0 20 20" fill="none" className="size-3.5" aria-hidden>
                    <path d="M4 10.5l3.5 3.5L16 5.5" stroke="#6ee7b7" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                </span>
                <span className="text-sm text-white/85">{line}</span>
              </li>
            ))}
          </ul>
        </div>

        <p className="relative z-10 text-xs text-white/45">
          © {year} GATHE Finance · Coopérative d&apos;épargne et de crédit
        </p>
      </aside>

      {/* ── Panneau formulaire ─────────────────────────────────────────── */}
      <div className="relative flex min-h-svh flex-col px-5 py-6 sm:px-8 lg:py-10">
        {/* Top bar : retour vitrine + demande d'adhésion. */}
        <div className="flex items-center justify-between gap-3">
          <a href={siteUrl} className="inline-flex items-center gap-1.5 text-xs font-medium text-ink-600 transition-colors hover:text-ink-900">
            <span aria-hidden>←</span>
            Retour au site
          </a>
          <a
            href={`${siteUrl}/devenir-membre`}
            className="text-xs font-medium text-ink-600 transition-colors hover:text-ink-900"
          >
            Pas encore membre&nbsp;?{" "}
            <span className="text-blue-700 underline-offset-2 hover:underline">Faire une demande</span>
          </a>
        </div>

        <div className="flex flex-1 items-center justify-center py-8">
          <div className="w-full max-w-md">
          {/* Logo (mobile : centré ; desktop : discret au-dessus du form). */}
          <div className="mb-8 flex flex-col items-center lg:items-start">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src="/images/logo.jpg"
              alt="GATHE Finance"
              className="h-11 w-auto rounded-xl ring-1 ring-ink-900/5 lg:hidden"
            />
            <p className="mt-3 font-display text-[0.65rem] font-semibold uppercase tracking-[0.22em] text-terra-600 lg:mt-0">
              Espace membre
            </p>
          </div>

          {/* Card form. */}
          <div className="rounded-2xl border border-line-200/80 bg-paper p-7 shadow-[0_8px_30px_-12px_rgba(15,23,42,0.08)] sm:p-9">
            <header className="mb-7">
              <h1 className="font-editorial text-2xl font-medium leading-tight text-ink-900 sm:text-3xl">
                Connexion
              </h1>
              <p className="mt-1.5 text-sm text-ink-600">
                Identifie-toi pour accéder à ton compte coopératif.
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
                  placeholder="prenom@exemple.com"
                />
              </div>

              <div>
                <div className="mb-1.5 flex items-baseline justify-between">
                  <label className="text-xs font-semibold text-ink-700" htmlFor="password">
                    Mot de passe
                  </label>
                  <a
                    href="/mot-de-passe-oublie"
                    className="text-xs text-ink-500 hover:text-blue-700"
                  >
                    Oublié&nbsp;?
                  </a>
                </div>
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
                className={buttonClasses({ variant: "primary", size: "lg", fullWidth: true }) + " mt-2"}
              >
                {submitting ? "Connexion…" : "Se connecter"}
              </button>
            </form>
          </div>

          {/* Footer discret (mobile — le panneau marque porte le copyright en desktop). */}
          <p className="mt-6 text-center text-[0.7rem] text-ink-500 lg:hidden">
            © {year} GATHE Finance · Coopérative d&apos;épargne et de crédit
          </p>
          </div>
        </div>
      </div>
    </main>
  );
}
