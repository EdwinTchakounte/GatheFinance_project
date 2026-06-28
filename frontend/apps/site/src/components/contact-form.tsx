"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { CheckCircle2, AlertCircle, Loader2, UploadCloud, X } from "lucide-react";

import { Button, cn } from "@gathe/ui";

import {
  DynamicFields,
  validateDynamicFields,
  type FormSchemaPayload,
  type FormValues,
} from "./form-renderer";

type Endpoint = "contact" | "adhesion";
type Status = "idle" | "submitting" | "success" | "error";

// CH-4 — Champs adhésion câblés en dur dans ce formulaire vitrine. Tous les
// autres champs du schéma `adhesion` actif sont rendus par <DynamicFields>.
// Doit refléter `_MEMBERSHIP_HARDCODED` dans `apps_coop/members/serializers.py`
// + `_hardcodedAdhesionFields` dans `mobile/.../membership_form_sheet.dart`.
const HARDCODED_ADHESION_FIELDS = new Set([
  "name", "email", "phone", "whatsapp", "city", "quartier_localite",
  "statut_pro", "urgence_nom", "urgence_lien", "urgence_phone",
  "message", "language",
  "cni_recto", "cni_verso", "plan_localisation", "photo_identite",
]);

// Taille max d'une pièce uploadée — alignée sur `_MAX_PIECE_SIZE` backend
// (`apps_coop/members/serializers.py`).
const MAX_PIECE_BYTES = 5 * 1024 * 1024;
const DOC_ACCEPT = "image/jpeg,image/png,image/heic,application/pdf,.heic";
const PHOTO_ACCEPT = "image/jpeg,image/png,image/heic,.heic";

type LoadedSchema = {
  id: number;
  kind: string;
  version: number;
  title: string;
  description: string;
  schema: { sections: Array<Record<string, unknown>> };
};

type PieceKey = "cni_recto" | "cni_verso" | "plan_localisation" | "photo_identite";

const inputCls =
  "block w-full rounded-[var(--radius-md)] border border-line-200 bg-surface-50 px-3.5 py-2.5 text-[0.9375rem] text-ink-900 " +
  "shadow-[var(--shadow-xs)] outline-none transition-colors placeholder:text-ink-400 " +
  "focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 aria-[invalid=true]:border-error aria-[invalid=true]:ring-error/20";
const labelCls = "mb-1.5 block text-sm font-medium text-ink-700";

function fmtSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} o`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} ko`;
  return `${(bytes / 1024 / 1024).toFixed(1)} Mo`;
}

