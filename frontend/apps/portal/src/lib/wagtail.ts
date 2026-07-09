// Client Wagtail (lecture) pour le fil d'actualités membre. En prod on tape
// directement l'API publique v2 sur le domaine api.*, en dev on passe par le
// rewrite `/api/v2` (next.config).

function wagtailBase(): string {
  if (typeof window === "undefined") return "/api/v2";
  const host = window.location.hostname;
  if (host.endsWith(".gathe-finance.horus-lab.com")) {
    return "https://api.gathe-finance.horus-lab.com/api/v2";
  }
  return "/api/v2";
}

function cmsUrl(url: string | null | undefined): string | null {
  if (!url) return null;
  return /^https?:\/\//.test(url) ? url : `${wagtailBase().replace(/\/api\/v2$/, "")}${url}`;
}

export type StreamBlock =
  | { type: "heading"; id: string; value: { eyebrow?: string; title: string; text?: string; alignment?: "left" | "center" } }
  | { type: "rich_text"; id: string; value: { body: string } }
  | { type: "callout"; id: string; value: { style?: string; title?: string; body: string } }
  | { type: "quote"; id: string; value: { quote: string; author?: string; role?: string } }
  | { type: "image"; id: string; value: { image: { url?: string; alt?: string } | number; caption?: string; alt?: string } }
  | { type: string; id: string; value: unknown };

export type ArticleListItem = {
  id: number;
  title: string;
  slug: string;
  date: string;
  excerpt: string;
  coverUrl: string | null;
  authorName: string | null;
};

export type Article = ArticleListItem & { body: StreamBlock[] };

const FIELDS = "date,excerpt,cover_image_data,author_name";

function normalise(it: Record<string, unknown>): ArticleListItem {
  const meta = (it.meta as Record<string, unknown> | undefined) ?? {};
  const cover = (it.cover_image_data as { url?: string } | null) ?? null;
  return {
    id: Number(it.id),
    title: String(it.title ?? ""),
    slug: String(meta.slug ?? ""),
    date: String(it.date ?? meta.first_published_at ?? ""),
    excerpt: String(it.excerpt ?? ""),
    coverUrl: cover?.url ? cmsUrl(cover.url) : null,
    authorName: (it.author_name as string) || null,
  };
}

async function get<T>(path: string): Promise<T | null> {
  try {
    const res = await fetch(`${wagtailBase()}${path}`, {
      credentials: "include",
      cache: "no-store",
    });
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  }
}

export async function getArticles(
  locale: string,
  limit = 20,
): Promise<ArticleListItem[]> {
  const loc = locale === "en" ? "en" : "fr";
  const data = await get<{ items: Array<Record<string, unknown>> }>(
    `/pages/?type=cms.BlogPostPage&fields=${FIELDS}&order=-date&limit=${limit}&locale=${loc}`,
  );
  return (data?.items ?? []).map(normalise);
}

export async function getArticleBySlug(
  slug: string,
  locale: string,
): Promise<Article | null> {
  const loc = locale === "en" ? "en" : "fr";
  const data = await get<{ items: Array<Record<string, unknown>> }>(
    `/pages/?type=cms.BlogPostPage&slug=${encodeURIComponent(slug)}&fields=${FIELDS},body&locale=${loc}`,
  );
  const it = data?.items?.[0];
  if (!it) return null;
  return {
    ...normalise(it),
    body: Array.isArray(it.body) ? (it.body as StreamBlock[]) : [],
  };
}
