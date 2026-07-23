"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { Container, buttonClasses } from "@gathe/ui";

import {
  portalApi,
  type ApiError,
  type ClassicSavingsSnapshot,
  type SavingsSnapshot,
  type WithdrawalModePaiement,
  type WithdrawalNetwork,
  type WithdrawalRead,
  type WithdrawalSource,
} from "@/lib/api";


/**
 * Refonte 2026 — Demande de retrait avec choix de canal :
 *   • MOMO        — l'argent est envoyé sur ton numéro Mobile Money dès que
 *                   l'admin valide la demande (payout Tara automatique).
 *   • Présentiel  — tu viens chercher l'argent en agence, l'admin te le
 *                   remettra contre signature.
 */
export default function WithdrawalRequestPage() {
  const router = useRouter();

  const [savings, setSavings] = useState<SavingsSnapshot | null>(null);
  // Épargne classique : peut être absente (compte jamais ouvert) → null.
  const [classic, setClassic] = useState<ClassicSavingsSnapshot | null>(null);
  const [mine, setMine] = useState<WithdrawalRead[]>([]);
  const [loading, setLoading] = useState(true);

  // Produit source du retrait. Une membre dont l'argent est en épargne
  // classique (cas Sinora) était bloquée tant que le retrait ne lisait que la
  // collecte : on lui laisse désormais choisir explicitement la source.
  const [source, setSource] = useState<WithdrawalSource>("collecte");
  const [mode, setMode] = useState<WithdrawalModePaiement>("momo");
  const [montant, setMontant] = useState("");
  const [motif, setMotif] = useState("");
  const [phone, setPhone] = useState("");
  const [network, setNetwork] = useState<WithdrawalNetwork>("MTN");

  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState<{ tone: "ok" | "err"; text: string } | null>(
    null,
  );

  async function load() {
    setLoading(true);
    try {
      portalApi.primeCsrf().catch(() => undefined);
      // L'épargne classique peut ne pas exister → on tolère l'échec (null).
      const [s, c, m] = await Promise.all([
        portalApi.savings(),
        portalApi.classicSavings().catch(() => null),
        portalApi.withdrawals.listMine(),
      ]);
      setSavings(s);
      setClassic(c);
      setMine(m.results);
    } finally {
      setLoading(false);
    }
  }

  // Solde disponible pour la source sélectionnée (aligné backend + mobile) :
  //   collecte         → savings.solde_disponible_retrait (= solde − retraits
  //                      déjà réservés). Fallback `solde` si backend ancien.
  //   classique libre  → classic.solde_disponible_retrait (= solde − max(placement,
  //                      gel garantie) − retraits déjà réservés). PAS solde_libre,
  //                      qui ignore le gel et le réservé → surestimait le disponible.
  const availableForSource =
    source === "classique_libre"
      ? Number(classic?.solde_disponible_retrait ?? classic?.solde_libre ?? 0)
      : Number(savings?.solde_disponible_retrait ?? savings?.solde ?? 0);
  const hasClassic = classic !== null && Number(classic.solde) > 0;

  useEffect(() => {
    load();
  }, []);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setMessage(null);
    const amount = parseInt(montant, 10);
    // Min 500 XAF aligne sur mobile (withdraw_sheet.dart l197 — regle metier
    // partagee). Etait 1 XAF avant : laxisme web qui permettait des micro-
    // retraits absurdes que le mobile rejetait.
    if (!amount || amount < 500) {
      setMessage({ tone: "err", text: "Le montant minimum est de 500 FCFA." });
      return;
    }
    if (amount > availableForSource) {
      setMessage({
        tone: "err",
        text: `Montant supérieur au disponible (${availableForSource.toLocaleString(
          "fr-FR",
        )} FCFA) sur ce produit.`,
      });
      return;
    }
    if (mode === "momo" && !phone.trim()) {
      setMessage({ tone: "err", text: "Renseigne ton numéro Mobile Money." });
      return;
    }
    setSubmitting(true);
    try {
      await portalApi.withdrawals.create({
        montant: amount,
        motif,
        source,
        mode_paiement: mode,
        recipient_phone: mode === "momo" ? phone.trim() : undefined,
        network: mode === "momo" ? network : undefined,
      });
      setMessage({
        tone: "ok",
        text:
          mode === "momo"
            ? "Demande enregistrée. Tu seras crédité sur ton numéro dès validation."
            : "Demande enregistrée. Présente-toi à l'agence dès que l'admin valide.",
      });
      setMontant("");
      setMotif("");
      setPhone("");
      await load();
    } catch (err) {
      const apiErr = err as ApiError;
      setMessage({ tone: "err", text: apiErr.detail ?? "Demande impossible." });
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Container>
      <header className="border-b border-line-200 pb-6 pt-10">
        <button
          type="button"
          onClick={() => router.push("/")}
          className="text-sm text-ink-600 hover:text-blue-700"
        >
          ← Retour au tableau de bord
        </button>
        <h1 className="mt-3 font-editorial text-3xl font-medium text-ink-900">
          Demander un retrait
        </h1>
        <p className="mt-2 text-sm text-ink-600">
          Retire tout ou partie de ton épargne. Choisis le canal de remise.
        </p>
      </header>

      <div className="mt-8 grid gap-8 lg:grid-cols-2">
        {/* Formulaire */}
        <section className="rounded-md border border-line-200 bg-paper p-6">
          <h2 className="font-editorial text-lg font-medium text-ink-900">
            Nouvelle demande
          </h2>
          <p className="mt-1 text-xs text-ink-600">
            Disponible ({source === "classique_libre" ? "épargne classique" : "collecte"}) :{" "}
            <strong>{availableForSource.toLocaleString("fr-FR")} FCFA</strong>
          </p>
          {source === "classique_libre" &&
          classic &&
          Number(classic.solde_placement_actif) > 0 ? (
            <p className="mt-1 text-[11px] text-ink-500">
              {Number(classic.solde_placement_actif).toLocaleString("fr-FR")} FCFA
              sont bloqués en placement (financement crédit) et ne sont pas
              retirables tant que le crédit financé n&apos;est pas clôturé.
            </p>
          ) : null}
          {/* Réforme garantie 2026 : part gelée en garantie d'un crédit
              (mandat avaliste / auto-garantie) et solde réellement retirable. */}
          {source === "classique_libre" &&
          classic &&
          Number(classic.montant_gele_credit) > 0 ? (
            <p className="mt-1 text-[11px] text-ink-500">
              Gelé (garantie crédit) :{" "}
              <strong>
                {Number(classic.montant_gele_credit).toLocaleString("fr-FR")} FCFA
              </strong>{" "}
              · Disponible au retrait :{" "}
              <strong>
                {Number(classic.solde_disponible_retrait).toLocaleString("fr-FR")} FCFA
              </strong>
            </p>
          ) : null}

          <form onSubmit={onSubmit} className="mt-5 space-y-4">
            {/* Source du retrait — visible seulement si le membre a une épargne
                classique alimentée (sinon la collecte est la seule option). */}
            {hasClassic ? (
              <fieldset className="space-y-2">
                <legend className="text-sm font-medium text-ink-700">
                  D&apos;où veux-tu retirer ?
                </legend>
                <SourceOption
                  value="collecte"
                  current={source}
                  onChange={setSource}
                  disabled={submitting}
                  title="Collecte journalière"
                  subtitle={`Disponible : ${Number(savings?.solde_disponible_retrait ?? savings?.solde ?? 0).toLocaleString("fr-FR")} FCFA`}
                />
                <SourceOption
                  value="classique_libre"
                  current={source}
                  onChange={setSource}
                  disabled={submitting}
                  title="Épargne classique (part libre)"
                  subtitle={`Disponible : ${Number(classic?.solde_disponible_retrait ?? classic?.solde_libre ?? 0).toLocaleString("fr-FR")} FCFA`}
                />
              </fieldset>
            ) : null}

            <div>
              <label className="block text-sm font-medium text-ink-700">
                Montant (FCFA)
              </label>
              <input
                type="number"
                min={500}
                step={500}
                value={montant}
                onChange={(e) => setMontant(e.target.value)}
                className="mt-1 w-full rounded-md border border-line-200 px-3 py-2 text-sm focus:border-emerald focus:outline-none focus:ring-1 focus:ring-emerald"
                placeholder="Ex. 25000"
                required
                disabled={submitting}
              />
              <p className="mt-1 text-[11px] text-ink-500">Minimum 500 FCFA.</p>
            </div>

            <div>
              <label className="block text-sm font-medium text-ink-700">
                Motif (facultatif)
              </label>
              <input
                type="text"
                value={motif}
                onChange={(e) => setMotif(e.target.value)}
                className="mt-1 w-full rounded-md border border-line-200 px-3 py-2 text-sm focus:border-emerald focus:outline-none focus:ring-1 focus:ring-emerald"
                placeholder="Ex. Frais scolaires"
                disabled={submitting}
              />
            </div>

            <fieldset className="space-y-2">
              <legend className="text-sm font-medium text-ink-700">
                Comment veux-tu recevoir l'argent ?
              </legend>

              <ChannelOption
                value="momo"
                current={mode}
                onChange={setMode}
                disabled={submitting}
                title="Mobile Money"
                subtitle="Crédité directement sur ton numéro MTN / Orange / Wave / Airtel dès validation."
              />
              <ChannelOption
                value="presentiel"
                current={mode}
                onChange={setMode}
                disabled={submitting}
                title="Espèces à l'agence"
                subtitle="Tu te présentes au comptoir et un agent te remet le cash."
              />
            </fieldset>

            {mode === "momo" && (
              <div className="space-y-3 rounded-md border border-line-200 bg-cream p-4">
                <div>
                  <label className="block text-xs font-medium text-ink-700">
                    Numéro Mobile Money
                  </label>
                  <input
                    type="tel"
                    value={phone}
                    onChange={(e) => setPhone(e.target.value)}
                    className="mt-1 w-full rounded-md border border-line-200 bg-paper px-3 py-2 text-sm focus:border-emerald focus:outline-none focus:ring-1 focus:ring-emerald"
                    placeholder="6 90 00 00 01"
                    required={mode === "momo"}
                    disabled={submitting}
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-ink-700">
                    Réseau
                  </label>
                  <select
                    value={network}
                    onChange={(e) => setNetwork(e.target.value as WithdrawalNetwork)}
                    className="mt-1 w-full rounded-md border border-line-200 bg-paper px-3 py-2 text-sm"
                    disabled={submitting}
                  >
                    <option value="MTN">MTN Mobile Money</option>
                    <option value="ORANGE">Orange Money</option>
                    <option value="WAVE">Wave</option>
                    <option value="AIRTEL">Airtel Money</option>
                  </select>
                </div>
              </div>
            )}

            {message && (
              <div
                className={`rounded-md px-3 py-2 text-sm ${
                  message.tone === "ok"
                    ? "border border-emerald-300 bg-emerald-50 text-emerald-800"
                    : "border border-red-300 bg-red-50 text-red-800"
                }`}
              >
                {message.text}
              </div>
            )}

            <button
              type="submit"
              disabled={submitting}
              className={buttonClasses({ variant: "primary", size: "md", fullWidth: true })}
            >
              {submitting ? "Envoi…" : "Soumettre ma demande"}
            </button>
          </form>
        </section>

        {/* Mes demandes */}
        <section className="rounded-md border border-line-200 bg-paper p-6">
          <h2 className="font-editorial text-lg font-medium text-ink-900">
            Mes demandes récentes
          </h2>
          {loading ? (
            <p className="mt-4 text-sm text-ink-500">Chargement…</p>
          ) : mine.length === 0 ? (
            <p className="mt-4 text-sm text-ink-500">Aucune demande à ce jour.</p>
          ) : (
            <ul className="mt-4 space-y-3">
              {mine.map((w) => (
                <WithdrawalCard key={w.id} w={w} />
              ))}
            </ul>
          )}
        </section>
      </div>
    </Container>
  );
}


