"use client";

import { useEffect, useState } from "react";
import { CalendarClock, Check } from "lucide-react";

import { ModalField, modalInputClass } from "@/components/modal";
import { buttonClasses } from "@gathe/ui";
import { adminApi, type ApiError, type Member } from "@/lib/api";


export default function AntidatedEntriesPage() {
  return <Inner />;
}


function todayIso(): string {
  // Pas de Date.now() ici : c'est du code client (navigateur), pas le sandbox
  // de workflow. On borne le sélecteur de date à aujourd'hui.
  return new Date().toISOString().slice(0, 10);
}


function Inner() {
  const [selectedMember, setSelectedMember] = useState<Member | null>(null);
  const [flash, setFlash] = useState<string | null>(null);

  function showFlash(msg: string) {
    setFlash(msg);
    setTimeout(() => setFlash(null), 5000);
  }

  return (
    <div className="px-8 py-8 lg:px-12 lg:py-10">
      <header className="mb-6">
        <p className="font-display text-[0.7rem] font-semibold uppercase tracking-[0.18em] text-terra-600">
          Épargne
        </p>
        <h1 className="mt-2 font-editorial text-3xl font-medium text-ink-900">
          Saisies antidatées
        </h1>
        <p className="mt-1 max-w-2xl text-sm text-ink-600">
          Reprise d&apos;historique des carnets papier : recrée un carnet à sa
          date d&apos;origine et ressaisit ses versements et retraits à leur
          vraie date. Aucune clôture n&apos;est rejouée, aucun paiement réel
          n&apos;est déclenché. Le solde du compte est simplement aligné sur le
          carnet.
        </p>
      </header>

      {flash ? (
        <div className="fixed bottom-6 left-1/2 z-50 -translate-x-1/2 rounded-md bg-emerald px-4 py-2.5 text-sm font-medium text-white shadow-lg">
          <span className="inline-flex items-center gap-2">
            <Check className="size-4" aria-hidden="true" />
            {flash}
          </span>
        </div>
      ) : null}

      <div className="max-w-2xl space-y-6">
        <MemberPicker
          selected={selectedMember}
          onSelect={setSelectedMember}
        />

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
                {selected.prenom} {selected.nom}
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
                        {m.prenom} {m.nom}
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
  const [product, setProduct] = useState<"collecte" | "classique">("collecte");
  const [sens, setSens] = useState<"depot" | "retrait">("depot");
  const [montant, setMontant] = useState("");
  const [date, setDate] = useState("");
  const [note, setNote] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

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
    setSubmitting(true);
    try {
      const res = await adminApi.antidated.recordEntry({
        member_id: member.id,
        product,
        sens,
        montant: montantNum,
        date,
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
        Un versement ou un retrait à sa vraie date. Un retrait ne peut pas
        rendre le solde négatif : ressaisis les dépôts avant les retraits.
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
            onChange={(e) =>
              setProduct(e.target.value as "collecte" | "classique")
            }
            className={modalInputClass}
          >
            <option value="collecte">Collecte journalière</option>
            <option value="classique">Épargne classique</option>
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
