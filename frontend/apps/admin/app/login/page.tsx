"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { buttonClasses } from "@gathe/ui";

import { adminApi, type ApiError } from "@/lib/api";

// Espace membre (portail) — URL de prod injectée au build via NEXT_PUBLIC_PORTAL_URL.
const PORTAL_URL = process.env.NEXT_PUBLIC_PORTAL_URL ?? "http://localhost:3201";


export default function AdminLoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
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
      setError(apiErr.detail ?? (apiErr.status === 401 ? "Identifiants invalides." : "Connexion impossible."));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="grid min-h-svh place-items-center bg-cream px-4">
      <div className="w-full max-w-md">
        <div className="mb-8 text-center">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src="/images/logo.jpg"
            alt="Gathé Finance"
            className="mx-auto mb-4 h-14 w-auto rounded-md"
          />
          <p className="font-display text-[0.72rem] font-semibold uppercase tracking-[0.18em] text-terra-600">
            Gathe Finance
          </p>
          <h1 className="mt-2 font-editorial text-2xl font-medium text-ink-900">
            Administration
          </h1>
          <p className="mt-2 text-sm text-ink-600">
            Réservé au personnel de la coopérative.
          </p>
        </div>

        <form
          onSubmit={onSubmit}
          className="rounded-lg border border-line-200 bg-paper p-7 shadow-[var(--shadow-md)]"
        >
          <label className="block text-sm font-medium text-ink-900" htmlFor="email">
            Adresse e-mail
          </label>
          <input
            id="email"
            type="email"
            required
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="mt-2 block w-full rounded-md border border-line-200 bg-paper px-3 py-2 text-ink-900 outline-none transition-colors focus:border-blue-700 focus:ring-1 focus:ring-blue-700"
            placeholder="admin@gathe-finance.com"
          />

          <label className="mt-5 block text-sm font-medium text-ink-900" htmlFor="password">
            Mot de passe
          </label>
          <input
            id="password"
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
            className={buttonClasses({ size: "lg", fullWidth: true }) + " mt-7"}
          >
            {submitting ? "Connexion…" : "Se connecter"}
          </button>
        </form>

        <p className="mt-6 text-center text-xs text-ink-600">
          Tu cherches l'espace membre ?{" "}
          <a href={`${PORTAL_URL}/connexion`} className="font-medium text-blue-700 hover:underline">
            C'est par ici →
          </a>
        </p>
      </div>
    </main>
  );
}
