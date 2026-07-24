"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { adminApi, type ApiError } from "@/lib/api";

type Step = "email" | "reset" | "done";

/**
 * Mot de passe oublie (back-office).
 * Flow OTP 6 chiffres par e-mail, memes endpoints backend que le portail
 * membre : /auth/password-reset/request/ puis /auth/password-reset/confirm/.
 * Etape 1 anti-enumeration : on affiche toujours un message neutre.
 */
export default function AdminForgotPasswordPage() {
  const router = useRouter();
  const [step, setStep] = useState<Step>("email");
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [showPwd, setShowPwd] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);

  useEffect(() => {
    adminApi.primeCsrf().catch(() => undefined);
  }, []);

  async function onRequest(e: React.FormEvent) {
    e.preventDefault();
    if (submitting) return;
    setError(null);
    setInfo(null);
    const trimmed = email.trim();
    if (!trimmed.includes("@")) {
      setError("Adresse e-mail invalide.");
      return;
    }
    setSubmitting(true);
    try {
      await adminApi.requestPasswordReset(trimmed);
      setInfo(
        "Si un compte existe pour cette adresse, un code à 6 chiffres vient d'être envoyé. Il expire dans 15 minutes.",
      );
      setStep("reset");
    } catch (err) {
      const apiErr = err as ApiError;
      setError(apiErr.detail ?? "Envoi impossible. Réessayez.");
    } finally {
      setSubmitting(false);
    }
  }

  async function onConfirm(e: React.FormEvent) {
    e.preventDefault();
    if (submitting) return;
    setError(null);
    if (!/^\d{6}$/.test(code.trim())) {
      setError("Le code doit contenir 6 chiffres.");
      return;
    }
    if (newPassword.length < 4) {
      setError("Le mot de passe doit faire au moins 4 caractères.");
      return;
    }
    setSubmitting(true);
    try {
      await adminApi.confirmPasswordReset({
        email: email.trim(),
        code: code.trim(),
        new_password: newPassword,
      });
      setStep("done");
    } catch (err) {
      const apiErr = err as ApiError;
      setError(apiErr.detail ?? "Code invalide ou expiré.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="relative min-h-svh bg-cream">
      <div aria-hidden className="pointer-events-none absolute inset-0 -z-0 overflow-hidden">
        <div className="absolute -top-32 left-1/2 size-[28rem] -translate-x-1/2 rounded-full bg-ink-200/20 blur-3xl" />
      </div>

      <div className="relative z-10 mx-auto flex max-w-5xl items-center justify-between px-5 pt-5 sm:px-8">
        <p className="font-display text-[0.7rem] font-semibold uppercase tracking-[0.22em] text-ink-500">
          Administration
        </p>
        <a
          href="/login"
          className="text-xs font-medium text-ink-600 hover:text-blue-700"
        >
          ← Connexion
        </a>
      </div>

      <div className="relative z-10 mx-auto flex min-h-[calc(100svh-3.5rem)] max-w-md items-center justify-center px-5 py-12 sm:px-0">
        <div className="w-full">
          <div className="mb-8 flex flex-col items-center">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src="/images/logo.jpg"
              alt="GATHE Finance"
              className="h-12 w-auto rounded-xl ring-1 ring-ink-900/5"
            />
            <p className="mt-3 font-display text-[0.65rem] font-semibold uppercase tracking-[0.22em] text-terra-600">
              Back-office
            </p>
          </div>

          <div className="rounded-2xl border border-line-100 bg-paper p-7 shadow-md sm:p-9">
            {step === "email" ? (
              <>
                <header className="mb-7">
                  <h1 className="font-editorial text-2xl font-medium leading-tight text-ink-900 sm:text-3xl">
                    Mot de passe oublié
                  </h1>
                  <p className="mt-1.5 text-sm text-ink-600">
                    Indiquez l&apos;adresse e-mail de votre compte pour recevoir
                    un code de réinitialisation.
                  </p>
                </header>

                <form onSubmit={onRequest} className="space-y-4">
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
                    {submitting ? "Envoi…" : "Recevoir le code"}
                  </button>
                </form>
              </>
            ) : null}

            {step === "reset" ? (
              <>
                <header className="mb-7">
                  <h1 className="font-editorial text-2xl font-medium leading-tight text-ink-900 sm:text-3xl">
                    Nouveau mot de passe
                  </h1>
                  <p className="mt-1.5 text-sm text-ink-600">
                    Saisissez le code reçu par e-mail et votre nouveau mot de
                    passe.
                  </p>
                </header>

                {info ? (
                  <p className="mb-4 rounded-xl border border-emerald-300 bg-emerald-50/70 px-3 py-2.5 text-sm text-emerald-700">
                    {info}
                  </p>
                ) : null}

                <form onSubmit={onConfirm} className="space-y-4">
                  <div>
                    <label
                      className="mb-1.5 block text-xs font-semibold text-ink-700"
                      htmlFor="code"
                    >
                      Code à 6 chiffres
                    </label>
                    <input
                      id="code"
                      inputMode="numeric"
                      autoComplete="one-time-code"
                      maxLength={6}
                      required
                      autoFocus
                      value={code}
                      onChange={(e) =>
                        setCode(e.target.value.replace(/\D/g, "").slice(0, 6))
                      }
                      className="block w-full rounded-xl border border-line-200 bg-paper px-3.5 py-2.5 text-center text-lg font-semibold tracking-[0.5em] text-ink-900 outline-none transition-all focus:border-blue-700 focus:ring-2 focus:ring-blue-700/15"
                      placeholder="••••••"
                    />
                  </div>

                  <div>
                    <label
                      className="mb-1.5 block text-xs font-semibold text-ink-700"
                      htmlFor="new-password"
                    >
                      Nouveau mot de passe
                    </label>
                    <div className="relative">
                      <input
                        id="new-password"
                        type={showPwd ? "text" : "password"}
                        required
                        autoComplete="new-password"
                        value={newPassword}
                        onChange={(e) => setNewPassword(e.target.value)}
                        className="block w-full rounded-xl border border-line-200 bg-paper px-3.5 py-2.5 pr-14 text-ink-900 outline-none transition-all placeholder:text-ink-400 focus:border-blue-700 focus:ring-2 focus:ring-blue-700/15"
                        placeholder="4 caractères minimum"
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
                    {submitting ? "Validation…" : "Réinitialiser le mot de passe"}
                  </button>

                  <button
                    type="button"
                    onClick={() => {
                      setStep("email");
                      setCode("");
                      setNewPassword("");
                      setError(null);
                      setInfo(null);
                    }}
                    className="w-full text-center text-xs font-medium text-ink-500 hover:text-ink-900"
                  >
                    Renvoyer un code
                  </button>
                </form>
              </>
            ) : null}

            {step === "done" ? (
              <div className="flex flex-col items-center py-4 text-center">
                <div className="flex size-14 items-center justify-center rounded-full bg-emerald-50 text-emerald-600">
                  <svg
                    viewBox="0 0 24 24"
                    fill="none"
                    className="size-7"
                    stroke="currentColor"
                    strokeWidth={2.4}
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <path d="M20 6 9 17l-5-5" />
                  </svg>
                </div>
                <h1 className="mt-5 font-editorial text-2xl font-medium leading-tight text-ink-900">
                  Mot de passe réinitialisé
                </h1>
                <p className="mt-1.5 text-sm text-ink-600">
                  Vous pouvez maintenant vous connecter avec votre nouveau mot
                  de passe.
                </p>
                <button
                  type="button"
                  onClick={() => router.push("/login")}
                  className="mt-6 inline-flex w-full items-center justify-center rounded-xl bg-blue-700 px-4 py-3 text-sm font-semibold text-white shadow-sm transition-all hover:bg-blue-800"
                >
                  Aller à la connexion
                </button>
              </div>
            ) : null}
          </div>

          <p className="mt-6 text-center text-[0.7rem] text-ink-500">
            © {new Date().getFullYear()} GATHE Finance · Back-office sécurisé
          </p>
        </div>
      </div>
    </main>
  );
}
