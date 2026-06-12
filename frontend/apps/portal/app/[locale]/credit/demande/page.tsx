"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { Container, buttonClasses } from "@gathe/ui";

import { portalApi, type ApiError, type FormSchemaPublic } from "@/lib/api";
import {
  DynamicFields,
  validateDynamicFields,
  type FormSchemaPayload,
  type FormValues,
} from "@/components/form-renderer";


type Voie = "senior_brc" | "avaliste" | "campaign";

type Canal = "tara_momo" | "tara_om" | "agence_especes";

type FormState = {
  voie: Voie;
  montant_demande: string;
  duree_mois: string;
  motif: string;
  avaliste_numero: string;
  avaliste_nom: string;
  profil_cible: string;
  campaign_id: string;
  // CH-9 — Canal de réception du décaissement choisi par le membre.
  moyen_reception: Canal;
  recipient_phone: string;
};

// CH-4 — Champs câblés en dur dans cette page (UI dédiée, métier 3 voies).
// Tous les autres champs du schéma loan_request actif sont rendus par
// <DynamicFields> sous le formulaire principal.
const HARDCODED_LOAN_FIELDS = new Set([
  "montant_demande", "duree_mois", "motif", "modalite_paiement",
  "avaliste_numero", "avaliste_nom", "campaign_id", "profil_cible",
  "moyen_reception", "recipient_phone",
]);

const CANAL_LABEL: Record<Canal, string> = {
  tara_momo: "MTN Mobile Money",
  tara_om: "Orange Money",
  agence_especes: "Retrait espèces en agence",
};


/**
 * Refonte 2026 — LOT 18 — formulaire 3 voies (SENIOR_BRC / AVALISTE / CAMPAIGN).
 *
 * Le membre choisit explicitement la voie. Le backend valide via
 * ``evaluate_routes`` qui peut rejeter avec des motifs cumulés détaillés.
 */
