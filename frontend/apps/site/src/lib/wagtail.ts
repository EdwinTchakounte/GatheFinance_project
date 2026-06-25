/**
 * Thin client for the headless CMS (Wagtail) API.
 *
 * Used only at build / ISR-revalidation time (never per visitor request).
 * Every call degrades gracefully: if the backend is unreachable it returns
 * `null` / `[]` so the front-end can fall back to its in-code content.
 */
const API_BASE = (process.env.CMS_API_URL ?? "http://localhost:8000").replace(/\/$/, "");
const REVALIDATE_SECONDS = Number(process.env.CMS_REVALIDATE_SECONDS ?? 3600);

async function cmsFetch<T>(path: string): Promise<T | null> {
  try {
    const res = await fetch(`${API_BASE}${path}`, {
      next: { revalidate: REVALIDATE_SECONDS, tags: ["cms"] },
      headers: { Accept: "application/json" },
    });
    if (!res.ok) {
      // Surface upstream errors at build/ISR time so a broken CMS network
      // (wrong ALLOWED_HOSTS, container not joining the right docker network,
      // etc.) shows up in the next-server logs instead of degrading silently
      // to an empty fallback rendering.
      console.warn(
        `[cms] ${API_BASE}${path} returned ${res.status} ${res.statusText}`,
      );
      return null;
    }
    return (await res.json()) as T;
  } catch (err) {
    console.warn(
      `[cms] ${API_BASE}${path} fetch failed:`,
      err instanceof Error ? err.message : err,
    );
    return null;
  }
}

const wagtailLocale = (locale: string) => (locale === "fr" ? "fr" : "en");

/** Make a possibly-relative media URL absolute against the CMS base. */
export function cmsUrl(url: string | null | undefined): string | null {
  if (!url) return null;
  return /^https?:\/\//.test(url) ? url : `${API_BASE}${url}`;
}

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type CmsImage = { url: string; width: number; height: number; alt: string } | null;

/** A StreamField block as returned by the Wagtail API: { type, value, id }. */
export type StreamBlock =
  | { type: "heading"; id: string; value: { eyebrow?: string; title: string; text?: string; alignment?: "left" | "center" } }
  | { type: "rich_text"; id: string; value: { body: string } }
  | { type: "callout"; id: string; value: { style?: "info" | "success" | "neutral"; title?: string; body: string } }
  | { type: "quote"; id: string; value: { quote: string; author?: string; role?: string } }
  | { type: "image"; id: string; value: { image: number | CmsImage; caption?: string; alt?: string } }
  | { type: "cta_band"; id: string; value: Record<string, unknown> }
  | { type: string; id: string; value: unknown };

export type SiteSettings = {
  legalName: string;
  baseline: string;
  address: string;
  phone: string;
  landline: string;
  email: string;
  openingHours: string;
  geo: { lat: number; lng: number } | null;
  social: { facebook: string | null; linkedin: string | null; whatsapp: string | null };
  cta: { title: string; text: string; buttonLabel: string };
  copyright: string;
  seo: {
    defaultTitle: string;
    defaultDescription: string;
    ogImage: CmsImage;
    googleSiteVerification: string | null;
    bingSiteVerification: string | null;
    plausibleDomain: string | null;
    ga4MeasurementId: string | null;
  };
};

export type BlogListItem = {
  id: number;
  title: string;
  slug: string;
  date: string;
  excerpt: string;
  coverImage: CmsImage;
  authorName: string | null;
  categories: { name: string; slug: string }[];
};

export type BlogPost = BlogListItem & {
  body: StreamBlock[];
  seoTitle: string | null;
  seoDescription: string | null;
};

export type LegalPage = {
  id: number;
  title: string;
  slug: string;
  body: StreamBlock[];
  lastPublishedAt: string | null;
};

// ---------------------------------------------------------------------------
// Endpoints
// ---------------------------------------------------------------------------

export function getSiteSettings(): Promise<SiteSettings | null> {
  return cmsFetch<SiteSettings>("/api/site/settings/");
}

function normaliseItem(it: Record<string, unknown>): BlogListItem {
  const meta = (it.meta as Record<string, unknown> | undefined) ?? {};
  const cover = (it.cover_image_data as CmsImage) ?? null;
  return {
    id: Number(it.id),
    title: String(it.title ?? ""),
    slug: String(meta.slug ?? it.slug ?? ""),
    date: String(it.date ?? meta.first_published_at ?? ""),
    excerpt: String(it.excerpt ?? ""),
    coverImage: cover && cover.url ? { ...cover, url: cmsUrl(cover.url)! } : null,
    authorName: (it.author_name as string) || null,
    categories: Array.isArray(it.category_list)
      ? (it.category_list as Array<{ name?: string; slug?: string }>).map((c) => ({
          name: String(c.name ?? ""),
          slug: String(c.slug ?? ""),
        }))
      : [],
  };
}

const POST_FIELDS = "date,excerpt,cover_image_data,author_name,category_list";

/** Published blog posts for a locale. Falls back to FR if the locale has none. */
export async function getBlogPosts(locale: string, limit = 12): Promise<BlogListItem[]> {
  const loc = wagtailLocale(locale);
  const fetchFor = async (l: string) =>
    cmsFetch<{ items: Array<Record<string, unknown>> }>(
      `/api/v2/pages/?type=cms.BlogPostPage&fields=${POST_FIELDS}&order=-date&limit=${limit}&locale=${l}`,
    );
  let data = await fetchFor(loc);
  if ((!data?.items || data.items.length === 0) && loc !== "fr") data = await fetchFor("fr");
  if (!data?.items) return [];
  return data.items.map(normaliseItem);
}

/** A single blog post by slug (with full body). Falls back to FR if missing. */
export async function getBlogPost(slug: string, locale: string): Promise<BlogPost | null> {
  const loc = wagtailLocale(locale);
  const fetchFor = async (l: string) =>
    cmsFetch<{ items: Array<Record<string, unknown>> }>(
      `/api/v2/pages/?type=cms.BlogPostPage&slug=${encodeURIComponent(slug)}&fields=${POST_FIELDS},body,seo_title,search_description&locale=${l}`,
    );
  let data = await fetchFor(loc);
  if ((!data?.items || data.items.length === 0) && loc !== "fr") data = await fetchFor("fr");
  const it = data?.items?.[0];
  if (!it) return null;
  return {
    ...normaliseItem(it),
    body: Array.isArray(it.body) ? (it.body as StreamBlock[]) : [],
    seoTitle: (it.seo_title as string) || null,
    seoDescription: (it.search_description as string) || null,
  };
}

export async function getLegalPage(slug: string, locale: string): Promise<LegalPage | null> {
  const loc = wagtailLocale(locale);
  const data = await cmsFetch<{ items: Array<Record<string, unknown>> }>(
    `/api/v2/pages/?type=cms.LegalPage&slug=${encodeURIComponent(slug)}&fields=body,last_published_at&locale=${loc}`,
  );
  const it = data?.items?.[0];
  if (!it) return null;
  const meta = (it.meta as Record<string, unknown> | undefined) ?? {};
  return {
    id: Number(it.id),
    title: String(it.title ?? ""),
    slug: String(meta.slug ?? slug),
    body: Array.isArray(it.body) ? (it.body as StreamBlock[]) : [],
    lastPublishedAt: (it.last_published_at as string) || null,
  };
}

export { API_BASE as CMS_API_BASE, REVALIDATE_SECONDS };
