"use client";

import { useEffect, useState } from "react";

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

  useEffect(() => {
    setLoading(true);
    setError(null);
    const url =
      `${wagtailBase()}/pages/?type=cms.BlogPostPage` +
      `&fields=date,excerpt,cover_image_data,author_name` +
      `&order=-date&limit=50&locale=${locale}`;
    fetch(url, { credentials: "include" })
      .then((r) => (r.ok ? r.json() : Promise.reject(r.statusText)))
      .then((data) => setItems((data?.items as WagtailArticle[]) ?? []))
      .catch((e) => setError(typeof e === "string" ? e : "Echec du chargement"))
      .finally(() => setLoading(false));
  }, [locale]);

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
          items.map((it) => {
            const cover = it.cover_image_data?.url;
            const wagtailEditUrl = `${wagtailAdminBase()}/pages/${it.id}/edit/`;
            return (
              <article key={it.id} className="overflow-hidden rounded-xl border border-line-200 bg-paper shadow-sm transition-all hover:shadow">
                {cover ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={cover} alt="" className="aspect-[16/10] w-full object-cover" />
                ) : (
                  <div className="aspect-[16/10] bg-cream/60" />
                )}
                <div className="space-y-2 p-4">
                  <p className="font-mono text-[0.65rem] uppercase tracking-wide text-ink-500">
                    {it.date ? new Date(it.date).toLocaleDateString("fr-CM") : "Brouillon"}
                    {" · "}{it.author_name || "Gathé"}
                  </p>
                  <h2 className="font-editorial text-base font-medium leading-tight text-ink-900">
                    {it.title}
                  </h2>
                  {it.excerpt ? (
                    <p className="line-clamp-2 text-xs text-ink-600">{it.excerpt}</p>
                  ) : null}
                  <div className="flex items-center justify-between pt-2">
                    <a
                      href={it.meta.html_url}
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
          })
        )}
      </div>
    </div>
  );
}
