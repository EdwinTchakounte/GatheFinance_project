import type { Metadata } from "next";
import Image from "next/image";
import { notFound } from "next/navigation";
import { getTranslations, setRequestLocale } from "next-intl/server";
import { ArrowLeft } from "lucide-react";

import { Section, SectionHeader } from "@gathe/ui";
import { Link } from "@/i18n/navigation";
import { CtaBand } from "@/components/cta-band";
import { StreamField } from "@/components/streamfield";
import { ArticleCard } from "@/components/article-card";
import { JsonLd, articleJsonLd, breadcrumbJsonLd } from "@/components/json-ld";
import { Reveal } from "@/components/reveal";
import { formatDate } from "@/lib/format";
import { blogFallbackImage } from "@/lib/site-config";
import { getBlogPost, getBlogPosts } from "@/lib/wagtail";

const SITE_URL = (process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000").replace(/\/$/, "");

type Params = { params: Promise<{ locale: string; slug: string }> };

export const dynamicParams = true;

export async function generateStaticParams({ params }: { params: { locale: string } }) {
  const posts = await getBlogPosts(params.locale, 50);
  return posts.map((p) => ({ slug: p.slug }));
}

export async function generateMetadata({ params }: Params): Promise<Metadata> {
  const { locale, slug } = await params;
  const post = await getBlogPost(slug, locale);
  if (!post) return {};
  return {
    title: post.seoTitle ?? post.title,
    description: post.seoDescription ?? post.excerpt,
    openGraph: { type: "article", title: post.title, description: post.excerpt },
  };
}

export default async function BlogArticlePage({ params }: Params) {
  const { locale, slug } = await params;
  setRequestLocale(locale);
  const post = await getBlogPost(slug, locale);
  if (!post) notFound();

  const t = await getTranslations({ locale, namespace: "blog" });
  const tn = await getTranslations({ locale, namespace: "nav" });
  const date = formatDate(post.date, locale);

  const all = await getBlogPosts(locale, 12);
  const related = all.filter((p) => p.slug !== post.slug).slice(0, 3);
  const path = locale === "fr" ? `/blog/${post.slug}` : `/${locale}/blog/${post.slug}`;

  return (
    <>
      <JsonLd
        data={[
          articleJsonLd({
            siteUrl: SITE_URL,
            url: `${SITE_URL}${path}`,
            title: post.title,
            description: post.excerpt,
            datePublished: post.date,
            author: post.authorName ?? "Gathe Finance",
            image: post.coverImage?.url ?? null,
          }),
          breadcrumbJsonLd(SITE_URL, [
            { name: tn("home"), path: locale === "fr" ? "/" : `/${locale}` },
            { name: tn("blog"), path: locale === "fr" ? "/blog" : `/${locale}/blog` },
            { name: post.title, path },
          ]),
        ]}
      />
      <Section tone="muted" spacing="md" className="border-b border-line-200">
        <nav aria-label="Fil d'Ariane" className="text-sm text-ink-500">
          <Link href="/" className="hover:text-blue-700">
            {tn("home")}
          </Link>
          <span aria-hidden="true" className="mx-2">/</span>
          <Link href="/blog" className="hover:text-blue-700">
            {tn("blog")}
          </Link>
          <span aria-hidden="true" className="mx-2">/</span>
          <span className="text-ink-700">{post.title}</span>
        </nav>
        <div className="mt-5 max-w-3xl">
          {post.categories[0] ? (
            <span className="inline-block rounded-full bg-green-100 px-2.5 py-0.5 text-xs font-semibold uppercase tracking-wide text-green-800">
              {post.categories[0].name}
            </span>
          ) : null}
          <h1 className="mt-3 text-balance text-3xl font-bold leading-tight text-ink-900 sm:text-4xl">{post.title}</h1>
          <p className="mt-3 text-sm text-ink-500">{t("byline", { author: post.authorName ?? "Gathe", date })}</p>
        </div>
      </Section>

      <Section spacing="lg">
        {(() => {
          const url = post.coverImage?.url ?? blogFallbackImage(post.slug);
          return (
            <div className="mx-auto mb-12 max-w-3xl">
              <div className="relative aspect-[16/8] overflow-hidden rounded-[var(--radius-2xl)] bg-blue-100 shadow-[var(--shadow-md)]">
                {url ? (
                  <Image src={url} alt={post.coverImage?.alt ?? post.title} fill priority sizes="(min-width: 768px) 50rem, 100vw" className="object-cover" />
                ) : (
                  <div className="absolute inset-0 bg-blue-50" />
                )}
              </div>
            </div>
          );
        })()}
        <article className="mx-auto max-w-2xl">
          <StreamField blocks={post.body} />
          <div className="mt-12 border-t border-line-200 pt-6">
            <Link href="/blog" className="inline-flex items-center gap-1.5 text-sm font-medium text-blue-700 hover:text-blue-800">
              <ArrowLeft aria-hidden="true" className="size-4" /> {t("backToBlog")}
            </Link>
          </div>
        </article>
      </Section>

      {related.length > 0 ? (
        <Section tone="muted" spacing="lg">
          <SectionHeader title={t("relatedTitle")} />
          <div className="mt-8 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {related.map((p, i) => (
              <Reveal key={p.id} delay={i * 70}>
                <ArticleCard post={p} locale={locale} />
              </Reveal>
            ))}
          </div>
        </Section>
      ) : null}

      <CtaBand />
    </>
  );
}
