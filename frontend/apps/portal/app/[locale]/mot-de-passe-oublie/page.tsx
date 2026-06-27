"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { portalApi, type ApiError } from "@/lib/api";


// P1 . 3 etapes du flow .
//   1. EMAIL    saisie de l'email -> POST /auth/password-reset/request/ (OTP par mail)
//   2. RESET    saisie du code 6 chiffres + nouveau mot de passe -> POST /confirm/
//   3. DONE     ecran succes -> bouton vers /connexion
type Step = "email" | "reset" | "done";


export default function ForgotPasswordPage() {
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
    portalApi.primeCsrf().catch(() => undefined);
  }, []);

  async function onRequestCode(e: React.FormEvent) {
    e.preventDefault();
    if (submitting) return;
    setError(null);
    setInfo(null);
    setSubmitting(true);
    try {
      const res = await portalApi.requestPasswordReset(email.trim().toLowerCase());
      // Le backend renvoie toujours le meme message (anti-enumeration).
      setInfo(
        res.detail
          ?? "Si un compte existe pour cet email, un code de 6 chiffres a ete envoye.",
      );
      setStep("reset");
    } catch (err) {
      const apiErr = err as ApiError;
      setError(apiErr.detail ?? "Demande impossible. Reessaie dans un instant.");
    } finally {
      setSubmitting(false);
    }
  }

  async function onConfirm(e: React.FormEvent) {
    e.preventDefault();
    if (submitting) return;
    setError(null);
    setInfo(null);
    if (code.length !== 6 || !/^\d{6}$/.test(code)) {
      setError("Le code doit contenir exactement 6 chiffres.");
      return;
    }
    if (newPassword.length < 8) {
      setError("Le mot de passe doit faire au moins 8 caracteres.");
      return;
    }
    setSubmitting(true);
    try {
      await portalApi.confirmPasswordReset({
        email: email.trim().toLowerCase(),
        code,
        new_password: newPassword,
      });
      setStep("done");
    } catch (err) {
      const apiErr = err as ApiError;
      setError(
        apiErr.detail
          ?? "Code invalide, expire ou mot de passe trop faible.",
      );
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
          Retour a la connexion
        </a>
      </div>

      <section className="relative z-10 mx-auto mt-10 max-w-md px-5 sm:px-8">
        <header className="mb-7 text-center">
          <p className="font-display text-[0.7rem] font-semibold uppercase tracking-[0.18em] text-emerald-700">
            Mot de passe oublie
          </p>
          <h1 className="mt-2 font-editorial text-3xl font-medium text-ink-900">
            {step === "email"
              ? "Receois un code par email"
              : step === "reset"
                ? "Saisis ton nouveau mot de passe"
                : "C'est fait !"}
          </h1>
          <p className="mt-2 text-sm text-ink-600">
            {step === "email"
              ? "On t'envoie un code de 6 chiffres a saisir a l'etape suivante."
              : step === "reset"
                ? "Le code expire dans 15 minutes. Si tu ne l'as pas recu, verifie tes spams."
                : "Tu peux maintenant te connecter avec ton nouveau mot de passe."}
          </p>
        </header>

        <div className="rounded-2xl border border-line-200 bg-paper/95 p-6 shadow-sm backdrop-blur-sm">
          {error ? (
            <div className="mb-4 rounded-md border border-rose-300 bg-rose-50/70 px-3 py-2 text-xs text-rose-700">
              {error}
            </div>
          ) : null}
          {info && step !== "done" ? (
            <div className="mb-4 rounded-md border border-emerald-300 bg-emerald-50/70 px-3 py-2 text-xs text-emerald-700">
              {info}
            </div>
          ) : null}

          {step === "email" ? (
            <form onSubmit={onRequestCode} className="space-y-4">
              <div>
                <label
                  htmlFor="email"
                  className="mb-1.5 block text-xs font-semibold text-ink-700"
                >
                  Email
                </label>
                <input
                  id="email"
                  type="email"
                  required
                  autoComplete="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="exemple@gathe-finance.com"
                  className="block w-full rounded-xl border border-line-200 bg-paper px-3.5 py-2.5 text-ink-900 outline-none transition-all placeholder:text-ink-400 focus:border-blue-700 focus:ring-2 focus:ring-blue-700/15"
                />
              </div>
              <button
                type="submit"
                disabled={submitting || !email}
                className="w-full rounded-xl bg-blue-700 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-blue-800 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {submitting ? "Envoi..." : "Recevoir le code"}
              </button>
            </form>
          ) : null}

          {step === "reset" ? (
            <form onSubmit={onConfirm} className="space-y-4">
              <div>
                <label
                  htmlFor="code"
                  className="mb-1.5 block text-xs font-semibold text-ink-700"
                >
                  Code recu par email (6 chiffres)
                </label>
                <input
                  id="code"
                  type="text"
                  inputMode="numeric"
                  pattern="\d{6}"
                  required
                  maxLength={6}
                  value={code}
                  onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
                  placeholder="123456"
                  className="block w-full rounded-xl border border-line-200 bg-paper px-3.5 py-2.5 text-center font-mono text-lg tracking-widest text-ink-900 outline-none transition-all placeholder:text-ink-400 focus:border-blue-700 focus:ring-2 focus:ring-blue-700/15"
                />
              </div>
              <div>
                <label
                  htmlFor="new-password"
                  className="mb-1.5 block text-xs font-semibold text-ink-700"
                >
                  Nouveau mot de passe
                </label>
                <div className="relative">
                  <input
                    id="new-password"
                    type={showPwd ? "text" : "password"}
                    required
                    autoComplete="new-password"
                    minLength={8}
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
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
              <button
                type="submit"
                disabled={submitting || code.length !== 6 || !newPassword}
                className="w-full rounded-xl bg-blue-700 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-blue-800 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {submitting ? "Validation..." : "Definir le nouveau mot de passe"}
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
                className="block w-full text-center text-xs text-ink-500 hover:text-ink-900"
              >
                Renvoyer un code
              </button>
            </form>
          ) : null}

          {step === "done" ? (
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
                Ton mot de passe a ete reinitialise avec succes.
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
        </div>
      </section>
    </main>
  );
}
