"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";

import { Container } from "@gathe/ui";

import { getArticles, type ArticleListItem } from "@/lib/wagtail";

function fmt(d: string): string {
  if (!d) return "";
  try {
    return new Date(d).toLocaleDateString("fr-FR", {
      day: "2-digit",
      month: "short",
      year: "numeric",
    });
  } catch {
    return d;
  }
}

/** Fil d'actualités membre — parité avec le feed articles du mobile. */
export default function ActualitesPage() {
  const router = useRouter();
  const params = useParams<{ locale: string }>();
  const locale = params?.locale ?? "fr";

  const [items, setItems] = useState<ArticleListItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    getArticles(locale, 24)
      .then((a) => {
        if (alive) setItems(a);
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [locale]);

  return (
    <main className="min-h-svh bg-cream py-12 lg:py-16">
      <Container className="max-w-4xl">
        <button
          type="button"
          onClick={() => router.push("/")}
          className="text-sm text-ink-600 transition-colors hover:text-blue-700"
        >
          ← Retour à l&apos;accueil
        </button>

        <header className="mt-4">
          <span className="label-num">Coopérative</span>
          <h1 className="mt-3 font-editorial text-3xl font-medium leading-tight text-ink-900">
            Actualités
          </h1>
          <p className="mt-1 text-sm text-ink-600">
            Les articles et conseils de GATHE Finance. Réagissez et commentez.
          </p>
        </header>

        {loading ? (
          <p className="mt-10 text-center text-sm text-ink-600">Chargement…</p>
        ) : items.length === 0 ? (
          <p className="mt-10 rounded-md border border-dashed border-line-200 bg-paper/70 p-10 text-center text-sm text-ink-600">
            Aucun article pour le moment.
          </p>
        ) : (
          <section className="mt-8 grid gap-6 md:grid-cols-2">
            {items.map((a) => (
              <button
                key={a.id}
                type="button"
                onClick={() => router.push(`/actualites/${a.slug}`)}
                className="flex flex-col overflow-hidden rounded-md border border-line-200 bg-paper text-left transition-all hover:shadow"
              >
                {a.coverUrl ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={a.coverUrl}
                    alt=""
                    className="h-40 w-full object-cover"
                  />
                ) : (
                  <div className="h-40 w-full bg-cream/60" />
                )}
                <div className="flex flex-1 flex-col p-5">
                  <p className="text-xs uppercase tracking-wide text-ink-500">
                    {fmt(a.date)}
                    {a.authorName ? ` · ${a.authorName}` : ""}
                  </p>
                  <h2 className="mt-1 font-editorial text-lg font-medium leading-tight text-ink-900">
                    {a.title}
                  </h2>
                  {a.excerpt ? (
                    <p className="mt-2 line-clamp-3 text-sm text-ink-600">
                      {a.excerpt}
                    </p>
                  ) : null}
                  <span className="mt-3 text-sm font-medium text-blue-700">
                    Lire & commenter →
                  </span>
                </div>
              </button>
            ))}
          </section>
        )}
      </Container>
    </main>
  );
}