export function ContactForm({ endpoint, submitLabel }: { endpoint: Endpoint; submitLabel?: string }) {
  const t = useTranslations("form");
  const locale = useLocale();
  const [challenge, setChallenge] = useState<{ question: string; token: string } | null>(null);
  const [status, setStatus] = useState<Status>("idle");
  const [errors, setErrors] = useState<Record<string, string | undefined>>({});
  const isAdhesion = endpoint === "adhesion";
  // CH-4 — Schéma + valeurs des champs ajoutés via FormSchema 'adhesion'.
  const [adhesionSchema, setAdhesionSchema] = useState<LoadedSchema | null>(null);
  const [extraValues, setExtraValues] = useState<FormValues>({});
  const [extraErrors, setExtraErrors] = useState<Record<string, string>>({});
  // Pièces obligatoires (Art.3 Règlement) — alignées 1:1 avec le mobile.
  const [pieces, setPieces] = useState<Record<PieceKey, File | null>>({
    cni_recto: null,
    cni_verso: null,
    plan_localisation: null,
    photo_identite: null,
  });
  const [piecesError, setPiecesError] = useState<string | null>(null);

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

  // CH-4 — Charge le schéma actif d'adhésion (silencieux si indisponible).
  useEffect(() => {
    if (!isAdhesion) return;
    let cancelled = false;
    async function loadSchema() {
      try {
        const res = await fetch("/api/forms/schema/adhesion", { cache: "no-store" });
        if (!res.ok) return;
        const data = (await res.json()) as LoadedSchema;
        if (!cancelled) setAdhesionSchema(data);
      } catch {
        /* schéma optionnel — mode legacy */
      }
    }
    void loadSchema();
    return () => {
      cancelled = true;
    };
  }, [isAdhesion]);

  function setPiece(key: PieceKey, file: File | null) {
    setPieces((p) => ({ ...p, [key]: file }));
    if (file) setPiecesError(null);
  }

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const data = new FormData(form);
    const get = (k: string) => String(data.get(k) ?? "").trim();

    const nextErrors: Record<string, string | undefined> = {};

    if (isAdhesion) {
      // Champs identité — alignés sur le mobile (prénom + nom séparés).
      if (!get("prenom")) nextErrors.prenom = "Le prénom est requis.";
      if (!get("nom")) nextErrors.nom = "Le nom est requis.";
    } else if (!get("name")) {
      nextErrors.name = t("requiredName");
    }

    const email = get("email");
    if (!email) nextErrors.email = t("requiredEmail");
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) nextErrors.email = t("invalidEmail");
    if (!get("captcha_answer")) nextErrors.captcha_answer = t("requiredCaptcha");

    if (isAdhesion) {
      // Champs requis . miroir exact des validators du mobile
      // (`membership_form_sheet.dart` — required: true).
      if (!get("phone")) nextErrors.phone = "Le numéro de téléphone est requis.";
      if (!get("city")) nextErrors.city = "La ville est requise.";
      if (!get("quartier_localite"))
        nextErrors.quartier_localite = "Précise le quartier ou lieu d'habitation.";
      if (!get("statut_pro")) nextErrors.statut_pro = "Choisis ton statut professionnel.";
      if (!get("urgence_nom"))
        nextErrors.urgence_nom = "Indique un contact à prévenir en cas d'urgence.";
      if (!get("urgence_lien")) nextErrors.urgence_lien = "Précise le lien avec ce contact.";
      if (!get("urgence_phone"))
        nextErrors.urgence_phone = "Indique le numéro du contact d'urgence.";

      // Pièces obligatoires (toutes les 4) — valide la présence + taille.
      const piecesMissing = (Object.keys(pieces) as PieceKey[]).filter((k) => !pieces[k]);
      if (piecesMissing.length > 0) {
        setPiecesError("Les 4 pièces justificatives sont obligatoires.");
      } else {
        const tooBig = (Object.entries(pieces) as Array<[PieceKey, File | null]>).find(
          ([, f]) => f && f.size > MAX_PIECE_BYTES,
        );
        if (tooBig) {
          setPiecesError(
            `Le fichier « ${tooBig[1]!.name} » dépasse 5 Mo. Réduis sa taille.`,
          );
        } else {
          setPiecesError(null);
        }
      }
    }

    setErrors(nextErrors);
    if (Object.values(nextErrors).some(Boolean)) return;
    if (isAdhesion && (piecesError || (Object.keys(pieces) as PieceKey[]).some((k) => !pieces[k]))) {
      return;
    }

    // CH-4 — Valide les champs supplémentaires côté client.
    if (isAdhesion && adhesionSchema) {
      const errs = validateDynamicFields(
        adhesionSchema as FormSchemaPayload,
        extraValues,
        HARDCODED_ADHESION_FIELDS,
      );
      if (Object.keys(errs).length > 0) {
        setExtraErrors(errs);
        return;
      }
      setExtraErrors({});
    }

    setStatus("submitting");
    try {
      let res: Response;
      if (isAdhesion) {
        // Adhésion = multipart/form-data (uploads CNI + plan + photo).
        // On reconstruit un FormData propre — concat prenom+nom → name pour
        // matcher le serializer backend (`name = serializers.CharField`).
        const fd = new FormData();
        fd.append("name", `${get("prenom")} ${get("nom")}`.trim());
        fd.append("email", email);
        fd.append("phone", get("phone"));
        fd.append("whatsapp", get("whatsapp"));
        fd.append("city", get("city"));
        fd.append("quartier_localite", get("quartier_localite"));
        fd.append("statut_pro", get("statut_pro"));
        fd.append("urgence_nom", get("urgence_nom"));
        fd.append("urgence_lien", get("urgence_lien"));
        fd.append("urgence_phone", get("urgence_phone"));
        fd.append("message", get("message"));
        fd.append("language", locale);
        fd.append("website", get("website")); // honeypot
        fd.append("captcha_token", challenge?.token ?? "");
        fd.append("captcha_answer", get("captcha_answer"));
        // 4 pièces. Validées non-null en amont.
        (Object.entries(pieces) as Array<[PieceKey, File | null]>).forEach(([k, f]) => {
          if (f) fd.append(k, f, f.name);
        });
        // CH-4 — Extras (scalaires uniquement, jamais d'upload via FormSchema
        // vitrine pour rester aligné mobile qui ignore aussi les PickedFile).
        if (adhesionSchema) {
          Object.entries(extraValues).forEach(([k, v]) => {
            if (v === null || v === undefined || v === "") return;
            if (v instanceof File) return; // uploads dynamiques . pas câblés
            if (Array.isArray(v)) {
              v.forEach((x) => fd.append(k, String(x)));
            } else {
              fd.append(k, String(v));
            }
          });
        }
        res = await fetch(`/api/forms/${endpoint}`, { method: "POST", body: fd });
      } else {
        res = await fetch(`/api/forms/${endpoint}`, {
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
          }),
        });
      }
      if (res.ok) {
        setStatus("success");
        form.reset();
        setExtraValues({});
        setExtraErrors({});
        setPieces({ cni_recto: null, cni_verso: null, plan_localisation: null, photo_identite: null });
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

      {/* ── Identité ──────────────────────────────────────────────────── */}
      {isAdhesion ? (
        <div className="grid gap-5 sm:grid-cols-2">
          <div>
            <label htmlFor="prenom" className={labelCls}>
              Prénom <span className="text-error">*</span>
            </label>
            <input
              id="prenom"
              name="prenom"
              type="text"
              autoComplete="given-name"
              required
              aria-invalid={errors.prenom ? true : undefined}
              aria-describedby={errors.prenom ? "prenom-error" : undefined}
              className={inputCls}
            />
            {errors.prenom ? (
              <p id="prenom-error" className="mt-1 text-sm text-error">{errors.prenom}</p>
            ) : null}
          </div>
          <div>
            <label htmlFor="nom" className={labelCls}>
              Nom <span className="text-error">*</span>
            </label>
            <input
              id="nom"
              name="nom"
              type="text"
              autoComplete="family-name"
              required
              aria-invalid={errors.nom ? true : undefined}
              aria-describedby={errors.nom ? "nom-error" : undefined}
              className={inputCls}
            />
            {errors.nom ? (
              <p id="nom-error" className="mt-1 text-sm text-error">{errors.nom}</p>
            ) : null}
          </div>
        </div>
      ) : (
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
            <p id="name-error" className="mt-1 text-sm text-error">{errors.name}</p>
          ) : null}
        </div>
      )}

      <div className="grid gap-5 sm:grid-cols-2">
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
            <p id="email-error" className="mt-1 text-sm text-error">{errors.email}</p>
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
            placeholder="+237 6XX XXX XXX"
            aria-invalid={errors.phone ? true : undefined}
            aria-describedby={errors.phone ? "phone-error" : undefined}
            className={inputCls}
          />
          {errors.phone ? (
            <p id="phone-error" className="mt-1 text-sm text-error">{errors.phone}</p>
          ) : null}
        </div>
      </div>

      {isAdhesion ? (
        <>
          {/* ── Coordonnées + localisation ──────────────────────────── */}
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
              <label htmlFor="city" className={labelCls}>
                {t("city")} <span className="text-error">*</span>
              </label>
              <input
                id="city"
                name="city"
                type="text"
                autoComplete="address-level2"
                required
                aria-invalid={errors.city ? true : undefined}
                aria-describedby={errors.city ? "city-error" : undefined}
                className={inputCls}
              />
              {errors.city ? (
                <p id="city-error" className="mt-1 text-sm text-error">{errors.city}</p>
              ) : null}
            </div>
            <div className="sm:col-span-2">
              <label htmlFor="quartier_localite" className={labelCls}>
                Quartier / lieu précis d&apos;habitation <span className="text-error">*</span>
              </label>
              <input
                id="quartier_localite"
                name="quartier_localite"
                type="text"
                required
                placeholder="Akwa, derrière le marché central…"
                aria-invalid={errors.quartier_localite ? true : undefined}
                aria-describedby={errors.quartier_localite ? "quartier-error" : undefined}
                className={inputCls}
              />
              {errors.quartier_localite ? (
                <p id="quartier-error" className="mt-1 text-sm text-error">{errors.quartier_localite}</p>
              ) : null}
            </div>
          </div>

          {/* ── Statut pro ──────────────────────────────────────────── */}
          <div>
            <label htmlFor="statut_pro" className={labelCls}>
              Statut professionnel <span className="text-error">*</span>
            </label>
            <select
              id="statut_pro"
              name="statut_pro"
              defaultValue=""
              required
              aria-invalid={errors.statut_pro ? true : undefined}
              aria-describedby={errors.statut_pro ? "statut-error" : undefined}
              className={inputCls}
            >
              <option value="">— Choisir —</option>
              <option value="salarie">Salarié</option>
              <option value="commercant">Commerçant</option>
              <option value="artisan">Artisan</option>
              <option value="sans_emploi">Sans emploi</option>
              <option value="autre">Autre</option>
            </select>
            {errors.statut_pro ? (
              <p id="statut-error" className="mt-1 text-sm text-error">{errors.statut_pro}</p>
            ) : null}
          </div>

          {/* ── Contact d'urgence ───────────────────────────────────── */}
          <fieldset className="space-y-3 rounded-[var(--radius-md)] border border-line-200 bg-ink-50/40 p-4">
            <legend className="px-1 text-sm font-medium text-ink-700">
              Contact à prévenir en cas d&apos;urgence <span className="text-error">*</span>
            </legend>
            <div className="grid gap-5 sm:grid-cols-3">
              <div>
                <label htmlFor="urgence_nom" className={labelCls}>
                  Nom &amp; prénom <span className="text-error">*</span>
                </label>
                <input
                  id="urgence_nom"
                  name="urgence_nom"
                  type="text"
                  required
                  aria-invalid={errors.urgence_nom ? true : undefined}
                  aria-describedby={errors.urgence_nom ? "urg-nom-error" : undefined}
                  className={inputCls}
                />
                {errors.urgence_nom ? (
                  <p id="urg-nom-error" className="mt-1 text-sm text-error">{errors.urgence_nom}</p>
                ) : null}
              </div>
              <div>
                <label htmlFor="urgence_lien" className={labelCls}>
                  Lien <span className="text-error">*</span>
                </label>
                <input
                  id="urgence_lien"
                  name="urgence_lien"
                  type="text"
                  required
                  placeholder="Conjoint, frère, ami…"
                  aria-invalid={errors.urgence_lien ? true : undefined}
                  aria-describedby={errors.urgence_lien ? "urg-lien-error" : undefined}
                  className={inputCls}
                />
                {errors.urgence_lien ? (
                  <p id="urg-lien-error" className="mt-1 text-sm text-error">{errors.urgence_lien}</p>
                ) : null}
              </div>
              <div>
                <label htmlFor="urgence_phone" className={labelCls}>
                  Téléphone <span className="text-error">*</span>
                </label>
                <input
                  id="urgence_phone"
                  name="urgence_phone"
                  type="tel"
                  inputMode="tel"
                  required
                  aria-invalid={errors.urgence_phone ? true : undefined}
                  aria-describedby={errors.urgence_phone ? "urg-tel-error" : undefined}
                  className={inputCls}
                />
                {errors.urgence_phone ? (
                  <p id="urg-tel-error" className="mt-1 text-sm text-error">{errors.urgence_phone}</p>
                ) : null}
              </div>
            </div>
          </fieldset>

          {/* ── Pièces justificatives (Art.3) ──────────────────────── */}
          <fieldset className="space-y-3 rounded-[var(--radius-md)] border border-line-200 bg-ink-50/40 p-4">
            <legend className="px-1 text-sm font-medium text-ink-700">
              Pièces justificatives <span className="text-error">*</span>
            </legend>
            <p className="text-xs text-ink-600">
              Photo / scan de chaque pièce. JPG, PNG, HEIC ou PDF, 5 Mo max par fichier.
            </p>
            <div className="grid gap-3 sm:grid-cols-2">
              <FilePickerInput
                name="cni_recto"
                label="CNI — recto"
                accept={DOC_ACCEPT}
                value={pieces.cni_recto}
                onChange={(f) => setPiece("cni_recto", f)}
              />
              <FilePickerInput
                name="cni_verso"
                label="CNI — verso"
                accept={DOC_ACCEPT}
                value={pieces.cni_verso}
                onChange={(f) => setPiece("cni_verso", f)}
              />
              <FilePickerInput
                name="plan_localisation"
                label="Plan de localisation"
                accept={DOC_ACCEPT}
                value={pieces.plan_localisation}
                onChange={(f) => setPiece("plan_localisation", f)}
              />
              <FilePickerInput
                name="photo_identite"
                label="Photo d'identité"
                accept={PHOTO_ACCEPT}
                value={pieces.photo_identite}
                onChange={(f) => setPiece("photo_identite", f)}
              />
            </div>
            {piecesError ? (
              <p className="text-sm font-medium text-error">{piecesError}</p>
            ) : null}
          </fieldset>
        </>
      ) : (
        <div>
          <label htmlFor="city" className={labelCls}>
            {t("city")}
          </label>
          <input
            id="city"
            name="city"
            type="text"
            autoComplete="address-level2"
            className={inputCls}
          />
        </div>
      )}

      {/* CH-4 — Section générée depuis le FormSchema actif d'adhésion. */}
      {isAdhesion && adhesionSchema ? (
        <div className="space-y-5">
          <DynamicFields
            schema={adhesionSchema as FormSchemaPayload}
            values={extraValues}
            onChange={setExtraValues}
            excludeFieldIds={HARDCODED_ADHESION_FIELDS}
            errors={extraErrors}
          />
        </div>
      ) : null}

      <div>
        <label htmlFor="message" className={labelCls}>
          {isAdhesion ? "Quelle est votre motivation ?" : t("message")}
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


