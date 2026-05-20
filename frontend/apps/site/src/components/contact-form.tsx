"use client";

import { useCallback, useEffect, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { CheckCircle2, AlertCircle, Loader2 } from "lucide-react";

import { Button, cn } from "@gathe/ui";

type Endpoint = "contact" | "adhesion";
type Status = "idle" | "submitting" | "success" | "error";

const inputCls =
  "block w-full rounded-[var(--radius-md)] border border-line-200 bg-surface-50 px-3.5 py-2.5 text-[0.9375rem] text-ink-900 " +
  "shadow-[var(--shadow-xs)] outline-none transition-colors placeholder:text-ink-400 " +
  "focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 aria-[invalid=true]:border-error aria-[invalid=true]:ring-error/20";
const labelCls = "mb-1.5 block text-sm font-medium text-ink-700";

export function ContactForm({ endpoint, submitLabel }: { endpoint: Endpoint; submitLabel?: string }) {
  const t = useTranslations("form");
  const locale = useLocale();
  const [challenge, setChallenge] = useState<{ question: string; token: string } | null>(null);
  const [status, setStatus] = useState<Status>("idle");
  const [errors, setErrors] = useState<Record<string, string | undefined>>({});
  const isAdhesion = endpoint === "adhesion";

  const loadChallenge = useCallback(async () => {
    try {
      const res = await fetch("/api/forms/captcha", { cache: "no-store" });
      if (res.ok) setChallenge(await res.json());
    } catch {
      /* the form still submits; the backend will reject without a valid token */
    }
  }, []);

  useEffect(() => {
    void loadChallenge();
  }, [loadChallenge]);

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const data = new FormData(form);
    const get = (k: string) => String(data.get(k) ?? "").trim();

    const nextErrors: Record<string, string | undefined> = {};
    if (!get("name")) nextErrors.name = t("requiredName");
    const email = get("email");
    if (!email) nextErrors.email = t("requiredEmail");
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) nextErrors.email = t("invalidEmail");
    if (!get("captcha_answer")) nextErrors.captcha_answer = t("requiredCaptcha");
    if (isAdhesion) {
      if (!get("phone")) nextErrors.phone = "Le numéro de téléphone est requis.";
      if (!get("city")) nextErrors.city = "La ville est requise.";
    }
    setErrors(nextErrors);
    if (Object.values(nextErrors).some(Boolean)) return;

    setStatus("submitting");
    try {
      const adhesionExtras = isAdhesion
        ? {
            whatsapp: get("whatsapp"),
            quartier_localite: get("quartier_localite"),
            statut_pro: get("statut_pro"),
            urgence_nom: get("urgence_nom"),
            urgence_lien: get("urgence_lien"),
            urgence_phone: get("urgence_phone"),
          }
        : {};
      const res = await fetch(`/api/forms/${endpoint}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: get("name"),
          city: get("city"),
          phone: get("phone"),
          email,
          message: get("message"),
          language: locale,
          website: get("website"), // honeypot
          captcha_token: challenge?.token ?? "",
          captcha_answer: get("captcha_answer"),
          ...adhesionExtras,
        }),
      });
      if (res.ok) {
        setStatus("success");
        form.reset();
        void loadChallenge();
      } else {
        let serverErrors: Record<string, unknown> = {};
        try {
          serverErrors = await res.json();
        } catch {
          /* ignore */
        }
        if (serverErrors.captcha_answer) {
          setErrors({ captcha_answer: t("wrongCaptcha") });
          setStatus("idle");
          void loadChallenge();
        } else {
          setStatus("error");
        }
      }
    } catch {
      setStatus("error");
    }
  }

  return (
    <form onSubmit={onSubmit} noValidate className="space-y-5">
      {/* honeypot — visually hidden, never filled by humans */}
      <div aria-hidden="true" className="absolute -left-[9999px] h-px w-px overflow-hidden" tabIndex={-1}>
        <label htmlFor="website">Ne pas remplir</label>
        <input id="website" name="website" type="text" autoComplete="off" tabIndex={-1} />
      </div>

      <div className="grid gap-5 sm:grid-cols-2">
        <div>
          <label htmlFor="name" className={labelCls}>
            {t("name")} <span className="text-error">*</span>
          </label>
          <input
            id="name"
            name="name"
            type="text"
            autoComplete="name"
            required
            aria-invalid={errors.name ? true : undefined}
            aria-describedby={errors.name ? "name-error" : undefined}
            className={inputCls}
          />
          {errors.name ? (
            <p id="name-error" className="mt-1 text-sm text-error">
              {errors.name}
            </p>
          ) : null}
        </div>
        <div>
          <label htmlFor="city" className={labelCls}>
            {t("city")} {isAdhesion ? <span className="text-error">*</span> : null}
          </label>
          <input
            id="city"
            name="city"
            type="text"
            autoComplete="address-level2"
            required={isAdhesion}
            aria-invalid={errors.city ? true : undefined}
            aria-describedby={errors.city ? "city-error" : undefined}
            className={inputCls}
          />
          {errors.city ? (
            <p id="city-error" className="mt-1 text-sm text-error">
              {errors.city}
            </p>
          ) : null}
        </div>
        <div>
          <label htmlFor="phone" className={labelCls}>
            {t("phone")} {isAdhesion ? <span className="text-error">*</span> : null}
          </label>
          <input
            id="phone"
            name="phone"
            type="tel"
            autoComplete="tel"
            inputMode="tel"
            required={isAdhesion}
            aria-invalid={errors.phone ? true : undefined}
            aria-describedby={errors.phone ? "phone-error" : undefined}
            className={inputCls}
          />
          {errors.phone ? (
            <p id="phone-error" className="mt-1 text-sm text-error">
              {errors.phone}
            </p>
          ) : null}
        </div>
        <div>
          <label htmlFor="email" className={labelCls}>
            {t("email")} <span className="text-error">*</span>
          </label>
          <input
            id="email"
            name="email"
            type="email"
            autoComplete="email"
            required
            aria-invalid={errors.email ? true : undefined}
            aria-describedby={errors.email ? "email-error" : undefined}
            className={inputCls}
          />
          {errors.email ? (
            <p id="email-error" className="mt-1 text-sm text-error">
              {errors.email}
            </p>
          ) : null}
        </div>
      </div>

      {isAdhesion ? (
        <>
          <div className="grid gap-5 sm:grid-cols-2">
            <div>
              <label htmlFor="whatsapp" className={labelCls}>
                Numéro WhatsApp
              </label>
              <input
                id="whatsapp"
                name="whatsapp"
                type="tel"
                inputMode="tel"
                placeholder="Idem que le téléphone si identique"
                className={inputCls}
              />
            </div>
            <div>
              <label htmlFor="quartier_localite" className={labelCls}>
                Quartier / lieu précis
              </label>
              <input
                id="quartier_localite"
                name="quartier_localite"
                type="text"
                placeholder="Akwa, derrière le marché central…"
                className={inputCls}
              />
            </div>
            <div>
              <label htmlFor="statut_pro" className={labelCls}>
                Statut professionnel
              </label>
              <select id="statut_pro" name="statut_pro" defaultValue="" className={inputCls}>
                <option value="">— Choisir —</option>
                <option value="salarie">Salarié</option>
                <option value="commercant">Commerçant</option>
                <option value="artisan">Artisan</option>
                <option value="sans_emploi">Sans emploi</option>
                <option value="autre">Autre</option>
              </select>
            </div>
          </div>

          <fieldset className="space-y-3 rounded-[var(--radius-md)] border border-line-200 bg-ink-50/40 p-4">
            <legend className="px-1 text-sm font-medium text-ink-700">
              Contact à prévenir en cas d&apos;urgence
            </legend>
            <div className="grid gap-5 sm:grid-cols-3">
              <div>
                <label htmlFor="urgence_nom" className={labelCls}>
                  Nom &amp; prénom
                </label>
                <input id="urgence_nom" name="urgence_nom" type="text" className={inputCls} />
              </div>
              <div>
                <label htmlFor="urgence_lien" className={labelCls}>
                  Lien
                </label>
                <input
                  id="urgence_lien"
                  name="urgence_lien"
                  type="text"
                  placeholder="Conjoint, frère, ami…"
                  className={inputCls}
                />
              </div>
              <div>
                <label htmlFor="urgence_phone" className={labelCls}>
                  Téléphone
                </label>
                <input
                  id="urgence_phone"
                  name="urgence_phone"
                  type="tel"
                  inputMode="tel"
                  className={inputCls}
                />
              </div>
            </div>
          </fieldset>
        </>
      ) : null}

      <div>
        <label htmlFor="message" className={labelCls}>
          {isAdhesion ? "Pourquoi rejoindre la coopérative ?" : t("message")}
        </label>
        <textarea id="message" name="message" rows={5} className={cn(inputCls, "resize-y")} />
      </div>

      <div className="max-w-xs">
        <label htmlFor="captcha_answer" className={labelCls}>
          {t("captchaLabel", { question: challenge?.question ?? "…" })} <span className="text-error">*</span>
        </label>
        <input
          id="captcha_answer"
          name="captcha_answer"
          type="text"
          inputMode="numeric"
          autoComplete="off"
          required
          aria-invalid={errors.captcha_answer ? true : undefined}
          aria-describedby={errors.captcha_answer ? "captcha-error" : undefined}
          className={inputCls}
        />
        {errors.captcha_answer ? (
          <p id="captcha-error" className="mt-1 text-sm text-error">
            {errors.captcha_answer}
          </p>
        ) : null}
      </div>

      <div className="flex flex-wrap items-center gap-4">
        <Button type="submit" size="lg" disabled={status === "submitting"}>
          {status === "submitting" ? (
            <>
              <Loader2 aria-hidden="true" className="size-4 animate-spin" /> {t("sending")}
            </>
          ) : (
            (submitLabel ?? t("submit"))
          )}
        </Button>
        <div aria-live="polite" className="text-sm">
          {status === "success" ? (
            <span className="inline-flex items-center gap-1.5 text-success">
              <CheckCircle2 aria-hidden="true" className="size-4" /> {t("success")}
            </span>
          ) : null}
          {status === "error" ? (
            <span className="inline-flex items-center gap-1.5 text-error">
              <AlertCircle aria-hidden="true" className="size-4" /> {t("error")}
            </span>
          ) : null}
        </div>
      </div>
    </form>
  );
}