function SourceOption({
  value,
  current,
  onChange,
  title,
  subtitle,
  disabled,
}: {
  value: WithdrawalSource;
  current: WithdrawalSource;
  onChange: (v: WithdrawalSource) => void;
  title: string;
  subtitle: string;
  disabled?: boolean;
}) {
  const checked = value === current;
  return (
    <label
      className={`flex cursor-pointer items-start gap-3 rounded-md border p-3 transition ${
        checked
          ? "border-emerald bg-emerald-50/50"
          : "border-line-200 bg-paper hover:border-emerald-300"
      } ${disabled ? "opacity-60" : ""}`}
    >
      <input
        type="radio"
        checked={checked}
        onChange={() => onChange(value)}
        disabled={disabled}
        className="mt-1"
      />
      <div>
        <p className="text-sm font-medium text-ink-900">{title}</p>
        <p className="text-xs text-ink-600">{subtitle}</p>
      </div>
    </label>
  );
}


function ChannelOption({
  value,
  current,
  onChange,
  title,
  subtitle,
  disabled,
}: {
  value: WithdrawalModePaiement;
  current: WithdrawalModePaiement;
  onChange: (v: WithdrawalModePaiement) => void;
  title: string;
  subtitle: string;
  disabled?: boolean;
}) {
  const checked = value === current;
  return (
    <label
      className={`flex cursor-pointer items-start gap-3 rounded-md border p-3 transition ${
        checked
          ? "border-emerald bg-emerald-50/50"
          : "border-line-200 bg-paper hover:border-emerald-300"
      } ${disabled ? "opacity-60" : ""}`}
    >
      <input
        type="radio"
        checked={checked}
        onChange={() => onChange(value)}
        disabled={disabled}
        className="mt-1"
      />
      <div>
        <p className="text-sm font-medium text-ink-900">{title}</p>
        <p className="text-xs text-ink-600">{subtitle}</p>
      </div>
    </label>
  );
}


