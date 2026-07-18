"use client";

import { useEffect, useState } from "react";
import { Check, X, Mail, Phone, MapPin, Eye, FileText } from "lucide-react";

import { buttonClasses } from "@gathe/ui";

import { Modal, ModalField, modalInputClass } from "@/components/modal";
import { adminApi, type ApiError, type MembershipRequest } from "@/lib/api";


export default function MembershipRequestsPage() {
  return (
    
      <Inner />
    
  );
}

function Inner() {
  const [filter, setFilter] = useState<"en_attente" | "approuvee" | "rejetee" | "">("en_attente");
  const [items, setItems] = useState<MembershipRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [actingId, setActingId] = useState<number | null>(null);
  const [message, setMessage] = useState<{ tone: "ok" | "err"; text: string } | null>(null);

  // Modal state
  const [approveTarget, setApproveTarget] = useState<MembershipRequest | null>(null);
  const [rejectTarget, setRejectTarget] = useState<MembershipRequest | null>(null);
  const [detailTarget, setDetailTarget] = useState<MembershipRequest | null>(null);

  async function reload() {
    setLoading(true);
    try {
      adminApi.primeCsrf().catch(() => undefined);
      const list = await adminApi.membershipRequests.list(filter || undefined);
      setItems(list);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { reload(); /* eslint-disable-next-line */ }, [filter]);

  async function submitApprove(payload: { prenom: string; nom: string }) {
    if (!approveTarget) return;
    setActingId(approveTarget.id);
    try {
      await adminApi.membershipRequests.approve(approveTarget.id, payload);
      setMessage({ tone: "ok", text: `Demande #${approveTarget.id} approuvée — Member créé.` });
      setApproveTarget(null);
      await reload();
    } catch (err) {
      const apiErr = err as ApiError;
      setMessage({ tone: "err", text: apiErr.detail ?? "Approbation impossible." });
    } finally {
      setActingId(null);
    }
  }

  async function submitReject(motif: string) {
    if (!rejectTarget) return;
    setActingId(rejectTarget.id);
    try {
      await adminApi.membershipRequests.reject(rejectTarget.id, motif);
      setMessage({ tone: "ok", text: `Demande #${rejectTarget.id} rejetée.` });
      setRejectTarget(null);
      await reload();
    } catch (err) {
      const apiErr = err as ApiError;
      setMessage({ tone: "err", text: apiErr.detail ?? "Rejet impossible." });
    } finally {
      setActingId(null);
    }
  }

  return (
    <div className="space-y-6">
      <header className="mb-8 flex items-end justify-between gap-4">
        <div>
          <p className="font-display text-[0.7rem] font-semibold uppercase tracking-[0.18em] text-terra-600">
            Adhésions
          </p>
          <h1 className="mt-2 font-editorial text-3xl font-medium text-ink-900">
            Demandes d'adhésion
          </h1>
          <p className="mt-1 text-sm text-ink-600">
            Examine, approuve ou rejette les demandes soumises depuis la vitrine.
          </p>
        </div>

        <div className="flex items-center gap-1 rounded-md border border-line-200 bg-paper p-1">
          {[
            { v: "en_attente", l: "En attente" },
            { v: "approuvee", l: "Approuvées" },
            { v: "rejetee", l: "Rejetées" },
            { v: "", l: "Toutes" },
          ].map((opt) => (
            <button
              key={opt.v}
              type="button"
              onClick={() => setFilter(opt.v as "en_attente" | "approuvee" | "rejetee" | "")}
              className={[
                "rounded px-3 py-1.5 text-xs font-medium transition-colors",
                filter === opt.v ? "bg-blue-700 text-white" : "text-ink-700 hover:text-blue-700",
              ].join(" ")}
            >
              {opt.l}
            </button>
          ))}
        </div>
      </header>

      {message ? (
        <div className={
          "mb-5 rounded-md px-4 py-2.5 text-sm " +
          (message.tone === "ok"
            ? "bg-emerald/10 text-emerald border border-emerald/30"
            : "bg-terra-50/60 text-terra-700 border border-terra-400/40")
        }>
          {message.text}
        </div>
      ) : null}

      {loading ? (
        <p className="text-ink-600">Chargement…</p>
      ) : items.length === 0 ? (
        <p className="rounded-md border border-dashed border-line-200 bg-paper/70 p-12 text-center text-sm text-ink-600">
          Aucune demande dans ce filtre.
        </p>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-line-100 bg-paper shadow-xs">
          <table className="table-admin">
            <thead>
              <tr>
                <th>Demandeur</th>
                <th>Contact</th>
                <th>Motivation</th>
                <th>Reçue le</th>
                <th>Statut</th>
                <th className="text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {items.map((r) => (
                <tr key={r.id}>
                  <td>
                    <p className="font-medium text-ink-900">
                      {r.prenom ? `${r.prenom} ` : ""}{r.nom}
                    </p>
                    <p className="text-xs text-ink-600 font-mono">#{r.id}</p>
                  </td>
                  <td className="space-y-1">
                    <p className="flex items-center gap-1.5 text-sm">
                      <Mail className="size-3.5 text-ink-400" aria-hidden="true" />{r.email}
                    </p>
                    {r.phone ? (
                      <p className="flex items-center gap-1.5 text-xs text-ink-600">
                        <Phone className="size-3 text-ink-400" aria-hidden="true" />{r.phone}
                      </p>
                    ) : null}
                    {r.city ? (
                      <p className="flex items-center gap-1.5 text-xs text-ink-600">
                        <MapPin className="size-3 text-ink-400" aria-hidden="true" />{r.city}
                      </p>
                    ) : null}
                  </td>
                  <td className="max-w-xs">
                    <p className="line-clamp-3 text-sm text-ink-700">
                      {r.motivation || <em className="text-ink-400">non renseignée</em>}
                    </p>
                  </td>
                  <td className="text-sm text-ink-600 whitespace-nowrap">
                    {new Date(r.created_at).toLocaleDateString("fr-FR", { day: "2-digit", month: "short", year: "2-digit" })}
                  </td>
                  <td>
                    <span className={
                      "pill " +
                      (r.statut === "en_attente" ? "pill-warning"
                       : r.statut === "approuvee" ? "pill-success" : "pill-danger")
                    }>{r.statut_display}</span>
                    {r.statut === "rejetee" && r.motif_rejet ? (
                      <p className="mt-1 text-xs text-terra-700 max-w-[12rem]">{r.motif_rejet}</p>
                    ) : null}
                  </td>
                  <td className="text-right">
                    <div className="flex justify-end gap-2">
                      <button
                        type="button"
                        onClick={() => setDetailTarget(r)}
                        className={buttonClasses({ variant: "ghost", size: "sm" })}
                      >
                        <Eye className="size-3.5" aria-hidden="true" />
                        Détail
                      </button>
                      {r.statut === "en_attente" ? (
                        <>
                          <button
                            type="button"
                            onClick={() => setApproveTarget(r)}
                            disabled={actingId === r.id}
                            title="Approuver la demande"
                            className={buttonClasses({ variant: "success", size: "sm" })}
                          >
                            <Check className="size-3.5" aria-hidden="true" />
                            Approuver
                          </button>
                          <button
                            type="button"
                            onClick={() => setRejectTarget(r)}
                            disabled={actingId === r.id}
                            className={buttonClasses({ variant: "ghost", size: "sm" })}
                          >
                            <X className="size-3.5" aria-hidden="true" />
                            Rejeter
                          </button>
                        </>
                      ) : null}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <ApproveMembershipModal
        target={approveTarget}
        onClose={() => setApproveTarget(null)}
        onSubmit={submitApprove}
        submitting={actingId !== null}
      />
      <RejectMembershipModal
        target={rejectTarget}
        onClose={() => setRejectTarget(null)}
        onSubmit={submitReject}
        submitting={actingId !== null}
      />
      <DetailMembershipModal
        target={detailTarget}
        onClose={() => setDetailTarget(null)}
      />
    </div>
  );
}


function ApproveMembershipModal({
  target,
  onClose,
  onSubmit,
  submitting,
}: {
  target: MembershipRequest | null;
  onClose: () => void;
  onSubmit: (payload: { prenom: string; nom: string }) => void;
  submitting: boolean;
}) {
  const [prenom, setPrenom] = useState("");
  const [nom, setNom] = useState("");

  // Reset fields each time the modal opens with a new target.
  useEffect(() => {
    if (target) {
      setPrenom(target.prenom || target.nom.split(" ")[0] || "");
      setNom(target.nom || "");
    }
  }, [target]);

  const open = target !== null;
  const trimmedNom = nom.trim();
  const canSubmit = !submitting && trimmedNom.length > 0;

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Approuver l'adhésion"
      description={
        target
          ? `Création du compte membre pour ${target.email}.`
          : undefined
      }
      tone="success"
      footer={
        <>
          <button
            type="button"
            onClick={onClose}
            className={buttonClasses({ variant: "ghost", size: "sm" })}
          >
            Annuler
          </button>
          <button
            type="button"
            onClick={() => canSubmit && onSubmit({ prenom: prenom.trim(), nom: trimmedNom })}
            disabled={!canSubmit}
            className={buttonClasses({ variant: "success", size: "sm" })}
          >
            <Check className="size-3.5" aria-hidden="true" />
            Approuver et créer le compte
          </button>
        </>
      }
    >
      <div className="space-y-4">
        <ModalField label="Prénom" hint="Tel qu'il figurera sur le carnet de membre.">
          <input
            type="text"
            value={prenom}
            onChange={(e) => setPrenom(e.target.value)}
            className={modalInputClass}
            autoFocus
          />
        </ModalField>
        <ModalField label="Nom" hint="Obligatoire.">
          <input
            type="text"
            value={nom}
            onChange={(e) => setNom(e.target.value)}
            className={modalInputClass}
            required
          />
        </ModalField>
      </div>
    </Modal>
  );
}


function RejectMembershipModal({
  target,
  onClose,
  onSubmit,
  submitting,
}: {
  target: MembershipRequest | null;
  onClose: () => void;
  onSubmit: (motif: string) => void;
  submitting: boolean;
}) {
  const [motif, setMotif] = useState("");

  useEffect(() => {
    if (target) setMotif("");
  }, [target]);

  const open = target !== null;
  const trimmed = motif.trim();
  const canSubmit = !submitting && trimmed.length > 0;

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Rejeter la demande"
      description={
        target
          ? `La notification de rejet sera envoyée à ${target.email}.`
          : undefined
      }
      tone="danger"
      footer={
        <>
          <button
            type="button"
            onClick={onClose}
            className={buttonClasses({ variant: "ghost", size: "sm" })}
          >
            Annuler
          </button>
          <button
            type="button"
            onClick={() => canSubmit && onSubmit(trimmed)}
            disabled={!canSubmit}
            className={buttonClasses({ variant: "danger", size: "sm" })}
          >
            <X className="size-3.5" aria-hidden="true" />
            Confirmer le rejet
          </button>
        </>
      }
    >
      <ModalField
        label="Motif"
        hint="Concis et factuel — sera communiqué au demandeur."
      >
        <textarea
          value={motif}
          onChange={(e) => setMotif(e.target.value)}
          rows={4}
          className={modalInputClass + " resize-y"}
          placeholder="Ex. : pièces justificatives manquantes (CNI recto/verso)."
          autoFocus
        />
      </ModalField>
    </Modal>
  );
}


function DetailMembershipModal({
  target,
  onClose,
}: {
  target: MembershipRequest | null;
  onClose: () => void;
}) {
  if (!target) return null;
  const t = target;

  return (
    <Modal
      open={!!target}
      onClose={onClose}
      title={`Demande #${t.id} . ${t.prenom} ${t.nom}`}
      description="Vue complete des informations soumises par le demandeur."
      footer={
        <button
          type="button"
          onClick={onClose}
          className={buttonClasses({ variant: "ghost", size: "md" })}
        >
          Fermer
        </button>
      }
    >
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Email">{t.email || "."}</Field>
        <Field label="Telephone">{t.phone || "."}</Field>
        <Field label="WhatsApp">{t.whatsapp || "."}</Field>
        <Field label="Statut pro">{t.statut_pro || "."}</Field>
        <Field label="Ville">{t.city || "."}</Field>
        <Field label="Quartier / localite">{t.quartier_localite || "."}</Field>
      </div>

      <div className="mt-5 rounded-md border border-line-200 bg-cream/50 p-4">
        <h4 className="text-xs font-semibold uppercase tracking-wide text-ink-700">
          Contact d'urgence
        </h4>
        <div className="mt-2 grid gap-3 sm:grid-cols-3">
          <Field label="Nom">{t.urgence_nom || "."}</Field>
          <Field label="Lien">{t.urgence_lien || "."}</Field>
          <Field label="Telephone">{t.urgence_phone || "."}</Field>
        </div>
      </div>

      <div className="mt-5">
        <h4 className="text-xs font-semibold uppercase tracking-wide text-ink-700">
          Motivation
        </h4>
        <p className="mt-2 whitespace-pre-wrap text-sm text-ink-800">
          {t.motivation || <em className="text-ink-400">non renseignee</em>}
        </p>
      </div>

      <div className="mt-5">
        <h4 className="text-xs font-semibold uppercase tracking-wide text-ink-700">
          Documents soumis
        </h4>
        <div className="mt-2 grid gap-3 sm:grid-cols-2">
          <DocCard label="CNI recto" url={t.cni_recto_url} />
          <DocCard label="CNI verso" url={t.cni_verso_url} />
          <DocCard label="Photo identite" url={t.photo_identite_url} />
          <DocCard label="Plan de localisation" url={t.plan_localisation_url} />
        </div>
      </div>
    </Modal>
  );
}


function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <p className="text-[0.65rem] font-mono uppercase tracking-wider text-ink-500">{label}</p>
      <p className="mt-0.5 break-all text-sm text-ink-900">{children}</p>
    </div>
  );
}


function DocCard({ label, url }: { label: string; url: string | null }) {
  if (!url) {
    return (
      <div className="flex items-center justify-between rounded-md border border-dashed border-line-200 bg-paper/50 px-3 py-2.5">
        <span className="text-xs text-ink-500">{label}</span>
        <span className="text-[0.65rem] uppercase text-ink-400">non soumis</span>
      </div>
    );
  }
  const isImage = /\.(jpe?g|png|webp|gif)(\?|$)/i.test(url);
  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      className="group flex items-center gap-3 rounded-md border border-line-200 bg-paper p-2.5 transition-colors hover:border-blue-700 hover:bg-blue-50/40"
    >
      {isImage ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={url} alt={label} className="size-14 rounded object-cover" />
      ) : (
        <span className="flex size-14 items-center justify-center rounded bg-blue-50 text-blue-700">
          <FileText className="size-6" />
        </span>
      )}
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium text-ink-900">{label}</p>
        <p className="truncate text-xs text-blue-700 group-hover:underline">
          Ouvrir le fichier
        </p>
      </div>
    </a>
  );
}
