"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";

import { Container } from "@gathe/ui";

import { CommentsSection } from "@/components/social/comments-section";
import { LikeButton } from "@/components/social/like-button";
import { StreamField } from "@/components/social/streamfield";
import { getArticleBySlug, type Article } from "@/lib/wagtail";

function fmt(d: string): string {
  if (!d) return "";
  try {
    return new Date(d).toLocaleDateString("fr-FR", {
      day: "2-digit",
      month: "long",
      year: "numeric",
    });
  } catch {
    return d;
  }
}

/** Détail d'un article + interactions sociales (like + commentaires). */
export default function ArticleDetailPage() {
  const router = useRouter();
  const params = useParams<{ locale: string; slug: string }>();
  const locale = params?.locale ?? "fr";
  const slug = params?.slug;

  const [article, setArticle] = useState<Article | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!slug) return;
    let alive = true;
    getArticleBySlug(slug, locale)
      .then((a) => {
        if (alive) setArticle(a);
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [slug, locale]);

  return (
    <main className="min-h-svh bg-cream py-12 lg:py-16">
      <Container className="max-w-3xl">
        <button
          type="button"
          onClick={() => router.push("/actualites")}
          className="text-sm text-ink-600 transition-colors hover:text-blue-700"
        >
          ← Toutes les actualités
        </button>

        {loading ? (
          <p className="mt-10 text-center text-sm text-ink-600">Chargement…</p>
        ) : !article ? (
          <p className="mt-10 mx-auto max-w-md rounded-md border border-line-200 bg-paper p-6 text-center text-sm text-ink-600">
            Article introuvable.
          </p>
        ) : (
          <div className="mt-6 space-y-6">
            <article className="overflow-hidden rounded-md border border-line-200 bg-paper">
              {article.coverUrl ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={article.coverUrl}
                  alt=""
                  className="h-56 w-full object-cover"
                />
              ) : null}
              <div className="p-6">
                <p className="text-xs uppercase tracking-wide text-ink-500">
                  {fmt(article.date)}
                  {article.authorName ? ` · ${article.authorName}` : ""}
                </p>
                <h1 className="mt-2 font-editorial text-2xl font-medium leading-tight text-ink-900 sm:text-3xl">
                  {article.title}
                </h1>

                <div className="mt-5">
                  <StreamField blocks={article.body} />
                </div>

                <div className="mt-6 border-t border-line-200 pt-4">
                  <LikeButton kind="articles" id={article.id} />
                </div>
              </div>
            </article>

            <CommentsSection kind="articles" id={article.id} />
          </div>
        )}
      </Container>
    </main>
  );
}
