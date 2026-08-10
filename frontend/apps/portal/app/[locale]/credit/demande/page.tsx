"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import { Container, buttonClasses } from "@gathe/ui";

import { portalApi, type ApiError, type Campaign, type FormSchemaPublic } from "@/lib/api";
import { fullName } from "@/lib/name";
import { computeLoanBreakdown, durationMonthsFor, type PaymentModality } from "@/lib/loan-terms";
import {
  DynamicFields,
  validateDynamicFields,
  type FormSchemaPayload,
  type FormValues,
} from "@/components/form-renderer";


type Voie = "senior_brc" | "avaliste" | "campaign" | "garantie_materielle";

type Canal = "tara_momo" | "tara_om" | "agence_especes";

type AvalisteCandidate = {
  numero_membre: string;
  nom: string;
  prenom: string;
  is_senior: boolean;
  capacite_caution: string;
};

type FormState = {
  voie: Voie;
  // L5 — Numéro de CNI du demandeur (capture identité, obligatoire).
  cni_demandeur: string;
  montant_demande: string;
  // CH-T1b : 3 modalites (journalier/hebdo/mensuel). Defaut mensuel
  // (Article 8 du Reglement). Le mobile fait pareil.
  modalite: PaymentModality;
  motif: string;
  avaliste_numero: string;
  avaliste_nom: string;
  profil_cible: string;
  campaign_id: string;
  // Réforme crédit L4 — voie garantie matérielle : le membre décrit le bien
  // mis en garantie (le titre de propriété est uploadé après création).
  garantie_description: string;
  // NB 2026-07-22 : les champs parcours/CGA/BRC (dont cga_brc_member /
  // cfp_brc_apprenant) sont rendus UNE seule fois par DynamicFields depuis le
  // FormSchema `loan_request`, pour toutes les voies. Plus de bloc codé en dur
  // ici (parité avec le mobile — fin de la duplication).
  // CH-9 — Canal de réception du décaissement choisi par le membre.
  moyen_reception: Canal;
  recipient_phone: string;
  // NOTE 2026-08 : le toggle générique `is_brc` est retiré au profit des deux
  // attributs schéma-driven « CGA BRC » (cga_adherent/cga_preuve) et « CFP BRC »
  // (ancien_apprenant/ancien_apprenant_preuve), rendus par DynamicFields.
};

