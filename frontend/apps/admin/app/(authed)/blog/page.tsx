"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ImagePlus, Loader2 } from "lucide-react";

import { adminApi } from "@/lib/api";

type WagtailArticle = {
  id: number;
  title: string;
  meta: {
    locale: string;
    slug: string;
    first_published_at: string | null;
    html_url: string;
  };
  date?: string;
  excerpt?: string;
  cover_image_data?: { url: string } | null;
  author_name?: string;
};

// L'admin Next.js parle au backend via /api/v1 (settings.ts adminApi). Pour
// l'API Wagtail v2 publique (lecture), on tape directement sur
// /api/v2/pages/... sans passer par /api/v1.
function wagtailBase(): string {
  if (typeof window === "undefined") return "/api/v2";
  const host = window.location.hostname;
  if (host.endsWith(".gathe-finance.horus-lab.com")) {
    return "https://api.gathe-finance.horus-lab.com/api/v2";
  }
  return "/api/v2";
}

// Le panneau d'edition vit dans le Wagtail admin (Django).
function wagtailAdminBase(): string {
  if (typeof window === "undefined") return "/admin";
  const host = window.location.hostname;
  if (host.endsWith(".gathe-finance.horus-lab.com")) {
    return "https://api.gathe-finance.horus-lab.com/admin";
  }
  return "/admin";
}


export default function BlogAdminPage() {
  const [locale, setLocale] = useState<"fr" | "en">("fr");
  const [items, setItems] = useState<WagtailArticle[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(() => {
    setLoading(true);
    setError(null);
    // Cache-buster pour forcer une lecture fraîche de l'API Wagtail après un
    // changement d'image (évite un cache HTTP intermédiaire).
    const url =
      `${wagtailBase()}/pages/?type=cms.BlogPostPage` +
      `&fields=date,excerpt,cover_image_data,author_name` +
      `&order=-date&limit=50&locale=${locale}&_=${Date.now()}`;
    fetch(url, { credentials: "include", cache: "no-store" })
      .then((r) => (r.ok ? r.json() : Promise.reject(r.statusText)))
      .then((data) => setItems((data?.items as WagtailArticle[]) ?? []))
      .catch((e) => setError(typeof e === "string" ? e : "Echec du chargement"))
      .finally(() => setLoading(false));
  }, [locale]);

  useEffect(() => {
    reload();
  }, [reload]);

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
          Liste des <code>BlogPostPage</code> publiés sur la vitrine. L'édition,
          la publication et la traduction se font dans Wagtail.
        </p>
      </header>

      <div className="flex flex-wrap items-center gap-3">
        {/* Sélecteur locale */}
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
          {items.length} article{items.length > 1 ? "s" : ""} publié{items.length > 1 ? "s" : ""}
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
          {error}. Si tu n'es pas connecté à Wagtail, ouvre d'abord
          {" "}
          <a href={wagtailAdminBase()} target="_blank" rel="noopener noreferrer" className="underline">
            le panneau Wagtail
          </a>.
        </p>
      ) : null}

      {/* Grille articles */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {loading ? (
          Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="h-64 animate-pulse rounded-xl bg-line-100" />
          ))
        ) : items.length === 0 ? (
          <p className="col-span-full rounded-xl border border-line-200 bg-paper p-8 text-center text-sm text-ink-500">
            Aucun article publié pour cette langue.
          </p>
        ) : (
          items.map((it) => (
            <ArticleCard
              key={it.id}
              article={it}
              wagtailEditUrl={`${wagtailAdminBase()}/pages/${it.id}/edit/`}
              onChanged={reload}
            />
          ))
        )}
      </div>
    </div>
  );
}


function ArticleCard({
  article,
  wagtailEditUrl,
  onChanged,
}: {
  article: WagtailArticle;
  wagtailEditUrl: string;
  onChanged: () => void;
}) {
  const fileRef = useRef<HTMLInputElement | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const cover = article.cover_image_data?.url;

  async function onPick(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    // Réinitialise l'input pour permettre de re-choisir le même fichier.
    if (fileRef.current) fileRef.current.value = "";
    if (!file) return;
    setErr(null);
    setBusy(true);
    try {
      await adminApi.cmsBlog.setCoverImage(article.id, file);
      onChanged(); // refetch la liste → nouvelle image visible immédiatement.
    } catch (e2) {
      const msg = (e2 as { detail?: string }).detail;
      setErr(msg ?? "Échec du changement d'image.");
      setBusy(false);
    }
  }

  return (
    <article className="overflow-hidden rounded-xl border border-line-200 bg-paper shadow-sm transition-all hover:shadow">
      <div className="group relative">
        {cover ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={cover} alt="" className="aspect-[16/10] w-full object-cover" />
        ) : (
          <div className="aspect-[16/10] bg-cream/60" />
        )}
        {/* Overlay bouton « Changer l'image » */}
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
      <div className="space-y-2 p-4">
        <p className="font-mono text-[0.65rem] uppercase tracking-wide text-ink-500">
          {article.date ? new Date(article.date).toLocaleDateString("fr-CM") : "Brouillon"}
          {" · "}
          {article.author_name || "Gathé"}
        </p>
        <h2 className="font-editorial text-base font-medium leading-tight text-ink-900">
          {article.title}
        </h2>
        {article.excerpt ? (
          <p className="line-clamp-2 text-xs text-ink-600">{article.excerpt}</p>
        ) : null}
        {err ? <p className="text-xs text-terra-700">{err}</p> : null}
        <div className="flex items-center justify-between pt-2">
          <a
            href={article.meta.html_url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs font-medium text-blue-700 hover:underline"
          >
            Voir en ligne →
          </a>
          <a
            href={wagtailEditUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="rounded-lg bg-ink-900 px-2.5 py-1.5 text-xs font-semibold text-white hover:bg-ink-800"
          >
            Éditer dans Wagtail
          </a>
        </div>
      </div>
    </article>
  );
}
