"use client";

import { useEffect, useState } from "react";
import Image from "next/image";
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
    <main className="min-h-svh bg-cream">
      <div className="grid min-h-svh lg:grid-cols-2">
        {/* ─── Image / branding (gauche desktop, hidden mobile) ─── */}
        <aside className="relative hidden lg:block">
          <Image
            src="/images/login-hero.jpg"
            alt="Gathé Finance Administration"
            fill
            sizes="50vw"
            priority
            className="object-cover"
          />
          <div className="absolute inset-0 bg-gradient-to-tr from-ink-900/90 via-ink-800/65 to-ink-700/30" />
          <div className="absolute inset-0 flex flex-col justify-between p-12 text-white">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src="/images/logo.jpg"
              alt="Gathé Finance"
              className="h-12 w-auto rounded-md ring-1 ring-white/20"
            />
            <div className="max-w-md space-y-5">
              <p className="font-display text-xs font-semibold uppercase tracking-[0.22em] text-terra-300">
                Administration
              </p>
              <h2 className="font-editorial text-4xl leading-tight">
                Pilote la coopérative en toute sérénité.
              </h2>
              <p className="text-base leading-relaxed text-white/75">
                Approuve les adhésions, instruis les crédits, suis les
                paiements, ajuste les paramètres métier. Tout est tracé,
                tout est auditable.
              </p>
              <div className="flex items-center gap-3 pt-2 text-sm text-white/75">
                <span className="inline-flex size-2 rounded-full bg-emerald-400" />
                Accès réservé au personnel autorisé.
              </div>
            </div>
            <p className="text-xs text-white/55">
              © Gathé Finance · Console d'administration interne
            </p>
          </div>
        </aside>

        {/* ─── Formulaire ─── */}
        {/* items-start sur mobile pour eviter le vide blanc en haut. */}
        <section className="flex items-start justify-center px-5 pt-6 pb-10 sm:px-8 lg:items-center lg:px-16 lg:py-10">
          <div className="w-full max-w-md">
            <div className="mb-6 lg:hidden">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src="/images/logo.jpg"
                alt="Gathé Finance"
                className="h-9 w-auto rounded-md"
              />
            </div>

            <header className="mb-7">
              <p className="font-display text-[0.7rem] font-semibold uppercase tracking-[0.18em] text-terra-600">
                Administration
              </p>
              <h1 className="mt-2 font-editorial text-3xl font-medium leading-tight text-ink-900 sm:text-4xl">
                Connexion au back-office.
              </h1>
              <p className="mt-2 text-sm text-ink-600">
                Réservé au personnel de la coopérative.
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
                  type="email"
                  required
                  autoComplete="email"
                  autoFocus
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="block w-full rounded-lg border border-line-200 bg-paper px-3.5 py-2.5 text-ink-900 outline-none transition-all placeholder:text-ink-400 focus:border-blue-700 focus:ring-2 focus:ring-blue-700/15"
                  placeholder="admin@gathe-finance.com"
                />
              </div>

              <div>
                <label
                  className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-700"
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
                className="mt-2 inline-flex w-full items-center justify-center rounded-lg bg-ink-900 px-4 py-3 text-sm font-semibold text-white shadow-sm transition-all hover:bg-ink-800 focus:outline-none focus:ring-2 focus:ring-ink-900/40 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {submitting ? "Connexion…" : "Se connecter"}
              </button>
            </form>

            <p className="mt-8 text-center text-sm text-ink-600">
              Tu cherches l'espace membre ?{" "}
              <a
                href={`${PORTAL_URL}/connexion`}
                className="font-semibold text-blue-700 hover:underline"
              >
                C'est par ici →
              </a>
            </p>
          </div>
        </section>
      </div>
    </main>
  );
}