export default function PortalLoanRequestPage() {
  const router = useRouter();
  const [eligibility, setEligibility] = useState<{
    eligible: boolean;
    plafond_max: string;
    motifs_ineligibilite: string[];
  } | null>(null);
  const [form, setForm] = useState<FormState>({
    voie: "senior_brc",
    montant_demande: "",
    duree_mois: "12",
    motif: "",
    avaliste_numero: "",
    avaliste_nom: "",
    profil_cible: "",
    campaign_id: "",
    // CH-9 — Canal de réception par défaut : MTN MoMo (le plus courant
    // pour les membres). Le membre peut changer avant soumission.
    moyen_reception: "tara_momo",
    recipient_phone: "",
  });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [errorList, setErrorList] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  // CH-4 — Champs supplémentaires saisis via le schéma loan_request actif.
  const [schema, setSchema] = useState<FormSchemaPublic | null>(null);
  const [extraValues, setExtraValues] = useState<FormValues>({});
  const [extraErrors, setExtraErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        await portalApi.primeCsrf();
        const [el, sc] = await Promise.all([
          portalApi.loans.eligibility(),
          // FormSchema optionnel : la page fonctionne aussi en mode legacy.
          portalApi.formSchema("loan_request").catch(() => null),
        ]);
        if (cancelled) return;
        setEligibility(el);
        setSchema(sc);
      } catch (err) {
        const apiErr = err as ApiError;
        if (apiErr.status === 401 || apiErr.status === 403) {
          router.replace("/connexion");
          return;
        }
        setError(apiErr.detail ?? "Impossible de charger l'éligibilité.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [router]);

  function set<K extends keyof FormState>(k: K, v: FormState[K]) {
    setForm((f) => ({ ...f, [k]: v }));
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (submitting) return;
    setError(null);
    setErrorList([]);

    // CH-4 — Valide les champs supplémentaires (FormSchema) côté client.
    if (schema) {
      const errs = validateDynamicFields(
        schema as FormSchemaPayload,
        extraValues,
        HARDCODED_LOAN_FIELDS,
      );
      if (Object.keys(errs).length > 0) {
        setExtraErrors(errs);
        const firstId = Object.keys(errs)[0];
        document.getElementById(`field-${firstId}`)?.scrollIntoView({
          behavior: "smooth", block: "center",
        });
        return;
      }
      setExtraErrors({});
    }

    // CH-9 — Validation locale : téléphone requis pour les canaux Tara.
    const phone = form.recipient_phone.trim();
    const needsPhone = form.moyen_reception === "tara_om" ||
      form.moyen_reception === "tara_momo";
    if (needsPhone && phone.length < 9) {
      setError("Renseigne un numéro Mobile Money valide pour ce canal de réception.");
      return;
    }

    setSubmitting(true);
    try {
      // CH-5 — Les valeurs de type File sont uploadées séparément après
      // création du LoanRequest. On les retire du body principal.
      const fileEntries: Array<[string, File]> = [];
      const scalarExtras: Record<string, unknown> = {};
      for (const [k, v] of Object.entries(extraValues)) {
        if (v instanceof File) fileEntries.push([k, v]);
        else scalarExtras[k] = v;
      }

      const payload: Parameters<typeof portalApi.loans.create>[0] = {
        montant_demande: Number(form.montant_demande),
        duree_mois: Number(form.duree_mois),
        motif: form.motif.trim(),
        // CH-9 — Canal de réception + téléphone (vide pour agence_especes).
        moyen_reception: form.moyen_reception,
        recipient_phone: needsPhone ? phone : "",
        // CH-4 — Champs scalaires supplémentaires routés vers extra_payload.
        ...scalarExtras,
      };
      if (form.voie === "avaliste") {
        payload.avaliste_numero = form.avaliste_numero.trim();
        payload.avaliste_nom = form.avaliste_nom.trim();
      } else if (form.voie === "campaign") {
        if (form.campaign_id.trim()) {
          payload.campaign_id = Number(form.campaign_id);
        }
        if (form.profil_cible.trim()) {
          payload.profil_cible = form.profil_cible.trim();
        }
      }

      const result = await portalApi.loans.create(payload);

      // CH-5 — Upload des fichiers attachés au LoanRequest créé.
      // Best-effort : si un upload échoue, on log mais on ne bloque pas la
      // navigation (le LoanRequest existe ; l'admin pourra demander re-upload).
      if (fileEntries.length > 0 && result.loan_request?.id) {
        for (const [fieldId, file] of fileEntries) {
          try {
            await portalApi.loans.uploadAttachment(
              result.loan_request.id,
              fieldId,
              file,
            );
          } catch (uploadErr) {
            console.warn(
              `Upload de ${fieldId} échoué — la demande est créée, ré-uploader plus tard.`,
              uploadErr,
            );
          }
        }
      }

      if (result.route === "avaliste") {
        router.push(
          `/credit?msg=avaliste_pending&request=${result.loan_request.id}`,
        );
        return;
      }
      if (result.route === "campaign") {
        router.push(
          `/credit?msg=campaign_pending&request=${result.loan_request.id}`,
        );
        return;
      }
      // SENIOR_BRC → paiement des frais
      router.push(
        `/epargne/depot?context=credit-fees&request=${result.loan_request.id}`,
      );
    } catch (err) {
      const apiErr = err as ApiError;
      setError(apiErr.detail ?? "Impossible d'envoyer la demande.");
      // Le backend renvoie souvent un tableau de motifs (voies non éligibles).
      const body = apiErr.body as { motifs?: string[] } | undefined;
      if (body?.motifs && Array.isArray(body.motifs)) {
        setErrorList(body.motifs);
      }
      setSubmitting(false);
    }
  }

  if (loading) {
    return (
      <main className="py-16">
        <Container>
          <p className="text-center text-ink-600">Chargement…</p>
        </Container>
      </main>
    );
  }

  // Plafond — pertinent uniquement pour la voie SENIOR_BRC.
  const plafondSenior = eligibility ? Number(eligibility.plafond_max) : 0;
  const universalBlock =
    eligibility?.motifs_ineligibilite?.find((m) =>
      /en cours|déjà|statut/i.test(m),
    ) || null;

  return (
    <main className="py-12 lg:py-16">
      <Container className="max-w-2xl">
        <header className="mb-8">
          <button
            type="button"
            onClick={() => router.push("/credit")}
            className="text-sm text-ink-600 transition-colors hover:text-blue-700"
          >
            ← Retour à mes crédits
          </button>
          <h1 className="mt-3 font-editorial text-3xl font-medium text-ink-900">
            Demande de crédit
          </h1>
          <p className="mt-2 text-sm text-ink-600">
            Trois voies sont possibles selon ton profil — sélectionne celle
            qui s'applique.
          </p>
        </header>

        {universalBlock && (
          <p className="mb-6 rounded-md border border-terra-400/40 bg-terra-50/60 p-4 text-sm text-terra-700">
            ⚠️ {universalBlock}
          </p>
        )}

        <form
          onSubmit={onSubmit}
          className="rounded-md border border-line-200 bg-paper p-7"
        >
          {/* Sélecteur de voie */}
          <fieldset className="space-y-2">
            <legend className="text-sm font-medium text-ink-900">
              Voie d'éligibilité
            </legend>
            <RadioCard
              checked={form.voie === "senior_brc"}
              onClick={() => set("voie", "senior_brc")}
              title="Membre ancien + BRC validé"
              hint={`Plafond : solde × 10 = ${plafondSenior.toLocaleString("fr-FR")} XAF.`}
            />
            <RadioCard
              checked={form.voie === "avaliste"}
              onClick={() => set("voie", "avaliste")}
              title="Avec un avaliste (garant)"
              hint="Tu désignes un membre ancien qui se porte garant. Il devra accepter."
            />
            <RadioCard
              checked={form.voie === "campaign"}
              onClick={() => set("voie", "campaign")}
              title="Campagne micro-crédit"
              hint="Pour les non-adhérents ou nouveaux membres ciblés (commerçants, agriculteurs…)."
            />
          </fieldset>

          {/* Montant + durée + motif (communs) */}
          <label
            className="mt-6 block text-sm font-medium text-ink-900"
            htmlFor="montant_demande"
          >
            Montant souhaité (XAF)
          </label>
          <input
            id="montant_demande"
            type="number"
            min={5000}
            step={1000}
            required
            value={form.montant_demande}
            onChange={(e) => set("montant_demande", e.target.value)}
            className={inputCls}
            placeholder="Ex. 50000"
          />
          {form.voie === "senior_brc" && (
            <p className="mt-1 text-xs text-ink-600">
              Min. 5 000 XAF · Max. {plafondSenior.toLocaleString("fr-FR")} XAF
            </p>
          )}

          <label
            className="mt-5 block text-sm font-medium text-ink-900"
            htmlFor="duree_mois"
          >
            Durée (mois)
          </label>
          <select
            id="duree_mois"
            required
            value={form.duree_mois}
            onChange={(e) => set("duree_mois", e.target.value)}
            className={inputCls}
          >
            <option value="3">3 mois</option>
            <option value="6">6 mois</option>
            <option value="12">12 mois</option>
            <option value="18">18 mois</option>
            <option value="24">24 mois</option>
            <option value="36">36 mois</option>
          </select>

          <label
            className="mt-5 block text-sm font-medium text-ink-900"
            htmlFor="motif"
          >
            Objet de la demande
          </label>
          <textarea
            id="motif"
            required
            rows={4}
            minLength={20}
            maxLength={2000}
            value={form.motif}
            onChange={(e) => set("motif", e.target.value)}
            className={inputCls}
            placeholder="Achat de matériel, fonds de roulement, formation…"
          />

          {/* Champs voie AVALISTE */}
          {form.voie === "avaliste" && (
            <div className="mt-6 space-y-3 rounded-md border border-line-200 bg-cream/40 p-4">
              <h3 className="text-sm font-semibold text-ink-900">
                Désignation de l'avaliste
              </h3>
              <p className="text-xs text-ink-600">
                Tape le numéro de membre <strong>et</strong> le nom de famille
                exacts (double-clé anti-fraude). L'avaliste recevra une
                notification pour accepter ou refuser le mandat depuis son
                espace.
              </p>
              <div>
                <label
                  className="block text-xs font-medium text-ink-700"
                  htmlFor="avaliste_numero"
                >
                  Numéro de membre
                </label>
                <input
                  id="avaliste_numero"
                  required
                  value={form.avaliste_numero}
                  onChange={(e) => set("avaliste_numero", e.target.value)}
                  className={inputCls}
                  placeholder="GF-2024-0042"
                />
              </div>
              <div>
                <label
                  className="block text-xs font-medium text-ink-700"
                  htmlFor="avaliste_nom"
                >
                  Nom de famille
                </label>
                <input
                  id="avaliste_nom"
                  required
                  value={form.avaliste_nom}
                  onChange={(e) => set("avaliste_nom", e.target.value)}
                  className={inputCls}
                  placeholder="DUPONT"
                />
              </div>
            </div>
          )}

          {/* Champs voie CAMPAIGN */}
          {form.voie === "campaign" && (
            <div className="mt-6 space-y-3 rounded-md border border-line-200 bg-cream/40 p-4">
              <h3 className="text-sm font-semibold text-ink-900">
                Campagne micro-crédit
              </h3>
              <p className="text-xs text-ink-600">
                Renseigne soit l'ID exact d'une campagne (si fourni), soit
                ton profil ciblé — le système trouvera la campagne ouverte
                correspondante.
              </p>
              <div>
                <label
                  className="block text-xs font-medium text-ink-700"
                  htmlFor="profil_cible"
                >
                  Mon profil (ex: commerçants, agriculteurs…)
                </label>
                <input
                  id="profil_cible"
                  value={form.profil_cible}
                  onChange={(e) => set("profil_cible", e.target.value)}
                  className={inputCls}
                  placeholder="commercants"
                />
              </div>
              <div>
                <label
                  className="block text-xs font-medium text-ink-700"
                  htmlFor="campaign_id"
                >
                  ID campagne (optionnel)
                </label>
                <input
                  id="campaign_id"
                  type="number"
                  min={1}
                  value={form.campaign_id}
                  onChange={(e) => set("campaign_id", e.target.value)}
                  className={inputCls}
                  placeholder="42"
                />
              </div>
            </div>
          )}

          {error && (
            <div
              role="alert"
              className="mt-4 rounded-md border border-terra-400/40 bg-terra-50/60 px-3 py-2 text-sm text-terra-700"
            >
              <p className="font-medium">{error}</p>
              {errorList.length > 0 && (
                <ul className="mt-2 list-disc space-y-0.5 pl-4 text-xs">
                  {errorList.map((m) => (
                    <li key={m}>{m}</li>
                  ))}
                </ul>
              )}
            </div>
          )}

          {/* CH-9 — Canal de réception du décaissement, à choisir avant
              soumission. Le payout Tara sera pré-rempli côté admin lors de
              la mise à disposition. */}
          <fieldset className="mt-7 rounded-md border border-line-200 bg-paper p-4">
            <legend className="px-1 text-sm font-semibold text-ink-900">
              Comment recevoir l&apos;argent une fois le crédit accordé ?
            </legend>
            <div className="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-3">
              {(["tara_momo", "tara_om", "agence_especes"] as const).map((c) => {
                const selected = form.moyen_reception === c;
                return (
                  <label
                    key={c}
                    className={[
                      "flex cursor-pointer items-center gap-2 rounded-md border p-3 text-sm transition-colors",
                      selected
                        ? "border-blue-700 bg-blue-50/60"
                        : "border-line-200 hover:border-blue-700/40",
                    ].join(" ")}
                  >
                    <input
                      type="radio"
                      name="moyen_reception"
                      value={c}
                      checked={selected}
                      onChange={() => set("moyen_reception", c)}
                      className="size-4"
                    />
                    <span
                      className={
                        selected
                          ? "font-medium text-blue-700"
                          : "text-ink-700"
                      }
                    >
                      {CANAL_LABEL[c]}
                    </span>
                  </label>
                );
              })}
            </div>
            {(form.moyen_reception === "tara_momo" ||
              form.moyen_reception === "tara_om") && (
              <div className="mt-3">
                <label
                  htmlFor="recipient_phone"
                  className="block text-xs font-medium text-ink-700"
                >
                  Numéro Mobile Money
                </label>
                <input
                  id="recipient_phone"
                  type="tel"
                  inputMode="tel"
                  placeholder="+237 6XX XX XX XX"
                  value={form.recipient_phone}
                  onChange={(e) => set("recipient_phone", e.target.value)}
                  className="mt-1 w-full rounded-md border border-line-200 bg-paper px-3 py-2 text-sm focus:border-blue-700 focus:outline-none focus:ring-1 focus:ring-blue-700"
                />
                <p className="mt-1 text-[11px] text-ink-500">
                  Ton numéro {form.moyen_reception === "tara_momo" ? "MTN" : "Orange"} sur lequel
                  l&apos;argent sera versé après approbation.
                </p>
              </div>
            )}
          </fieldset>

          <div className="mt-5 space-y-3">
            <div className="rounded-md bg-cream p-4 text-sm text-ink-700">
              <p>
                <strong>Frais d&apos;étude du dossier</strong> : à régler après
                soumission (montant configuré par l&apos;administration). Pour
                la voie <em>avaliste</em>, le paiement se déclenche après
                l&apos;acceptation du garant. Pour la voie <em>campagne</em>,
                après la validation du comité.
              </p>
            </div>
            {/* CH-7 — Mention non-remboursable bien visible. */}
            <div
              role="note"
              className="rounded-md border border-terra-400/40 bg-terra-50/60 p-3 text-xs text-terra-700"
            >
              <strong>Important — ces frais sont non-remboursables.</strong>{" "}
              Ils couvrent l&apos;instruction du dossier et la visite terrain
              éventuelle. Aucun remboursement ne sera effectué, y compris en
              cas de refus de la demande.
            </div>
          </div>

          {/* CH-4 — Section générée depuis le FormSchema actif loan_request.
              Les champs hardcoded (montant, durée, motif, voies) sont rendus
              au-dessus dans leur UI dédiée et exclus ici. */}
          {schema ? (
            <div className="mt-6 space-y-6">
              <DynamicFields
                schema={schema as FormSchemaPayload}
                values={extraValues}
                onChange={setExtraValues}
                excludeFieldIds={HARDCODED_LOAN_FIELDS}
                errors={extraErrors}
              />
            </div>
          ) : null}

          <button
            type="submit"
            disabled={submitting}
            className={
              buttonClasses({
                variant: "success",
                size: "lg",
                fullWidth: true,
              }) + " mt-6"
            }
          >
            {submitting ? "Envoi…" : "Soumettre la demande"}
          </button>
        </form>
      </Container>
    </main>
  );
}


function RadioCard({
  checked,
  onClick,
  title,
  hint,
}: {
  checked: boolean;
  onClick: () => void;
  title: string;
  hint: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`block w-full rounded-md border p-3 text-left transition-colors ${
        checked
          ? "border-blue-700 bg-blue-50/40 ring-1 ring-blue-700"
          : "border-line-200 bg-paper hover:bg-cream"
      }`}
    >
      <div className="flex items-center gap-2">
        <div
          className={`inline-block size-3.5 rounded-full border ${
            checked ? "border-blue-700 bg-blue-700" : "border-ink-400 bg-paper"
          }`}
          aria-hidden="true"
        />
        <span className="text-sm font-medium text-ink-900">{title}</span>
      </div>
      <p className="ml-5.5 mt-1 text-xs text-ink-600">{hint}</p>
    </button>
  );
}


const inputCls =
  "mt-2 block w-full rounded-md border border-line-200 bg-paper px-3 py-2 text-ink-900 outline-none transition-colors focus:border-blue-700 focus:ring-1 focus:ring-blue-700";