function FilePickerInput({
  name,
  label,
  accept,
  value,
  onChange,
}: {
  name: string;
  label: string;
  accept: string;
  value: File | null;
  onChange: (file: File | null) => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const filled = value !== null;
  const tooBig = filled && value!.size > MAX_PIECE_BYTES;

  return (
    <div>
      <span className={labelCls}>{label} <span className="text-error">*</span></span>
      <label
        htmlFor={`file-${name}`}
        className={cn(
          "flex cursor-pointer items-center gap-3 rounded-[var(--radius-md)] border bg-paper px-3.5 py-2.5 text-sm transition-colors",
          filled && !tooBig
            ? "border-emerald-300 bg-emerald-50/60"
            : tooBig
              ? "border-error/60 bg-error/5"
              : "border-line-200 hover:border-blue-400 hover:bg-cream",
        )}
      >
        <span
          className={cn(
            "flex size-9 shrink-0 items-center justify-center rounded-full",
            filled && !tooBig ? "bg-emerald-500 text-white" : "bg-blue-50 text-blue-600",
          )}
        >
          {filled && !tooBig ? (
            <CheckCircle2 aria-hidden="true" className="size-5" />
          ) : (
            <UploadCloud aria-hidden="true" className="size-5" />
          )}
        </span>
        <span className="min-w-0 flex-1">
          <span className="block truncate text-ink-900">
            {filled ? value!.name : "Cliquer pour choisir un fichier"}
          </span>
          <span
            className={cn(
              "block text-xs",
              tooBig ? "text-error" : filled ? "text-emerald-700" : "text-ink-500",
            )}
          >
            {filled
              ? tooBig
                ? `${fmtSize(value!.size)} — trop volumineux (max 5 Mo)`
                : fmtSize(value!.size)
              : "JPG, PNG, HEIC ou PDF · 5 Mo max"}
          </span>
        </span>
        {filled ? (
          <button
            type="button"
            onClick={(e) => {
              e.preventDefault();
              if (inputRef.current) inputRef.current.value = "";
              onChange(null);
            }}
            className="rounded-full p-1 text-ink-500 transition-colors hover:bg-ink-100 hover:text-ink-900"
            aria-label="Retirer le fichier"
          >
            <X aria-hidden="true" className="size-4" />
          </button>
        ) : null}
        <input
          ref={inputRef}
          id={`file-${name}`}
          type="file"
          accept={accept}
          className="sr-only"
          onChange={(e) => {
            const f = e.target.files?.[0] ?? null;
            onChange(f);
          }}
        />
      </label>
    </div>
  );
}
