import type { MetadataRoute } from "next";
import { routing } from "@/i18n/routing";
import { getBlogPosts } from "@/lib/wagtail";

const BASE = (process.env.NEXT_PUBLIC_SITE_URL ?? "https://www.gathe-finance.com").replace(/\/$/, "");

const STATIC_PATHS = [
  "",
  "/a-propos",
  "/services-financiers",
  "/blog",
  "/contact",
  "/devenir-membre",
  "/mentions-legales",
  "/politique-confidentialite",
];

function urlFor(locale: string, path: string): string {
  return locale === routing.defaultLocale ? `${BASE}${path || "/"}` : `${BASE}/${locale}${path}`;
}

function alternates(path: string) {
  return { languages: Object.fromEntries(routing.locales.map((l) => [l, urlFor(l, path)])) };
}

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const entries: MetadataRoute.Sitemap = STATIC_PATHS.map((path) => ({
    url: urlFor(routing.defaultLocale, path),
    changeFrequency: path === "/blog" ? "weekly" : "monthly",
    priority: path === "" ? 1 : 0.7,
    alternates: alternates(path),
  }));

  const posts = await getBlogPosts(routing.defaultLocale, 100);
  for (const post of posts) {
    const path = `/blog/${post.slug}`;
    entries.push({
      url: urlFor(routing.defaultLocale, path),
      lastModified: post.date ? new Date(post.date) : undefined,
      changeFrequency: "yearly",
      priority: 0.6,
      alternates: alternates(path),
    });
  }
  return entries;
}
