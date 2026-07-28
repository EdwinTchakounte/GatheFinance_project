"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  ChevronLeft,
  ChevronRight,
  Eye,
  Globe,
  ImagePlus,
  Loader2,
  MessageSquare,
  Power,
} from "lucide-react";

import { Modal } from "@/components/modal";
import {
  adminApi,
  type AdminBlogArticle,
  type ArticleCommentRow,
} from "@/lib/api";

const PAGE_SIZE = 12;

// Le panneau d'édition complet vit dans le Wagtail admin (Django), PAS dans
// l'app Next admin (qui n'a aucune route /admin → un lien relatif "/admin"
// tombait sur du 404/500 en dev). On cible donc toujours le backend.
function wagtailAdminBase(): string {
  const envBase = process.env.NEXT_PUBLIC_WAGTAIL_ADMIN_URL;
  if (envBase) return envBase.replace(/\/+$/, "");
  if (typeof window === "undefined") return "/admin";
  const host = window.location.hostname;
  if (host.endsWith(".gathe-finance.horus-lab.com")) {
    return "https://api.gathe-finance.horus-lab.com/admin";
  }
  // Dev local : le backend Django (Wagtail) écoute sur le port 8200.
  return "http://localhost:8200/admin";
}

// Anti-cache sur une image fraîchement changée pour forcer le rechargement.
function bust(url: string): string {
  const sep = url.includes("?") ? "&" : "?";
  return `${url}${sep}v=${Date.now()}`;
}

function fmtDate(d: string | null): string {
  if (!d) return "Brouillon";
  return new Date(d).toLocaleDateString("fr-FR", {
    day: "2-digit",
    month: "short",
    year: "2-digit",
  });
}

export default function BlogAdminPage() {
  const [locale, setLocale] = useState<"fr" | "en">("fr");
  const [items, setItems] = useState<AdminBlogArticle[]>([]);
  const [count, setCount] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [commentsFor, setCommentsFor] = useState<AdminBlogArticle | null>(null);

  const reload = useCallback(() => {
    setLoading(true);
    setError(null);
    adminApi.cmsBlog
      .list({ locale, limit: PAGE_SIZE, offset })
      .then((data) => {
        setItems(data.results);
        setCount(data.count);
      })
      .catch(() => setError("Échec du chargement des articles."))
      .finally(() => setLoading(false));
  }, [locale, offset]);

  useEffect(() => {
    reload();
  }, [reload]);

  // Reset de la pagination quand on change de langue.
  useEffect(() => {
    setOffset(0);
  }, [locale]);

  // Applique localement la nouvelle image renvoyée par l'upload (autoritaire).
  const patchCover = useCallback(
    (id: number, cover: { url: string } | null) => {
      setItems((prev) =>
        prev.map((it) => (it.id === id ? { ...it, cover_image_data: cover } : it)),
      );
    },
    [],
  );

  const patchLive = useCallback((id: number, live: boolean) => {
    setItems((prev) => prev.map((it) => (it.id === id ? { ...it, live } : it)));
  }, []);

  const totalPages = Math.max(1, Math.ceil(count / PAGE_SIZE));
  const currentPage = Math.floor(offset / PAGE_SIZE) + 1;

  return (
    <div className="space-y-6">
      <header>
        <p className="font-display text-[0.7rem] font-semibold uppercase tracking-[0.18em] text-blue-700">
          Vitrine · CMS
        </p>
        <h1 className="mt-2 font-editorial text-2xl font-medium text-ink-900 sm:text-3xl">
          Articles du blog
        </h1>
        <p className="mt-1 text-sm text-ink-600">
          Active/désactive un article, change son image, et prévisualise ses
          commentaires. L'édition complète du contenu se fait dans Wagtail.
        </p>
      </header>

      <div className="flex flex-wrap items-center gap-3">
        <div className="inline-flex rounded-full bg-paper p-1 ring-1 ring-line-200">
          {(["fr", "en"] as const).map((l) => (
            <button
              key={l}
              onClick={() => setLocale(l)}
              className={
                "rounded-full px-3 py-1 text-xs font-semibold uppercase " +
                (locale === l ? "bg-blue-700 text-white" : "text-ink-600 hover:text-ink-900")
              }
            >
              {l}
            </button>
          ))}
        </div>

        <span className="text-xs text-ink-500">
          {count} article{count > 1 ? "s" : ""}
        </span>

        <a
          href={`${wagtailAdminBase()}/pages/`}
          target="_blank"
          rel="noopener noreferrer"
          className="ml-auto inline-flex items-center gap-2 rounded-lg bg-blue-700 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-blue-800"
        >
          Ouvrir Wagtail Admin →
        </a>
      </div>

      {error ? (
        <p className="rounded-lg border border-terra-400/40 bg-terra-50/60 p-3 text-sm text-terra-700">
          {error}
        </p>
      ) : null}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {loading ? (
          Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="h-72 animate-pulse rounded-xl bg-line-100" />
          ))
        ) : items.length === 0 ? (
          <p className="col-span-full rounded-xl border border-line-200 bg-paper p-8 text-center text-sm text-ink-500">
            Aucun article pour cette langue.
          </p>
        ) : (
          items.map((it) => (
            <ArticleCard
              key={it.id}
              article={it}
              wagtailEditUrl={`${wagtailAdminBase()}/pages/${it.id}/edit/`}
              onCoverChanged={patchCover}
              onLiveChanged={patchLive}
              onOpenComments={() => setCommentsFor(it)}
            />
          ))
        )}
      </div>

      {/* Pagination */}
      {count > PAGE_SIZE ? (
        <div className="flex items-center justify-center gap-3">
          <button
            type="button"
            disabled={offset === 0}
            onClick={() => setOffset((o) => Math.max(0, o - PAGE_SIZE))}
            className="inline-flex items-center gap-1 rounded-lg border border-line-200 bg-paper px-3 py-1.5 text-sm text-ink-700 disabled:opacity-40 hover:enabled:bg-line-50"
          >
            <ChevronLeft className="size-4" aria-hidden="true" />
            Précédent
          </button>
          <span className="text-sm text-ink-600">
            Page {currentPage} / {totalPages}
          </span>
          <button
            type="button"
            disabled={currentPage >= totalPages}
            onClick={() => setOffset((o) => o + PAGE_SIZE)}
            className="inline-flex items-center gap-1 rounded-lg border border-line-200 bg-paper px-3 py-1.5 text-sm text-ink-700 disabled:opacity-40 hover:enabled:bg-line-50"
          >
            Suivant
            <ChevronRight className="size-4" aria-hidden="true" />
          </button>
        </div>
      ) : null}

      <CommentsModal
        article={commentsFor}
        onClose={() => setCommentsFor(null)}
      />
    </div>
  );
}

