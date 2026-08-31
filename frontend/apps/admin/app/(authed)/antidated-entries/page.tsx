"use client";

import { useEffect, useState } from "react";
import { CalendarClock, Check, Ban, RotateCcw } from "lucide-react";

import { ModalField, modalInputClass } from "@/components/modal";
import { PageHeader } from "@/components/page-header";
import { buttonClasses } from "@gathe/ui";
import {
  adminApi,
  type AntidatedEntryRow,
  type ApiError,
  type Member,
  type SpecialCollectionCycleRow,
} from "@/lib/api";
import { fullName } from "@/lib/name";

type AntidatedProduct = "collecte" | "classique" | "tontine" | "caisse_scolaire";

// Produit antidaté → type de collecte particulière (pour charger les cycles).
const PRODUCT_TO_COLLECTION: Partial<Record<AntidatedProduct, string>> = {
  tontine: "tontine_alimentaire",
  caisse_scolaire: "caisse_scolaire",
};


export default function AntidatedEntriesPage() {
  return <Inner />;
}


function todayIso(): string {
  // Pas de Date.now() ici : c'est du code client (navigateur), pas le sandbox
  // de workflow. On borne le sélecteur de date à aujourd'hui.
  return new Date().toISOString().slice(0, 10);
}


type Tab = "saisie" | "historique";

function Inner() {
  const [tab, setTab] = useState<Tab>("saisie");
  const [selectedMember, setSelectedMember] = useState<Member | null>(null);
  const [flash, setFlash] = useState<string | null>(null);

  function showFlash(msg: string) {
    setFlash(msg);
    setTimeout(() => setFlash(null), 6000);
  }

  const tabBtn = (t: Tab, label: string) => (
    <button
      type="button"
      onClick={() => setTab(t)}
      className={
        "border-b-2 px-1 pb-2 text-sm font-medium transition-colors " +
        (tab === t
          ? "border-emerald-600 text-ink-900"
          : "border-transparent text-ink-500 hover:text-ink-800")
      }
    >
      {label}
    </button>
  );

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Épargne"
        title="Saisies antidatées"
        description="Reprise d&apos;historique des carnets papier : recrée un carnet à sa date d&apos;origine et ressaisit ses versements et retraits à leur vraie date. Aucune clôture n&apos;est rejouée, aucun paiement réel n&apos;est déclenché. Le solde du compte est simplement aligné sur le carnet."
      />

      {flash ? (
        <div className="fixed bottom-6 left-1/2 z-50 -translate-x-1/2 rounded-md bg-emerald px-4 py-2.5 text-sm font-medium text-white shadow-lg">
          <span className="inline-flex items-center gap-2">
            <Check className="size-4" aria-hidden="true" />
            {flash}
          </span>
        </div>
      ) : null}

      <div className="flex gap-6 border-b border-line-200">
        {tabBtn("saisie", "Nouvelle saisie")}
        {tabBtn("historique", "Historique")}
      </div>

      {tab === "saisie" ? (
        <div className="max-w-2xl space-y-6">
          <MemberPicker selected={selectedMember} onSelect={setSelectedMember} />

          {selectedMember ? (
            <>
              <BookletForm member={selectedMember} onDone={showFlash} />
              <EntryForm member={selectedMember} onDone={showFlash} />
            </>
          ) : (
            <p className="rounded-md border border-dashed border-line-200 bg-paper/70 p-8 text-center text-sm text-ink-500">
              Sélectionne d&apos;abord un membre pour saisir son historique.
            </p>
          )}
        </div>
      ) : (
        <HistoryTab onDone={showFlash} />
      )}
    </div>
  );
}


// ── Sélection membre (pattern repris du cash-in) ─────────────────────────────