// CH-4 — Champs câblés en dur dans cette page (UI dédiée, métier 3 voies).
// Tous les autres champs du schéma loan_request actif sont rendus par
// <DynamicFields> sous le formulaire principal.
//
// NB : `modalite_paiement` DOIT etre rendu par <DynamicFields> via le
// FormSchema (option seedee dans seed_form_schemas.py). On le retire de
// la liste hardcoded pour qu'il s'affiche.
//
// `duree_mois` reste hardcoded mais en LECTURE SEULE : la duree est derivee
// du montant via Article 7 (palier table). Le mobile fait pareil.
const HARDCODED_LOAN_FIELDS = new Set([
  "montant_demande", "duree_mois", "motif",
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
    plafond_sans_avaliste?: string;
    motifs_ineligibilite: string[];
  } | null>(null);
  const [form, setForm] = useState<FormState>({
    voie: "senior_brc",
    cni_demandeur: "",
    montant_demande: "",
    modalite: "mensuel",
    motif: "",
    avaliste_numero: "",
    avaliste_nom: "",
    profil_cible: "",
    campaign_id: "",
    garantie_description: "",
    // CH-9 — Canal de réception par défaut : MTN MoMo (le plus courant
    // pour les membres). Le membre peut changer avant soumission.
    moyen_reception: "tara_momo",
    recipient_phone: "",
  });
  const [submitting, setSubmitting] = useState(false);
  // Réforme crédit L4 — titre de propriété (voie garantie matérielle),
  // uploadé après création via l'endpoint attachments (clé titre_propriete).
  const [titreProprieteFile, setTitreProprieteFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [errorList, setErrorList] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  // CH-4 — Champs supplémentaires saisis via le schéma loan_request actif.
  const [schema, setSchema] = useState<FormSchemaPublic | null>(null);
  const [extraValues, setExtraValues] = useState<FormValues>({});
  const [extraErrors, setExtraErrors] = useState<Record<string, string>>({});
  // LOT 11 — Campagnes ouvertes pour le sélecteur de la voie campagne
  // (remplace la saisie manuelle d'ID). Parité avec le picker mobile.
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);

  // LOT 11 — Chargement des campagnes ouvertes + pré-remplissage depuis les
  // query params (?voie=campaign&campaign=<id>) posés par le bouton
  // « Postuler » du catalogue /credit/campagnes. Lu via window.location pour
  // éviter la frontière Suspense qu'imposerait useSearchParams (Next 15).
  useEffect(() => {
    portalApi.loans
      .activeCampaigns({ limit: 50 })
      .then((res) => setCampaigns(res.results))
      .catch(() => undefined);
    if (typeof window !== "undefined") {
      const sp = new URLSearchParams(window.location.search);
      const voieParam = sp.get("voie");
      const campaignParam = sp.get("campaign");
      setForm((f) => ({
        ...f,
        ...(voieParam === "campaign" ? { voie: "campaign" as Voie } : {}),
        ...(campaignParam ? { campaign_id: campaignParam } : {}),
      }));
    }
  }, []);

  // Typeahead avaliste (parite mobile loan_request_sheet.dart).
  const [avalisteQuery, setAvalisteQuery] = useState("");
  const [avalisteSuggestions, setAvalisteSuggestions] = useState<AvalisteCandidate[]>([]);
  const [avalisteSelected, setAvalisteSelected] = useState<AvalisteCandidate | null>(null);
  const [avalisteSearching, setAvalisteSearching] = useState(false);
  const avalisteDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // CH-7 — Recap frais d'etude affiche apres submit, AVANT redirection vers
  // /epargne/depot. Parite mobile (loan_request_sheet.dart success step).
  type FeeRecap = {
    requestId: number;
    montant: string;
    libelle: string;
  };
  const [feeRecap, setFeeRecap] = useState<FeeRecap | null>(null);

  // Derivation duree via Article 7 (palier table = source mobile).
  // Affichee en lecture seule sous le montant. Recalculee a chaque saisie.
  const dureeMoisDerivee = useMemo(() => {
    const m = Number(form.montant_demande);
    if (!Number.isFinite(m) || m < 5000) return null;
    return durationMonthsFor(m);
  }, [form.montant_demande]);

  // Recap complet (interets, total du, nb echeances) pour le membre.
  const breakdown = useMemo(() => {
    const m = Number(form.montant_demande);
    if (!Number.isFinite(m) || m < 5000) return null;
    return computeLoanBreakdown(m, form.modalite);
  }, [form.montant_demande, form.modalite]);

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

  // Typeahead avaliste : recherche backend avec debounce 300 ms (parite mobile).
  // Ne fire que si voie=avaliste, qu'aucun candidat n'est encore selectionne,
  // et que la query fait >= 2 caracteres.
  useEffect(() => {
    if (form.voie !== "avaliste" || avalisteSelected) {
      setAvalisteSuggestions([]);
      return;
    }
    const q = avalisteQuery.trim();
    if (q.length < 2) {
      setAvalisteSuggestions([]);
      return;
    }
    if (avalisteDebounceRef.current) {
      clearTimeout(avalisteDebounceRef.current);
    }
    avalisteDebounceRef.current = setTimeout(async () => {
      setAvalisteSearching(true);
      try {
        const res = await portalApi.loans.searchAvaliste(q);
        setAvalisteSuggestions(res.results);
      } catch {
        setAvalisteSuggestions([]);
      } finally {
        setAvalisteSearching(false);
      }
    }, 300);
    return () => {
      if (avalisteDebounceRef.current) {
        clearTimeout(avalisteDebounceRef.current);
      }
    };
  }, [avalisteQuery, form.voie, avalisteSelected]);

  // Quand l'utilisateur change de voie, on reset les champs avaliste pour
  // eviter qu'une selection orpheline ne pollue le payload.
  useEffect(() => {
    if (form.voie !== "avaliste") {
      setAvalisteSelected(null);
      setAvalisteQuery("");
      setAvalisteSuggestions([]);
      setForm((f) => ({ ...f, avaliste_numero: "", avaliste_nom: "" }));
    }
    // Reset des champs garantie matérielle quand on quitte cette voie.
    if (form.voie !== "garantie_materielle") {
      setTitreProprieteFile(null);
      setForm((f) => ({ ...f, garantie_description: "" }));
    }
  }, [form.voie]);

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

    // L5 — Numéro de CNI du demandeur obligatoire.
    if (form.cni_demandeur.trim().length === 0) {
      setError("Renseigne ton numéro de CNI.");
      return;
    }

    // Validation montant + duree derivee.
    const montantNum = Number(form.montant_demande);
    if (!Number.isFinite(montantNum) || montantNum < 5000) {
      setError("Le montant doit etre d'au moins 5 000 XAF.");
      return;
    }
    const dureeMois = durationMonthsFor(montantNum);

    // Task 2 — Bornes campagne (UX ; le serveur reste la source de vérité).
    if (form.voie === "campaign" && form.campaign_id) {
      const camp = campaigns.find((c) => String(c.id) === form.campaign_id);
      if (camp) {
        if (montantNum < Number(camp.montant_min)) {
          setError(
            `Le montant doit etre au moins ${Number(camp.montant_min).toLocaleString("fr-FR")} XAF pour cette campagne.`,
          );
          return;
        }
        if (montantNum > Number(camp.montant_max)) {
          setError(
            `Le montant ne peut pas depasser ${Number(camp.montant_max).toLocaleString("fr-FR")} XAF pour cette campagne.`,
          );
          return;
        }
      }
    }

    // Motif aligne mobile : 10 chars minimum (au lieu de 20 cote portail
    // historique). 2000 max conserve.
    if (form.motif.trim().length < 10) {
      setError("Le motif doit faire au moins 10 caracteres.");
      return;
    }

    // Voie avaliste : un candidat valide doit etre selectionne via le
    // typeahead (pas de saisie libre). Garde anti-typo/fraude.
    if (form.voie === "avaliste" && !avalisteSelected) {
      setError(
        "Selectionne un avaliste dans la liste (recherche par nom ou numero de membre).",
      );
      return;
    }

    // Réforme crédit L4 — voie garantie matérielle : description du bien
    // (min 10 chars) + titre de propriété obligatoires.
    if (form.voie === "garantie_materielle") {
      if (form.garantie_description.trim().length < 10) {
        setError("Décris le bien mis en garantie (au moins 10 caractères).");
        return;
      }
      if (!titreProprieteFile) {
        setError("Joins le titre de propriété du bien mis en garantie.");
        return;
      }
    }

    // (Les preuves CGA BRC / CFP BRC sont des champs `file` du schéma : leur
    // caractère requis est validé par validateDynamicFields ci-dessus.)

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
        montant_demande: montantNum,
        // Duree DERIVEE du montant (Article 7) ; le client ne la choisit pas.
        duree_mois: dureeMois,
        motif: form.motif.trim(),
        // L5 — Numéro de CNI du demandeur.
        cni_demandeur: form.cni_demandeur.trim(),
        // Modalite de paiement (3 valeurs : journalier / hebdomadaire / mensuel)
        // routee vers extra_payload via le compat layer backend.
        modalite_paiement: form.modalite,
        // CH-9 — Canal de réception + téléphone (vide pour agence_especes).
        moyen_reception: form.moyen_reception,
        recipient_phone: needsPhone ? phone : "",
        // CH-4 — Champs scalaires supplémentaires routés vers extra_payload
        // (dont cga_adherent / ancien_apprenant — CGA BRC / CFP BRC).
        ...scalarExtras,
      };
      // Les flags parcours/CGA/BRC arrivent maintenant via scalarExtras
      // (schéma dynamique), plus besoin de les injecter à la main.
      if (form.voie === "avaliste" && avalisteSelected) {
        // Numero + nom valides via le typeahead backend (anti-fraude).
        payload.avaliste_numero = avalisteSelected.numero_membre;
        payload.avaliste_nom = avalisteSelected.nom;
      } else if (form.voie === "campaign") {
        if (form.campaign_id.trim()) {
          payload.campaign_id = Number(form.campaign_id);
        }
        if (form.profil_cible.trim()) {
          payload.profil_cible = form.profil_cible.trim();
        }
      } else if (form.voie === "garantie_materielle") {
        // Réforme crédit L4 — le backend route vers la voie garantie_materielle
        // (statut en_attente) via ce flag + la description du bien.
        payload.garantie_materielle = true;
        payload.garantie_description = form.garantie_description.trim();
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

      // (Les preuves parcours/CGA/BRC — cga_brc_preuve, cfp_brc_preuve,
      // ancien_apprenant_preuve, cga_preuve — sont des champs `file` du schéma :
      // elles remontent déjà via `fileEntries` ci-dessus. Plus de traitement
      // dédié ici, parité mobile.)

      // Réforme crédit L4 — titre de propriété (clé titre_propriete) uploadé
      // après création via le même endpoint attachments que les autres preuves.
      if (
        form.voie === "garantie_materielle" &&
        titreProprieteFile &&
        result.loan_request?.id
      ) {
        try {
          await portalApi.loans.uploadAttachment(
            result.loan_request.id,
            "titre_propriete",
            titreProprieteFile,
          );
        } catch (uploadErr) {
          console.warn("Upload du titre de propriété échoué.", uploadErr);
        }
      }

      // (Les preuves CGA BRC / CFP BRC — cga_preuve / ancien_apprenant_preuve —
      // sont des champs `file` du schéma : déjà uploadées via la boucle
      // fileEntries ci-dessus, comme toute pièce du FormSchema.)

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
      // Réforme crédit L4 — voie garantie matérielle : demande en attente de
      // vérification du bien par la coopérative (pas de frais immédiats).
      if (result.route === "garantie_materielle") {
        router.push(
          `/credit?msg=garantie_pending&request=${result.loan_request.id}`,
        );
        return;
      }
      // SENIOR_BRC → recap frais d'etude AVANT redirection vers /epargne/depot.
      // Le membre voit le montant + la mention "non-remboursable" + un bouton
      // explicite. Parite mobile (CH-7 success step).
      if (result.frais_a_payer) {
        setFeeRecap({
          requestId: result.loan_request.id,
          montant: result.frais_a_payer.montant,
          libelle: result.frais_a_payer.libelle,
        });
        setSubmitting(false);
        return;
      }
      // Pas de frais a payer (cas degenere) : on redirige direct.
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
  // Réforme garantie 2026 : montant empruntable SANS avaliste (= épargne
  // classique disponible). INDICATIF pour toutes les voies — au-delà, le membre
  // doit désigner un avaliste (le serveur reste seul juge). Fallback plafond_max.
  const plafondSansAvaliste = eligibility
    ? Number(eligibility.plafond_sans_avaliste ?? eligibility.plafond_max)
    : 0;

  // Task 2 — Bornes campagne validées côté client (UX ; le serveur fait foi).
  // Erreur inline quand un montant est hors [montant_min ; montant_max] de la
  // campagne sélectionnée.
  const selectedCampaign =
    form.voie === "campaign" && form.campaign_id
      ? campaigns.find((c) => String(c.id) === form.campaign_id) ?? null
      : null;
  const montantNumLive = Number(form.montant_demande);
  const campaignBoundsError =
    selectedCampaign && Number.isFinite(montantNumLive) && montantNumLive > 0
      ? montantNumLive < Number(selectedCampaign.montant_min)
        ? `Le montant doit être au moins ${Number(selectedCampaign.montant_min).toLocaleString("fr-FR")} XAF pour cette campagne.`
        : montantNumLive > Number(selectedCampaign.montant_max)
          ? `Le montant ne peut pas dépasser ${Number(selectedCampaign.montant_max).toLocaleString("fr-FR")} XAF pour cette campagne.`
          : null
      : null;
  const universalBlock =
    eligibility?.motifs_ineligibilite?.find((m) =>
      /en cours|déjà|statut/i.test(m),
    ) || null;

  // CH-7 — Apres soumission, on affiche un recap des frais d'etude AVANT
  // de rediriger vers /epargne/depot. Parite mobile : le membre voit le
  // montant + la mention non-remboursable + un bouton explicite "Payer".
  if (feeRecap) {
    return (
      <main className="py-12 lg:py-16">
        <Container className="max-w-lg">
          <div className="rounded-md border border-line-200 bg-paper p-8 text-center">
            <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-emerald-100">
              <span className="text-3xl">✓</span>
            </div>
            <h1 className="mt-5 font-editorial text-2xl font-medium text-ink-900">
              Demande enregistree
            </h1>
            <p className="mt-2 text-sm text-ink-600">
              Ta demande est sauvegardee. Pour qu&apos;elle passe en
              instruction, regle maintenant les frais d&apos;etude.
            </p>

            <div className="mt-6 rounded-md border border-blue-300 bg-blue-50/60 p-5">
              <p className="text-xs font-medium uppercase tracking-wide text-blue-700">
                {feeRecap.libelle}
              </p>
              <p className="mt-2 font-editorial text-3xl font-semibold text-ink-900">
                {Number(feeRecap.montant).toLocaleString("fr-FR")} XAF
              </p>
            </div>

            <div className="mt-4 rounded-md border border-terra-400/40 bg-terra-50/60 p-3 text-xs text-terra-700">
              <strong>Important — ces frais sont non-remboursables.</strong>{" "}
              Ils couvrent l&apos;instruction du dossier et la visite terrain
              eventuelle. Aucun remboursement ne sera effectue, y compris en
              cas de refus.
            </div>

            <div className="mt-6 space-y-2">
              <button
                type="button"
                onClick={() =>
                  router.push(
                    `/epargne/depot?context=credit-fees&request=${feeRecap.requestId}`,
                  )
                }
                className={buttonClasses({
                  variant: "success",
                  size: "lg",
                  fullWidth: true,
                })}
              >
                Payer {Number(feeRecap.montant).toLocaleString("fr-FR")} XAF maintenant
              </button>
              <button
                type="button"
                onClick={() => router.push("/credit")}
                className="block w-full text-sm font-medium text-ink-600 transition-colors hover:text-ink-900"
              >
                Payer plus tard
              </button>
              <p className="text-[11px] text-ink-500">
                Tu pourras retrouver ta demande en attente sur la page Credit
                et regler les frais a tout moment.
              </p>
            </div>
          </div>
        </Container>
      </main>
    );
  }

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
            Plusieurs voies sont possibles selon ton profil — sélectionne
            celle qui s'applique.
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
              title="Sur mon épargne"
              hint={`Crédit couvert par ton épargne — plafond : ${plafondSenior.toLocaleString("fr-FR")} XAF.`}
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
            <RadioCard
              checked={form.voie === "garantie_materielle"}
              onClick={() => set("voie", "garantie_materielle")}
              title="Garantie matérielle (bien)"
              hint="Tu mets un bien en garantie (véhicule, terrain, matériel…) avec son titre de propriété."
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
          {/* Réforme garantie 2026 : le montant est libre (min 5 000, pas de
              plafond dur). L'épargne classique disponible n'est qu'un repère —
              au-delà, on désigne un avaliste. La campagne impose ses bornes. */}
          {selectedCampaign ? (
            <p className="mt-1 text-xs text-ink-600">
              Campagne « {selectedCampaign.nom} » : de{" "}
              {Number(selectedCampaign.montant_min).toLocaleString("fr-FR")} à{" "}
              {Number(selectedCampaign.montant_max).toLocaleString("fr-FR")} XAF.
            </p>
          ) : (
            <p className="mt-1 text-xs text-ink-600">
              Min. 5 000 XAF. Sans avaliste jusqu&apos;à{" "}
              {plafondSansAvaliste.toLocaleString("fr-FR")} XAF (votre épargne).
              Au-delà, désignez un avaliste.
            </p>
          )}
          {campaignBoundsError && (
            <p className="mt-1 text-xs font-medium text-terra-700">
              {campaignBoundsError}
            </p>
          )}

          {/* Duree : DERIVEE du montant via Article 7 (palier table). Le
              membre ne choisit pas. Aligne sur mobile. */}
          <div className="mt-5">
            <p className="block text-sm font-medium text-ink-900">
              Duree de remboursement (Article 7)
            </p>
            <div className="mt-2 flex items-center gap-3 rounded-md border border-line-200 bg-cream/40 px-3 py-2.5">
              <span className="text-2xl font-semibold text-ink-900">
                {dureeMoisDerivee ?? "—"}
              </span>
              <span className="text-sm text-ink-600">
                mois — derivee automatiquement du montant
              </span>
            </div>
            {breakdown && (
              <p className="mt-1 text-[11px] text-ink-500">
                À rembourser :{" "}
                <strong className="text-ink-700">
                  {breakdown.montantTotalDu.toLocaleString("fr-FR")} XAF
                </strong>{" "}
                (intérêts flat 10 %), en une fois ou plusieurs versements
                libres, <strong className="text-ink-700">avant la date
                butoir</strong> (fixée à l'approbation).
              </p>
            )}
          </div>

          {/* Règle 2026 « date butoir unique » : plus de modalité imposée
              (journalier/hebdo/mensuel). La durée (fonction du montant) fixe
              une date limite ; le membre rembourse librement d'ici là. Le
              sélecteur de modalité a donc été retiré. */}

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
            minLength={10}
            maxLength={2000}
            value={form.motif}
            onChange={(e) => set("motif", e.target.value)}
            className={inputCls}
            placeholder="Achat de materiel, fonds de roulement, formation…"
          />
          <p className="mt-1 text-[11px] text-ink-500">
            10 caracteres minimum.
          </p>

          {/* L5 — Numéro de CNI du demandeur (capture identité obligatoire). */}
          <label
            className="mt-5 block text-sm font-medium text-ink-900"
            htmlFor="cni_demandeur"
          >
            Numéro de CNI
          </label>
          <input
            id="cni_demandeur"
            type="text"
            required
            value={form.cni_demandeur}
            onChange={(e) => set("cni_demandeur", e.target.value)}
            className={inputCls}
            placeholder="Ex. 123456789"
            autoComplete="off"
          />
          <p className="mt-1 text-[11px] text-ink-500">
            Ton numéro de carte nationale d&apos;identité.
          </p>

          {/* Voie AVALISTE : typeahead backend (anti-fraude) - parite mobile.
              On recherche un membre Senior actif puis on le selectionne. La
              capacite de caution restante est affichee sous chaque candidat. */}
          {form.voie === "avaliste" && (
            <div className="mt-6 space-y-3 rounded-md border border-line-200 bg-cream/40 p-4">
              <h3 className="text-sm font-semibold text-ink-900">
                Designation de l'avaliste
              </h3>
              <p className="text-xs text-ink-600">
                Tape le nom ou le numero de membre. Seuls les membres anciens
                (Senior) actifs sont propose. L'avaliste recevra une notification
                pour accepter ou refuser le mandat depuis son espace.
              </p>

              {avalisteSelected ? (
                <div className="rounded-md border border-blue-300 bg-blue-50/60 p-3">
                  <p className="text-sm font-semibold text-blue-900">
                    {fullName(avalisteSelected.prenom, avalisteSelected.nom)}
                  </p>
                  <p className="mt-0.5 font-mono text-[11px] text-blue-800">
                    {avalisteSelected.numero_membre}
                  </p>
                  <p className="mt-1 text-[11px] text-ink-600">
                    Capacité de garantie restante :{" "}
                    <strong>
                      {Number(avalisteSelected.capacite_caution).toLocaleString("fr-FR")} XAF
                    </strong>
                    .
                  </p>
                  <button
                    type="button"
                    onClick={() => {
                      setAvalisteSelected(null);
                      setAvalisteQuery("");
                    }}
                    className="mt-2 text-xs font-medium text-blue-700 underline-offset-2 hover:underline"
                  >
                    Changer d'avaliste
                  </button>
                </div>
              ) : (
                <div>
                  <input
                    id="avaliste_search"
                    type="text"
                    value={avalisteQuery}
                    onChange={(e) => setAvalisteQuery(e.target.value)}
                    placeholder="Tape un nom ou un numero (min 2 lettres)"
                    className={inputCls}
                    autoComplete="off"
                  />
                  {avalisteSearching && (
                    <p className="mt-1 text-[11px] text-ink-500">Recherche…</p>
                  )}
                  {!avalisteSearching && avalisteQuery.trim().length >= 2 && avalisteSuggestions.length === 0 && (
                    <p className="mt-1 text-[11px] text-ink-500">
                      Aucun membre Senior actif trouve.
                    </p>
                  )}
                  {avalisteSuggestions.length > 0 && (
                    <ul className="mt-2 max-h-60 divide-y divide-line-200 overflow-y-auto rounded-md border border-line-200 bg-paper">
                      {avalisteSuggestions.map((c) => {
                        const capacity = Number(c.capacite_caution);
                        const disabled = capacity <= 0;
                        return (
                          <li key={c.numero_membre}>
                            <button
                              type="button"
                              disabled={disabled}
                              onClick={() => {
                                setAvalisteSelected(c);
                                setAvalisteSuggestions([]);
                              }}
                              className={[
                                "block w-full px-3 py-2 text-left text-sm transition-colors",
                                disabled
                                  ? "cursor-not-allowed bg-paper/50 text-ink-400"
                                  : "hover:bg-blue-50/40",
                              ].join(" ")}
                            >
                              <span className="font-medium text-ink-900">
                                {fullName(c.prenom, c.nom)}
                              </span>
                              <span className="ml-2 font-mono text-[11px] text-ink-500">
                                {c.numero_membre}
                              </span>
                              <span className="block text-[11px] text-ink-600">
                                Capacite :{" "}
                                {capacity > 0
                                  ? `${capacity.toLocaleString("fr-FR")} XAF dispo`
                                  : "saturee (pas de marge)"}
                              </span>
                            </button>
                          </li>
                        );
                      })}
                    </ul>
                  )}
                </div>
              )}
            </div>
          )}

          {/* Champs voie CAMPAIGN — sélecteur des campagnes ouvertes
              (parité picker mobile ; remplace la saisie manuelle d'ID). */}
          {form.voie === "campaign" && (
            <div className="mt-6 space-y-3 rounded-md border border-line-200 bg-cream/40 p-4">
              <div className="flex items-center justify-between gap-3">
                <h3 className="text-sm font-semibold text-ink-900">
                  Campagne micro-crédit
                </h3>
                <button
                  type="button"
                  onClick={() => router.push("/credit/campagnes")}
                  className="text-xs font-medium text-blue-700 hover:underline"
                >
                  Voir les campagnes →
                </button>
              </div>

              {campaigns.length > 0 ? (
                <div>
                  <label
                    className="block text-xs font-medium text-ink-700"
                    htmlFor="campaign_id"
                  >
                    Choisis une campagne ouverte
                  </label>
                  <select
                    id="campaign_id"
                    value={form.campaign_id}
                    onChange={(e) => set("campaign_id", e.target.value)}
                    className={inputCls}
                  >
                    <option value="">— Sélectionne une campagne —</option>
                    {campaigns.map((c) => (
                      <option key={c.id} value={String(c.id)}>
                        {c.nom}
                        {c.profil_cible ? ` · ${c.profil_cible}` : ""} (
                        {Number(c.montant_min).toLocaleString("fr-FR")}–
                        {Number(c.montant_max).toLocaleString("fr-FR")} XAF)
                      </option>
                    ))}
                  </select>
                  <p className="mt-1 text-[11px] text-ink-500">
                    Aucune campagne ne te correspond ? Renseigne ton profil
                    ci-dessous, le système cherchera une campagne ouverte.
                  </p>
                </div>
              ) : (
                <p className="text-xs text-ink-600">
                  Aucune campagne ouverte listée pour le moment. Tu peux
                  renseigner ton profil ciblé — le système cherchera une
                  campagne ouverte correspondante.
                </p>
              )}

              <div>
                <label
                  className="block text-xs font-medium text-ink-700"
                  htmlFor="profil_cible"
                >
                  Mon profil (optionnel — ex: commerçants, agriculteurs…)
                </label>
                <input
                  id="profil_cible"
                  value={form.profil_cible}
                  onChange={(e) => set("profil_cible", e.target.value)}
                  className={inputCls}
                  placeholder="commercants"
                />
              </div>
            </div>
          )}

          {/* Voie GARANTIE MATÉRIELLE — description du bien + titre de propriété.
              Le bien est vérifié par la coopérative avant décaissement. */}
          {form.voie === "garantie_materielle" && (
            <div className="mt-6 space-y-3 rounded-md border border-line-200 bg-cream/40 p-4">
              <h3 className="text-sm font-semibold text-ink-900">
                Bien mis en garantie
              </h3>
              <p className="text-xs text-ink-600">
                Décris le bien que tu mets en garantie et joins son titre de
                propriété. La coopérative vérifie le bien avant d&apos;accorder
                le crédit.
              </p>

              <div>
                <label
                  className="block text-xs font-medium text-ink-700"
                  htmlFor="garantie_description"
                >
                  Description du bien
                </label>
                <textarea
                  id="garantie_description"
                  rows={3}
                  minLength={10}
                  maxLength={2000}
                  value={form.garantie_description}
                  onChange={(e) => set("garantie_description", e.target.value)}
                  className={inputCls}
                  placeholder="Ex. Véhicule Toyota Corolla 2015, immatriculation LT-234-AB, valeur estimée 3 000 000 XAF…"
                />
                <p className="mt-1 text-[11px] text-ink-500">
                  10 caractères minimum.
                </p>
              </div>

              <div>
                <label
                  className="block text-xs font-medium text-ink-700"
                  htmlFor="titre_propriete"
                >
                  Titre de propriété
                </label>
                <input
                  id="titre_propriete"
                  type="file"
                  accept="image/*,application/pdf"
                  onChange={(e) =>
                    setTitreProprieteFile(e.target.files?.[0] ?? null)
                  }
                  className="mt-1 block w-full text-xs text-ink-600 file:mr-3 file:rounded-md file:border-0 file:bg-emerald file:px-3 file:py-1.5 file:text-white"
                />
                <p className="mt-1 text-[11px] text-ink-500">
                  Image ou PDF. Obligatoire pour cette voie.
                </p>
              </div>
            </div>
          )}

          {/* CGA BRC / CFP BRC : rendus par DynamicFields (schéma) ci-dessus,
              couplables à toute voie — plus de toggle « BRC » hardcodé ici. */}

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
            disabled={submitting || Boolean(campaignBoundsError)}
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