function ArticleCard({
  article,
  wagtailEditUrl,
  onCoverChanged,
  onLiveChanged,
  onOpenComments,
}: {
  article: AdminBlogArticle;
  wagtailEditUrl: string;
  onCoverChanged: (id: number, cover: { url: string } | null) => void;
  onLiveChanged: (id: number, live: boolean) => void;
  onOpenComments: () => void;
}) {
  const fileRef = useRef<HTMLInputElement | null>(null);
  const [busy, setBusy] = useState(false);
  const [toggling, setToggling] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [enOpen, setEnOpen] = useState(false);
  const [hasEn, setHasEn] = useState(article.has_en);
  const cover = article.cover_image_data?.url;

  async function onPick(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (fileRef.current) fileRef.current.value = "";
    if (!file) return;
    setErr(null);
    setBusy(true);
    try {
      const res = await adminApi.cmsBlog.setCoverImage(article.id, file);
      const next = res.cover_image_data
        ? { url: bust(res.cover_image_data.url) }
        : null;
      onCoverChanged(article.id, next);
    } catch (e2) {
      setErr((e2 as { detail?: string }).detail ?? "Échec du changement d'image.");
    } finally {
      setBusy(false);
    }
  }

  async function toggleLive() {
    setErr(null);
    setToggling(true);
    try {
      const res = await adminApi.cmsBlog.setLive(article.id, !article.live);
      onLiveChanged(article.id, res.live);
    } catch (e2) {
      setErr((e2 as { detail?: string }).detail ?? "Action impossible.");
    } finally {
      setToggling(false);
    }
  }

  return (
    <article className="flex flex-col overflow-hidden rounded-xl border border-line-200 bg-paper shadow-sm transition-all hover:shadow">
      <div className="group relative">
        {cover ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={cover} alt="" className="aspect-[16/10] w-full object-cover" />
        ) : (
          <div className="aspect-[16/10] bg-cream/60" />
        )}
        {/* Badge statut */}
        <span
          className={
            "absolute left-2 top-2 inline-flex items-center rounded-full px-2 py-0.5 text-[0.65rem] font-semibold ring-1 ring-inset " +
            (article.live
              ? "bg-emerald-50 text-emerald-700 ring-emerald-200"
              : "bg-line-100 text-ink-500 ring-line-200")
          }
        >
          {article.live ? "En ligne" : "Désactivé"}
        </span>
        <button
          type="button"
          onClick={() => fileRef.current?.click()}
          disabled={busy}
          className="absolute bottom-2 right-2 inline-flex items-center gap-1.5 rounded-lg bg-ink-900/80 px-2.5 py-1.5 text-xs font-semibold text-white backdrop-blur transition hover:bg-ink-900 disabled:opacity-70"
        >
          {busy ? (
            <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />
          ) : (
            <ImagePlus className="size-3.5" aria-hidden="true" />
          )}
          {busy ? "Envoi…" : "Changer l'image"}
        </button>
        <input
          ref={fileRef}
          type="file"
          accept="image/*"
          onChange={onPick}
          className="hidden"
        />
      </div>

      <div className="flex flex-1 flex-col space-y-2 p-4">
        <p className="font-mono text-[0.65rem] uppercase tracking-wide text-ink-500">
          {fmtDate(article.date)}
          {" · "}
          {article.author_name || "GATHE"}
        </p>
        <h2 className="font-editorial text-base font-medium leading-tight text-ink-900">
          {article.title}
        </h2>

        {err ? <p className="text-xs text-terra-700">{err}</p> : null}

        <div className="mt-auto flex flex-wrap items-center gap-2 pt-2">
          <button
            type="button"
            onClick={toggleLive}
            disabled={toggling}
            className={
              "inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-semibold ring-1 ring-inset disabled:opacity-60 " +
              (article.live
                ? "bg-terra-50/60 text-terra-700 ring-terra-400/40 hover:bg-terra-50"
                : "bg-emerald-50 text-emerald-700 ring-emerald-200 hover:bg-emerald-100")
            }
          >
            {toggling ? (
              <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />
            ) : (
              <Power className="size-3.5" aria-hidden="true" />
            )}
            {article.live ? "Désactiver" : "Activer"}
          </button>

          <button
            type="button"
            onClick={onOpenComments}
            className="inline-flex items-center gap-1.5 rounded-lg bg-blue-50 px-2.5 py-1.5 text-xs font-semibold text-blue-700 ring-1 ring-inset ring-blue-200 hover:bg-blue-100"
          >
            <MessageSquare className="size-3.5" aria-hidden="true" />
            {article.comment_count} commentaire{article.comment_count > 1 ? "s" : ""}
          </button>

          <button
            type="button"
            onClick={() => setEnOpen(true)}
            className={
              "inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-semibold ring-1 ring-inset " +
              (hasEn
                ? "bg-teal-50 text-teal-700 ring-teal-200 hover:bg-teal-100"
                : "bg-line-100 text-ink-500 ring-line-200 hover:bg-line-200")
            }
          >
            <Globe className="size-3.5" aria-hidden="true" />
            {hasEn ? "EN ✓" : "EN"}
          </button>

          {article.live && article.html_url ? (
            <a
              href={article.html_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-xs font-medium text-ink-600 hover:text-blue-700"
            >
              <Eye className="size-3.5" aria-hidden="true" />
              Voir
            </a>
          ) : null}

          <a
            href={wagtailEditUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="ml-auto rounded-lg bg-ink-900 px-2.5 py-1.5 text-xs font-semibold text-white hover:bg-ink-800"
          >
            Éditer
          </a>
        </div>
      </div>

      {enOpen ? (
        <EnEditorModal
          article={article}
          onClose={() => setEnOpen(false)}
          onSaved={(has) => setHasEn(has)}
        />
      ) : null}
    </article>
  );
}


/** Modale d'édition de la correspondance anglaise (titre / extrait / contenu). */
function EnEditorModal({
  article,
  onClose,
  onSaved,
}: {
  article: AdminBlogArticle;
  onClose: () => void;
  onSaved: (hasEn: boolean) => void;
}) {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [titleEn, setTitleEn] = useState("");
  const [excerptEn, setExcerptEn] = useState("");
  const [bodyEn, setBodyEn] = useState("");
  const [refFr, setRefFr] = useState<{ title: string; excerpt: string }>({
    title: article.title,
    excerpt: "",
  });

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const d = await adminApi.cmsBlog.getI18n(article.id);
        if (!alive) return;
        setTitleEn(d.title_en);
        setExcerptEn(d.excerpt_en);
        setBodyEn(d.body_en);
        setRefFr({ title: d.title, excerpt: d.excerpt });
      } catch (e) {
        if (alive) setErr((e as { detail?: string }).detail ?? "Chargement impossible.");
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => {
      alive = false;
    };
  }, [article.id]);

  async function save() {
    setSaving(true);
    setErr(null);
    try {
      const res = await adminApi.cmsBlog.setI18n(article.id, {
        title_en: titleEn,
        excerpt_en: excerptEn,
        body_en: bodyEn,
      });
      onSaved(Boolean(res.title_en || res.excerpt_en || res.body_en));
      onClose();
    } catch (e) {
      setErr((e as { detail?: string }).detail ?? "Enregistrement impossible.");
    } finally {
      setSaving(false);
    }
  }

  const input =
    "w-full rounded-md border border-line-200 bg-paper px-3 py-2 text-sm text-ink-900 focus:border-teal-600 focus:outline-none focus:ring-1 focus:ring-teal-600";

  return (
    <Modal open onClose={onClose} title="Version anglaise de l'article">
      {loading ? (
        <p className="py-8 text-center text-sm text-ink-500">Chargement…</p>
      ) : (
        <div className="space-y-4">
          {err ? (
            <p className="rounded-md bg-terra-50 px-3 py-2 text-sm text-terra-700">
              {err}
            </p>
          ) : null}
          <p className="text-xs text-ink-500">
            Laisse un champ vide pour retomber sur le français côté vitrine.
          </p>

          <div>
            <label className="mb-1 block text-xs font-medium text-ink-700">
              Titre (EN)
            </label>
            <input
              className={input}
              value={titleEn}
              onChange={(e) => setTitleEn(e.target.value)}
              placeholder={refFr.title}
            />
          </div>

          <div>
            <label className="mb-1 block text-xs font-medium text-ink-700">
              Extrait (EN)
            </label>
            <textarea
              className={input}
              rows={3}
              value={excerptEn}
              onChange={(e) => setExcerptEn(e.target.value)}
              placeholder={refFr.excerpt}
            />
          </div>

          <div>
            <label className="mb-1 block text-xs font-medium text-ink-700">
              Contenu (EN)
            </label>
            <textarea
              className={input}
              rows={10}
              value={bodyEn}
              onChange={(e) => setBodyEn(e.target.value)}
              placeholder="Texte de l'article en anglais…"
            />
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg border border-line-200 px-3 py-1.5 text-sm font-medium text-ink-700 hover:bg-cream"
            >
              Annuler
            </button>
            <button
              type="button"
              onClick={save}
              disabled={saving}
              className="rounded-lg bg-teal-600 px-4 py-1.5 text-sm font-semibold text-white hover:bg-teal-700 disabled:opacity-60"
            >
              {saving ? "Enregistrement…" : "Enregistrer"}
            </button>
          </div>
        </div>
      )}
    </Modal>
  );
}