function WithdrawalCard({ w }: { w: WithdrawalRead }) {
  const colorMap: Record<WithdrawalRead["statut"], string> = {
    en_attente: "border-ink-200 bg-ink-50 text-ink-700",
    approuvee: "border-amber-200 bg-amber-50 text-amber-800",
    en_payout: "border-blue-200 bg-blue-50 text-blue-700",
    completee: "border-emerald-300 bg-emerald-50 text-emerald-800",
    payout_failed: "border-red-300 bg-red-50 text-red-700",
    rejetee: "border-red-300 bg-red-50 text-red-700",
  };
  return (
    <li className={`rounded-md border p-3 ${colorMap[w.statut]}`}>
      <div className="flex items-center justify-between">
        <span className="font-semibold">
          {parseInt(w.montant).toLocaleString("fr-FR")} FCFA
        </span>
        <span className="text-xs">{w.statut_display}</span>
      </div>
      <p className="mt-1 text-xs">
        {w.source_display ? `${w.source_display} · ` : ""}
        {w.mode_paiement_display}
        {w.network ? ` · ${w.network} ${w.recipient_phone_masked}` : ""}
      </p>
      {w.motif_rejet ? (
        <p className="mt-1 text-xs italic">⚠ {w.motif_rejet}</p>
      ) : null}
      <p className="mt-1 text-[10px] opacity-70">
        Demandé le {new Date(w.date_demande).toLocaleDateString("fr-FR")}
      </p>
    </li>
  );
}