function MemberPicker({
  selected,
  onSelect,
}: {
  selected: Member | null;
  onSelect: (m: Member | null) => void;
}) {
  const [query, setQuery] = useState("");
  const [members, setMembers] = useState<Member[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (selected) return;
    const q = query.trim();
    if (q.length < 2) {
      setMembers([]);
      return;
    }
    const handle = setTimeout(async () => {
      setLoading(true);
      try {
        const res = await adminApi.members.list({ q, limit: 10 });
        setMembers(res.results);
      } catch {
        setMembers([]);
      } finally {
        setLoading(false);
      }
    }, 250);
    return () => clearTimeout(handle);
  }, [query, selected]);

  return (
    <section className="rounded-md border border-line-200 bg-paper p-5">
      <ModalField
        label="Membre"
        hint="Recherche par numéro, nom ou prénom (≥ 2 caractères)."
      >
        {selected ? (
          <div className="flex items-center justify-between rounded-md border border-emerald-200 bg-emerald-50/60 px-3 py-2 text-sm">
            <div>
              <p className="font-medium text-ink-900">
                {fullName(selected.prenom, selected.nom)}
              </p>
              <p className="font-mono text-[10px] text-ink-500">
                {selected.numero_membre} · {selected.statut}
              </p>
            </div>
            <button
              type="button"
              onClick={() => onSelect(null)}
              className="text-xs font-medium text-emerald-700 hover:underline"
            >
              Changer
            </button>
          </div>
        ) : (
          <>
            <input
              type="search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Tape numéro, nom…"
              className={modalInputClass}
            />
            {loading ? (
              <p className="mt-1 text-[11px] text-ink-500">Recherche…</p>
            ) : null}
            {members.length > 0 ? (
              <ul className="mt-2 max-h-48 overflow-y-auto rounded-md border border-line-200">
                {members.map((m) => (
                  <li key={m.id}>
                    <button
                      type="button"
                      onClick={() => {
                        onSelect(m);
                        setMembers([]);
                        setQuery("");
                      }}
                      className="block w-full px-3 py-2 text-left text-xs hover:bg-line-100"
                    >
                      <span className="font-medium text-ink-900">
                        {fullName(m.prenom, m.nom)}
                      </span>
                      <span className="ml-2 font-mono text-[10px] text-ink-500">
                        {m.numero_membre} · {m.statut}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            ) : null}
          </>
        )}
      </ModalField>
    </section>
  );
}


// ── Créer un carnet antidaté ─────────────────────────────────────────────────

function BookletForm({
  member,
  onDone,
}: {
  member: Member;
  onDone: (msg: string) => void;
}) {
  const [date, setDate] = useState("");
  const [montant, setMontant] = useState("");
  const [note, setNote] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    setError(null);
    if (!date) {
      setError("Indique la date d'origine du carnet.");
      return;
    }
    setSubmitting(true);
    try {
      const res = await adminApi.antidated.createBooklet({
        member_id: member.id,
        date,
        montant: montant.trim() ? Number(montant) : undefined,
        note: note.trim() || undefined,
      });
      onDone(`Carnet antidaté créé (#${res.booklet_order_id}, ${res.date}).`);
      setDate("");
      setMontant("");
      setNote("");
    } catch (e) {
      setError((e as ApiError).detail ?? "Création impossible.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="rounded-md border border-line-200 bg-paper p-5">
      <h2 className="flex items-center gap-2 font-display text-sm font-semibold text-ink-900">
        <CalendarClock className="size-4 text-terra-600" aria-hidden="true" />
        Créer un carnet antidaté
      </h2>
      <p className="mt-1 text-xs text-ink-500">
        À faire une fois, avant de saisir les écritures : les versements et
        retraits s&apos;y rattacheront automatiquement selon leur date. Le
        montant est optionnel (0 par défaut : le carnet existe déjà, on ne
        ré-encaisse pas de frais).
      </p>

      {error ? (
        <p className="mt-3 rounded-md border border-rose-200 bg-rose-50/60 p-2.5 text-xs text-rose-700">
          {error}
        </p>
      ) : null}

      <div className="mt-4 grid gap-4 sm:grid-cols-2">
        <ModalField label="Date d'origine du carnet">
          <input
            type="date"
            value={date}
            max={todayIso()}
            onChange={(e) => setDate(e.target.value)}
            className={modalInputClass}
          />
        </ModalField>
        <ModalField label="Frais perçus à l'époque (optionnel)">
          <input
            type="number"
            min={0}
            value={montant}
            onChange={(e) => setMontant(e.target.value)}
            placeholder="0"
            className={modalInputClass}
          />
        </ModalField>
      </div>
      <ModalField label="Note (optionnel)">
        <input
          type="text"
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder="Ex. carnet 2026 repris du papier"
          className={modalInputClass}
        />
      </ModalField>

      <div className="mt-4 flex justify-end">
        <button
          type="button"
          onClick={submit}
          disabled={submitting || !date}
          className={buttonClasses({ variant: "primary", size: "sm" })}
        >
          {submitting ? "Création…" : "Créer le carnet"}
        </button>
      </div>
    </section>
  );
}


// ── Saisir une écriture antidatée ────────────────────────────────────────────

function EntryForm({
  member,
  onDone,
}: {
  member: Member;
  onDone: (msg: string) => void;
}) {
  const [product, setProduct] = useState<AntidatedProduct>("collecte");
  const [sens, setSens] = useState<"depot" | "retrait">("depot");
  const [montant, setMontant] = useState("");
  const [date, setDate] = useState("");
  const [note, setNote] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Collectes particulières : collecte ciblée (obligatoire pour tontine/caisse).
  const [cycles, setCycles] = useState<SpecialCollectionCycleRow[]>([]);
  const [cycleId, setCycleId] = useState("");
  const collectionType = PRODUCT_TO_COLLECTION[product];
  const isSpecial = collectionType != null;

  useEffect(() => {
    if (!isSpecial || !collectionType) {
      setCycles([]);
      return;
    }
    let cancelled = false;
    adminApi.specialCollections.cycles
      .list(collectionType)
      .then((rows) => {
        if (!cancelled) setCycles(rows);
      })
      .catch(() => {
        if (!cancelled) setCycles([]);
      });
    return () => {
      cancelled = true;
    };
  }, [isSpecial, collectionType]);

  async function submit() {
    setError(null);
    const montantNum = Number(montant);
    if (!Number.isFinite(montantNum) || montantNum <= 0) {
      setError("Montant invalide.");
      return;
    }
    if (!date) {
      setError("Indique la date de l'écriture.");
      return;
    }
    if (isSpecial && !cycleId) {
      setError("Choisis la collecte concernée.");
      return;
    }
    setSubmitting(true);
    try {
      const res = await adminApi.antidated.recordEntry({
        member_id: member.id,
        product,
        sens,
        montant: montantNum,
        date,
        cycle_id: isSpecial ? Number(cycleId) : undefined,
        note: note.trim() || undefined,
      });
      onDone(
        `${sens === "depot" ? "Dépôt" : "Retrait"} enregistré · nouveau solde ` +
          `${Number(res.solde_apres).toLocaleString("fr-FR")} XAF.`,
      );
      setMontant("");
      // On garde produit/sens/date : la ressaisie enchaîne souvent des lignes
      // proches. Seul le montant se vide.
    } catch (e) {
      setError((e as ApiError).detail ?? "Saisie impossible.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="rounded-md border border-line-200 bg-paper p-5">
      <h2 className="font-display text-sm font-semibold text-ink-900">
        Saisir une écriture
      </h2>
      <p className="mt-1 text-xs text-ink-500">
        Un versement ou un retrait à sa vraie date. Reprise d'historique : un
        retrait peut être saisi même s'il dépasse le solde du moment (le solde
        peut passer négatif, l'ordre réel des écritures est respecté).
      </p>

      {error ? (
        <p className="mt-3 rounded-md border border-rose-200 bg-rose-50/60 p-2.5 text-xs text-rose-700">
          {error}
        </p>
      ) : null}

      <div className="mt-4 grid gap-4 sm:grid-cols-2">
        <ModalField label="Produit">
          <select
            value={product}
            onChange={(e) => {
              setProduct(e.target.value as AntidatedProduct);
              setCycleId("");
            }}
            className={modalInputClass}
          >
            <option value="collecte">Collecte journalière</option>
            <option value="classique">Épargne classique</option>
            <option value="tontine">Tontine</option>
            <option value="caisse_scolaire">Caisse scolaire</option>
          </select>
        </ModalField>
        <ModalField label="Sens">
          <select
            value={sens}
            onChange={(e) => setSens(e.target.value as "depot" | "retrait")}
            className={modalInputClass}
          >
            <option value="depot">Versement</option>
            <option value="retrait">Retrait</option>
          </select>
        </ModalField>
        <ModalField label="Montant (XAF)">
          <input
            type="number"
            min={1}
            value={montant}
            onChange={(e) => setMontant(e.target.value)}
            placeholder="Ex. 1000"
            className={modalInputClass}
          />
        </ModalField>
        <ModalField label="Date de l'écriture">
          <input
            type="date"
            value={date}
            max={todayIso()}
            onChange={(e) => setDate(e.target.value)}
            className={modalInputClass}
          />
        </ModalField>
        {isSpecial ? (
          <ModalField label="Collecte concernée">
            {cycles.length === 0 ? (
              <p className="rounded-md border border-amber-200 bg-amber-50/60 p-2 text-xs text-amber-700">
                Aucune collecte de ce type. Crée-la d'abord.
              </p>
            ) : (
              <select
                value={cycleId}
                onChange={(e) => setCycleId(e.target.value)}
                className={modalInputClass}
              >
                <option value="">— Choisir —</option>
                {cycles.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.nom}
                    {c.is_open ? "" : " (close)"}
                  </option>
                ))}
              </select>
            )}
          </ModalField>
        ) : null}
      </div>
      <ModalField label="Note (optionnel)">
        <input
          type="text"
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder="Ex. report ligne carnet page 3"
          className={modalInputClass}
        />
      </ModalField>

      <div className="mt-4 flex justify-end">
        <button
          type="button"
          onClick={submit}
          disabled={submitting || !montant || !date}
          className={buttonClasses({ variant: "primary", size: "sm" })}
        >
          {submitting ? "Enregistrement…" : "Enregistrer l'écriture"}
        </button>
      </div>
    </section>
  );
}


// ── Onglet Historique des saisies antidatées + invalidation ─────────────────

const PRODUCT_LABEL: Record<AntidatedEntryRow["product"], string> = {
  collecte: "Collecte journalière",
  classique: "Épargne classique",
  special: "Tontine / Caisse",
};

function HistoryTab({ onDone }: { onDone: (msg: string) => void }) {
  const [rows, setRows] = useState<AntidatedEntryRow[]>([]);
  const [count, setCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [productFilter, setProductFilter] = useState<"" | AntidatedEntryRow["product"]>("");
  const [showReversed, setShowReversed] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const res = await adminApi.antidated.list({
        product: productFilter || undefined,
        include_reversed: showReversed,
        limit: 200,
      });
      setRows(res.results);
      setCount(res.count);
    } catch (e) {
      setError((e as ApiError).detail ?? "Chargement impossible.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [productFilter, showReversed]);

  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-center gap-4">
        <select
          value={productFilter}
          onChange={(e) =>
            setProductFilter(e.target.value as "" | AntidatedEntryRow["product"])
          }
          className={modalInputClass + " max-w-xs"}
        >
          <option value="">Tous les produits</option>
          <option value="collecte">Collecte journalière</option>
          <option value="classique">Épargne classique</option>
          <option value="special">Tontine / Caisse</option>
        </select>
        <label className="inline-flex items-center gap-2 text-sm text-ink-700">
          <input
            type="checkbox"
            checked={showReversed}
            onChange={(e) => setShowReversed(e.target.checked)}
          />
          Afficher les invalidées
        </label>
        <button
          type="button"
          onClick={load}
          className="inline-flex items-center gap-1.5 text-sm font-medium text-emerald-700 hover:underline"
        >
          <RotateCcw className="size-3.5" aria-hidden="true" /> Rafraîchir
        </button>
        <span className="ml-auto text-xs text-ink-500">{count} écriture(s)</span>
      </div>

      {error ? (
        <p className="rounded-md border border-rose-200 bg-rose-50/60 p-2.5 text-xs text-rose-700">
          {error}
        </p>
      ) : null}

      {loading ? (
        <p className="text-sm text-ink-500">Chargement…</p>
      ) : rows.length === 0 ? (
        <p className="rounded-md border border-dashed border-line-200 bg-paper/70 p-8 text-center text-sm text-ink-500">
          Aucune saisie antidatée.
        </p>
      ) : (
        <div className="overflow-x-auto rounded-md border border-line-200">
          <table className="w-full min-w-[860px] text-left text-sm">
            <thead className="bg-line-100/60 text-[11px] uppercase tracking-wide text-ink-500">
              <tr>
                <th className="px-3 py-2 font-medium">Date opération</th>
                <th className="px-3 py-2 font-medium">Membre</th>
                <th className="px-3 py-2 font-medium">Produit</th>
                <th className="px-3 py-2 font-medium">Sens</th>
                <th className="px-3 py-2 text-right font-medium">Montant</th>
                <th className="px-3 py-2 font-medium">Saisie le</th>
                <th className="px-3 py-2 font-medium">Statut</th>
                <th className="px-3 py-2" />
              </tr>
            </thead>
            <tbody className="divide-y divide-line-200">
              {rows.map((r) => (
                <HistoryRow
                  key={`${r.entite_type}-${r.id}`}
                  row={r}
                  onDone={(msg) => {
                    onDone(msg);
                    load();
                  }}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function HistoryRow({
  row,
  onDone,
}: {
  row: AntidatedEntryRow;
  onDone: (msg: string) => void;
}) {
  const [confirming, setConfirming] = useState(false);
  const [motif, setMotif] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function invalidate() {
    setBusy(true);
    setError(null);
    try {
      const res = await adminApi.antidated.invalidate({
        entite_type: row.entite_type,
        entite_id: row.id,
        motif: motif.trim() || undefined,
      });
      const warn = res.went_negative
        ? ` ⚠ Le solde du membre est désormais négatif (${Number(
            res.solde_apres,
          ).toLocaleString("fr-FR")} XAF).`
        : "";
      onDone(`Écriture invalidée · nouveau solde ${Number(
        res.solde_apres,
      ).toLocaleString("fr-FR")} XAF.${warn}`);
    } catch (e) {
      setError((e as ApiError).detail ?? "Invalidation impossible.");
      setBusy(false);
    }
  }

  const montant = Number(row.montant).toLocaleString("fr-FR");
  const strike = row.reversed ? "text-ink-400 line-through" : "text-ink-900";

  return (
    <>
      <tr className={row.reversed ? "bg-rose-50/30" : ""}>
        <td className={"px-3 py-2 font-mono text-xs " + (row.reversed ? "text-ink-400" : "text-ink-700")}>
          {row.date}
        </td>
        <td className="px-3 py-2">
          <span className={strike}>{row.membre.nom}</span>
          <span className="ml-1 font-mono text-[10px] text-ink-500">
            {row.membre.numero}
          </span>
        </td>
        <td className="px-3 py-2 text-xs text-ink-600">
          {PRODUCT_LABEL[row.product]}
        </td>
        <td className="px-3 py-2">
          <span
            className={
              "rounded px-1.5 py-0.5 text-[11px] font-medium " +
              (row.sens === "depot"
                ? "bg-emerald-50 text-emerald-700"
                : "bg-amber-50 text-amber-700")
            }
          >
            {row.sens === "depot" ? "Versement" : "Retrait"}
          </span>
        </td>
        <td className={"px-3 py-2 text-right font-mono " + strike}>{montant}</td>
        <td className="px-3 py-2 font-mono text-[11px] text-ink-500">
          {row.saisi_le.slice(0, 10)}
        </td>
        <td className="px-3 py-2">
          {row.reversed ? (
            <span
              className="rounded bg-rose-100 px-1.5 py-0.5 text-[11px] font-medium text-rose-700"
              title={row.reversal_note || undefined}
            >
              Invalidée
            </span>
          ) : (
            <span className="rounded bg-line-100 px-1.5 py-0.5 text-[11px] text-ink-600">
              Active
            </span>
          )}
        </td>
        <td className="px-3 py-2 text-right">
          {!row.reversed ? (
            <button
              type="button"
              onClick={() => setConfirming((v) => !v)}
              className="inline-flex items-center gap-1 text-xs font-medium text-rose-600 hover:underline"
            >
              <Ban className="size-3.5" aria-hidden="true" /> Invalider
            </button>
          ) : null}
        </td>
      </tr>
      {confirming && !row.reversed ? (
        <tr className="bg-rose-50/40">
          <td colSpan={8} className="px-3 py-3">
            <div className="space-y-2">
              <p className="text-xs text-ink-700">
                Confirme l&apos;invalidation de cette écriture ({montant} XAF).
                Son effet sur le solde sera contre-passé (une écriture inverse est
                créée). Le solde peut devenir négatif.
              </p>
              {error ? (
                <p className="rounded-md border border-rose-200 bg-rose-50 p-2 text-xs text-rose-700">
                  {error}
                </p>
              ) : null}
              <div className="flex flex-wrap items-center gap-2">
                <input
                  type="text"
                  value={motif}
                  onChange={(e) => setMotif(e.target.value)}
                  placeholder="Motif (optionnel)"
                  className={modalInputClass + " max-w-sm"}
                />
                <button
                  type="button"
                  onClick={invalidate}
                  disabled={busy}
                  className={buttonClasses({ variant: "danger", size: "sm" })}
                >
                  {busy ? "Invalidation…" : "Confirmer l'invalidation"}
                </button>
                <button
                  type="button"
                  onClick={() => setConfirming(false)}
                  className="text-xs font-medium text-ink-500 hover:underline"
                >
                  Annuler
                </button>
              </div>
            </div>
          </td>
        </tr>
      ) : null}
    </>
  );
}