function CommentsModal({
  article,
  onClose,
}: {
  article: AdminBlogArticle | null;
  onClose: () => void;
}) {
  const [rows, setRows] = useState<ArticleCommentRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!article) return;
    setLoading(true);
    setError(null);
    setRows([]);
    adminApi.cmsBlog
      .comments(article.id, { limit: 50 })
      .then((data) => setRows(data.results))
      .catch(() => setError("Échec du chargement des commentaires."))
      .finally(() => setLoading(false));
  }, [article]);

  return (
    <Modal
      open={article !== null}
      onClose={onClose}
      title={article ? `Commentaires · ${article.title}` : "Commentaires"}
      description="Aperçu des commentaires et réponses (les masqués sont signalés)."
    >
      {loading ? (
        <p className="py-6 text-center text-sm text-ink-500">Chargement…</p>
      ) : error ? (
        <p className="text-sm text-terra-700">{error}</p>
      ) : rows.length === 0 ? (
        <p className="py-6 text-center text-sm text-ink-500">
          Aucun commentaire pour cet article.
        </p>
      ) : (
        <ul className="space-y-3">
          {rows.map((c) => (
            <CommentItem key={c.id} c={c} />
          ))}
        </ul>
      )}
    </Modal>
  );
}

function CommentItem({ c, depth = 0 }: { c: ArticleCommentRow; depth?: number }) {
  return (
    <li className={depth > 0 ? "ml-4 border-l border-line-200 pl-3" : ""}>
      <div className="rounded-lg border border-line-200 bg-cream/40 p-3">
        <div className="flex items-center justify-between gap-2">
          <p className="text-xs font-semibold text-ink-900">
            {c.author_name || "Membre"}
          </p>
          <span className="text-[0.65rem] text-ink-500">
            {new Date(c.created_at).toLocaleDateString("fr-FR", {
              day: "2-digit",
              month: "short",
              year: "2-digit",
            })}
            {c.hidden ? (
              <span className="ml-2 rounded-full bg-terra-50 px-1.5 py-0.5 font-semibold text-terra-700 ring-1 ring-inset ring-terra-400/40">
                masqué
              </span>
            ) : null}
          </span>
        </div>
        <p className="mt-1 whitespace-pre-wrap text-sm text-ink-700">{c.body}</p>
      </div>
      {c.replies?.length ? (
        <ul className="mt-2 space-y-2">
          {c.replies.map((r) => (
            <CommentItem key={r.id} c={r} depth={depth + 1} />
          ))}
        </ul>
      ) : null}
    </li>
  );
}
