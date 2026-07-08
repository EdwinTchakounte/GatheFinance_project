"use client";

import { useEffect, useMemo, useState } from "react";
import { EyeOff, Eye, RotateCcw, Search } from "lucide-react";

import { DataTable, type DataColumn } from "@/components/data-table";
import { Modal, ModalField, modalInputClass, buttonClasses } from "@/components/modal";
import { Pagination } from "@/components/pagination";
import {
  adminApi,
  type ApiError,
  type SocialCommentRow,
  type SocialCommentsFilters,
} from "@/lib/api";


const DEFAULT_LIMIT = 25;


export default function CommentsPage() {
  return <Inner />;
}


function Inner() {
  // Filtres
  const [q, setQ] = useState("");
  const [hidden, setHidden] = useState<SocialCommentsFilters["hidden"]>("");
  const [contentType, setContentType] =
    useState<SocialCommentsFilters["content_type"]>("");

  // Pagination
  const [limit, setLimit] = useState(DEFAULT_LIMIT);
  const [offset, setOffset] = useState(0);

  // Data
  const [items, setItems] = useState<SocialCommentRow[]>([]);
  const [count, setCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Modale hide
  const [hideTarget, setHideTarget] = useState<SocialCommentRow | null>(null);
  const [hideReason, setHideReason] = useState("");
  const [hideBusy, setHideBusy] = useState(false);
  const [hideError, setHideError] = useState<string | null>(null);

  async function reload() {
    setLoading(true);
    setError(null);
    try {
      const res = await adminApi.social.comments.list({
        q: q.trim() || undefined,
        hidden: hidden || undefined,
        content_type: contentType || undefined,
        limit,
        offset,
      });
      setItems(res.results);
      setCount(res.count);
    } catch (err) {
      const apiErr = err as ApiError;
      setError(apiErr.detail ?? "Chargement impossible.");
    } finally {
      setLoading(false);
    }
  }

  // Re-fetch a chaque changement de filtre/pagination — sauf q qui est
  // declenche par submit, comme la page audit.
  useEffect(() => {
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hidden, contentType, limit, offset]);

  function resetFilters() {
    setQ("");
    setHidden("");
    setContentType("");
    setOffset(0);
  }

  const activeFilterCount = useMemo(
    () => [q, hidden, contentType].filter((v) => v && v.trim() !== "").length,
    [q, hidden, contentType],
  );

  async function submitHide() {
    if (!hideTarget) return;
    setHideBusy(true);
    setHideError(null);
    try {
      await adminApi.social.comments.hide(hideTarget.id, hideReason.trim());
      setHideTarget(null);
      setHideReason("");
      await reload();
    } catch (err) {
      const apiErr = err as ApiError;
      setHideError(apiErr.detail ?? "Action impossible.");
    } finally {
      setHideBusy(false);
    }
  }

  async function unhide(row: SocialCommentRow) {
    try {
      await adminApi.social.comments.unhide(row.id);
      await reload();
    } catch (err) {
      const apiErr = err as ApiError;
      setError(apiErr.detail ?? "Action impossible.");
    }
  }

  const columns: DataColumn<SocialCommentRow>[] = [
    {
      key: "date",
      label: "Date",
      text: (row) => row.created_at,
      render: (row) => (
        <div className="whitespace-nowrap text-sm">
          <p className="text-ink-900">
            {new Date(row.created_at).toLocaleDateString("fr-FR", {
              day: "2-digit",
              month: "short",
              year: "2-digit",
            })}
          </p>
          <p className="font-mono text-xs text-ink-500">
            {new Date(row.created_at).toLocaleTimeString("fr-FR", {
              hour: "2-digit",
              minute: "2-digit",
            })}
          </p>
        </div>
      ),
    },
    {
      key: "auteur",
      label: "Auteur",
      locked: true,
      text: (row) => `${row.author_name} ${row.author_email}`,
      render: (row) => (
        <div>
          <p className="font-medium text-ink-900">{row.author_name}</p>
          <p className="font-mono text-xs text-ink-500">{row.author_email}</p>
        </div>
      ),
    },
    {
      key: "contenu",
      label: "Contenu",
      text: (row) => row.body,
      render: (row) => (
        <div className="max-w-md">
          {row.parent_id ? (
            <span className="mb-1 inline-block rounded bg-blue-50 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-blue-700">
              Réponse
            </span>
          ) : null}
          <p className="line-clamp-2 text-sm text-ink-700">
            {row.body || <span className="italic text-ink-400">(vide)</span>}
          </p>
        </div>
      ),
    },
    {
      key: "sur",
      label: "Sur",
      text: (row) => `${labelForContentType(row.content_type_label)} ${row.object_id}`,
      render: (row) => (
        <span className="text-sm text-ink-700">
          <span className="font-medium">
            {labelForContentType(row.content_type_label)}
          </span>
          <span className="ml-1 font-mono text-xs text-ink-500">#{row.object_id}</span>
        </span>
      ),
    },
    {
      key: "statut",
      label: "Statut",
      text: (row) => (row.hidden ? "Masqué" : "Visible"),
      render: (row) =>
        row.hidden ? (
          <span
            title={row.hidden_reason ? `Motif : ${row.hidden_reason}` : undefined}
            className="inline-flex items-center gap-1 rounded bg-terra-500/15 px-2 py-0.5 text-xs font-medium text-terra-700"
          >
            <EyeOff className="size-3" aria-hidden="true" />
            Masqué
          </span>
        ) : (
          <span className="inline-flex items-center gap-1 rounded bg-emerald/10 px-2 py-0.5 text-xs font-medium text-emerald">
            <Eye className="size-3" aria-hidden="true" />
            Visible
          </span>
        ),
    },
  ];

  return (
    <div className="px-8 py-8 lg:px-12 lg:py-10">
      <header className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="font-display text-[0.7rem] font-semibold uppercase tracking-[0.18em] text-terra-600">
            Modération
          </p>
          <h1 className="mt-2 font-editorial text-3xl font-medium text-ink-900">
            Commentaires
          </h1>
          <p className="mt-1 text-sm text-ink-600">
            Tous les commentaires postés par les membres sur les articles et
            campagnes. Masque un commentaire avec un motif si besoin — la trace
            reste en base pour l'audit.
          </p>
        </div>

        <div className="flex items-center gap-3 text-sm text-ink-600">
          <span className="font-mono text-ink-900 font-medium">{count}</span>
          <span>commentaire{count > 1 ? "s" : ""}</span>
          {activeFilterCount > 0 ? (
            <button
              type="button"
              onClick={resetFilters}
              className="inline-flex items-center gap-1.5 rounded-md border border-line-200 bg-paper px-2.5 py-1.5 text-xs font-medium text-ink-700 hover:border-blue-700 hover:text-blue-700"
            >
              <RotateCcw className="size-3.5" aria-hidden="true" />
              Réinitialiser ({activeFilterCount})
            </button>
          ) : null}
        </div>
      </header>

      {/* Barre de filtres */}
      <div className="mb-5 grid grid-cols-1 gap-3 md:grid-cols-[1fr_auto_auto]">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            setOffset(0);
            reload();
          }}
          className="relative"
        >
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-ink-400" />
          <input
            type="search"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Recherche (contenu du commentaire, email auteur)…"
            className="w-full rounded-md border border-line-200 bg-paper py-2 pl-9 pr-3 text-sm placeholder:text-ink-400 focus:border-blue-700 focus:outline-none focus:ring-1 focus:ring-blue-700"
          />
        </form>

        <select
          value={hidden ?? ""}
          onChange={(e) => {
            setHidden(e.target.value as SocialCommentsFilters["hidden"]);
            setOffset(0);
          }}
          className="rounded-md border border-line-200 bg-paper px-3 py-2 text-sm text-ink-900 focus:border-blue-700 focus:outline-none focus:ring-1 focus:ring-blue-700"
        >
          <option value="">Statut — tous</option>
          <option value="0">Visibles</option>
          <option value="1">Masqués</option>
        </select>

        <select
          value={contentType ?? ""}
          onChange={(e) => {
            setContentType(
              e.target.value as SocialCommentsFilters["content_type"],
            );
            setOffset(0);
          }}
          className="rounded-md border border-line-200 bg-paper px-3 py-2 text-sm text-ink-900 focus:border-blue-700 focus:outline-none focus:ring-1 focus:ring-blue-700"
        >
          <option value="">Type — tous</option>
          <option value="article">Articles</option>
          <option value="campaign">Campagnes</option>
        </select>
      </div>

      {error ? (
        <div className="mb-5 rounded-md border border-terra-400/40 bg-terra-50/60 px-4 py-2.5 text-sm text-terra-700">
          {error}
        </div>
      ) : null}

      {loading ? (
        <p className="text-ink-600">Chargement…</p>
      ) : (
        <>
          <DataTable
            columns={columns}
            rows={items}
            rowKey={(row) => row.id}
            emptyLabel="Aucun commentaire ne correspond à ces filtres."
            exportFilename="commentaires"
            exportTitle="Commentaires — Gathé Finance"
            actions={(row) =>
              row.hidden ? (
                <button
                  type="button"
                  onClick={() => unhide(row)}
                  className="inline-flex items-center gap-1 rounded-md border border-line-200 bg-paper px-2 py-1 text-xs font-medium text-ink-700 hover:border-emerald hover:text-emerald"
                >
                  Restaurer
                </button>
              ) : (
                <button
                  type="button"
                  onClick={() => {
                    setHideTarget(row);
                    setHideReason("");
                    setHideError(null);
                  }}
                  className="inline-flex items-center gap-1 rounded-md border border-line-200 bg-paper px-2 py-1 text-xs font-medium text-ink-700 hover:border-terra-700 hover:text-terra-700"
                >
                  Masquer
                </button>
              )
            }
          />
          {count > 0 ? (
            <Pagination
              count={count}
              limit={limit}
              offset={offset}
              onChange={setOffset}
              onLimitChange={(v) => {
                setLimit(v);
                setOffset(0);
              }}
            />
          ) : null}
        </>
      )}

      <Modal
        open={hideTarget !== null}
        onClose={() => setHideTarget(null)}
        title="Masquer ce commentaire"
        description="Le commentaire restera en base (trace audit) mais ne sera plus visible des autres membres."
        tone="danger"
        footer={
          <>
            <button
              type="button"
              onClick={() => setHideTarget(null)}
              className={buttonClasses({ variant: "ghost", size: "sm" })}
            >
              Annuler
            </button>
            <button
              type="button"
              disabled={hideBusy || hideReason.trim().length === 0}
              onClick={submitHide}
              className={buttonClasses({ variant: "danger", size: "sm" })}
            >
              {hideBusy ? "Masquage…" : "Masquer"}
            </button>
          </>
        }
      >
        {hideTarget ? (
          <div className="space-y-3">
            <div className="rounded-md border border-line-200 bg-cream/50 p-3 text-sm text-ink-700">
              <p className="font-medium text-ink-900">
                {hideTarget.author_name}
              </p>
              <p className="mt-1 line-clamp-3 text-xs">{hideTarget.body}</p>
            </div>
            <ModalField
              label="Motif (obligatoire)"
              hint="Sera consigné dans l'audit — résumé court (max 500)."
            >
              <textarea
                value={hideReason}
                onChange={(e) => setHideReason(e.target.value)}
                rows={3}
                maxLength={500}
                className={modalInputClass}
                placeholder="Ex. propos inappropriés, hors-sujet, spam…"
              />
            </ModalField>
            {hideError ? (
              <p className="text-sm text-terra-700">{hideError}</p>
            ) : null}
          </div>
        ) : null}
      </Modal>
    </div>
  );
}


function labelForContentType(raw: string): string {
  // raw vient sous la forme "app_label.model" (lowercase).
  // On expose des libelles francais pour les 2 types actuels.
  if (raw === "cms.blogpostpage") return "Article";
  if (raw === "loans.microcreditcampaign") return "Campagne";
  return raw || "—";
}
