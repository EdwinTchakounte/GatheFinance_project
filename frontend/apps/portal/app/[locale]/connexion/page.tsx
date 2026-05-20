"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { buttonClasses } from "@gathe/ui";

import { portalApi, type ApiError } from "@/lib/api";


export default function PortalLoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Prime the CSRF cookie on mount — subsequent POST gets the token via document.cookie.
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
          ?? (apiErr.status === 401 ? "Identifiants invalides." : "Connexion impossible.")
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="min-h-svh bg-cream py-16">
      <section className="mx-auto w-full max-w-md px-6">
        <header className="mb-8 text-center">
          <span className="label-num">Espace membre</span>
          <h1 className="mt-3 font-editorial text-3xl font-medium text-ink-900">
            Connexion
          </h1>
          <p className="mt-3 text-sm text-ink-600">
            Accède à ton compte d'épargne, tes crédits et tes paiements.
          </p>
        </header>

        <form
          onSubmit={onSubmit}
          className="rounded-md border border-line-200 bg-paper p-7 shadow-[var(--shadow-sm)]"
        >
          <label className="block text-sm font-medium text-ink-900" htmlFor="email">
            Adresse e-mail
          </label>
          <input
            id="email"
            name="email"
            type="email"
            required
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="mt-2 block w-full rounded-md border border-line-200 bg-paper px-3 py-2 text-ink-900 outline-none transition-colors focus:border-blue-700 focus:ring-1 focus:ring-blue-700"
            placeholder="prenom@exemple.com"
          />

          <label className="mt-5 block text-sm font-medium text-ink-900" htmlFor="password">
            Mot de passe
          </label>
          <input
            id="password"
            name="password"
            type="password"
            required
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="mt-2 block w-full rounded-md border border-line-200 bg-paper px-3 py-2 text-ink-900 outline-none transition-colors focus:border-blue-700 focus:ring-1 focus:ring-blue-700"
          />

          {error ? (
            <p
              role="alert"
              className="mt-4 rounded-md border border-terra-400/40 bg-terra-50/60 px-3 py-2 text-sm text-terra-700"
            >
              {error}
            </p>
          ) : null}

          <button
            type="submit"
            disabled={submitting}
            className={buttonClasses({ variant: "success", size: "lg", fullWidth: true }) + " mt-7"}
          >
            {submitting ? "Connexion…" : "Se connecter"}
          </button>

          <p className="mt-5 text-center text-xs text-ink-600">
            Pas encore membre ?{" "}
            <a href="/devenir-membre" className="font-medium text-blue-700 hover:underline">
              Faire une demande d'adhésion
            </a>
          </p>
        </form>
      </section>
    </main>
  );
}
