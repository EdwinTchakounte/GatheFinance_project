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
            author: post.authorName ?? "GATHE Finance",
            image: post.coverImage?.url ?? null,
          }),
          breadcrumbJsonLd(SITE_URL, [
            { name: tn("home"), path: locale === "fr" ? "/" : `/${locale}` },
            { name: tn("blog"), path: locale === "fr" ? "/blog" : `/${locale}/blog` },
            { name: post.title, path },
          ]),
        ]}
      />
      {/* HERO . hauteur reduite, marges resserrees, titre tres percutant */}
      <Section tone="default" spacing="md" className="!pt-8 !pb-4">
        <nav aria-label="Fil d'Ariane" className="text-xs text-ink-500">
          <Link href="/" className="hover:text-blue-700 transition-colors">
            {tn("home")}
          </Link>
          <span aria-hidden="true" className="mx-2 text-line-300">/</span>
          <Link href="/blog" className="hover:text-blue-700 transition-colors">
            {tn("blog")}
          </Link>
          <span aria-hidden="true" className="mx-2 text-line-300">/</span>
          <span className="text-ink-700 truncate">{post.title}</span>
        </nav>
        <div className="mt-6 max-w-[55rem]">
          {post.categories[0] ? (
            <span className="inline-flex items-center gap-1.5 rounded-full border border-green-200 bg-green-50 px-3 py-1 text-[0.7rem] font-bold uppercase tracking-[0.12em] text-green-800">
              <span className="size-1.5 rounded-full bg-green-600" />
              {post.categories[0].name}
            </span>
          ) : null}
          <h1 className="mt-5 text-balance font-editorial text-4xl font-semibold leading-[1.1] text-ink-900 sm:text-5xl md:text-[3.5rem]">
            {post.title}
          </h1>
          {post.excerpt ? (
            <p className="mt-4 max-w-2xl text-lg leading-relaxed text-ink-600">{post.excerpt}</p>
          ) : null}
          <div className="mt-6 flex items-center gap-3 text-sm">
            <div className="size-9 shrink-0 rounded-full bg-gradient-to-br from-blue-200 to-green-200" aria-hidden="true" />
            <div>
              <p className="font-semibold text-ink-900">{post.authorName ?? "GATHE Finance"}</p>
              <p className="text-xs text-ink-500">{date}</p>
            </div>
          </div>
        </div>
      </Section>

      {/* HERO IMAGE . pleine largeur, ratio paysage, ombre prononcee */}
      {(() => {
        const url = post.coverImage?.url ?? blogFallbackImage(post.slug);
        return (
          <div className="mx-auto -mt-2 mb-8 max-w-[80rem] px-4 sm:mb-10 sm:px-8">
            <div className="relative aspect-[16/9] overflow-hidden rounded-[var(--radius-2xl)] bg-blue-50 shadow-[0_20px_60px_-15px_rgba(15,23,42,0.25)]">
              {url ? (
                <Image
                  src={url}
                  alt={post.coverImage?.alt ?? post.title}
                  fill
                  priority
                  sizes="(min-width: 1024px) 1024px, 100vw"
                  className="object-cover"
                />
              ) : (
                <div className="absolute inset-0 bg-gradient-to-br from-blue-100 via-blue-50 to-green-50" />
              )}
            </div>
          </div>
        );
      })()}

      {/* ARTICLE . texte justifie, marges generistes mais resserrees.
          Tailwind arbitrary selectors pour cibler tous les <p> rendus
          par StreamField sans repasser sur le markup. */}
      <Section spacing="md" className="!pt-2 !pb-16">
        <article
          className={[
            "article-body mx-auto px-4 sm:px-6",
            "max-w-[58rem] text-ink-800",
            "[&_p]:text-justify [&_p]:hyphens-auto [&_p]:leading-[1.75]",
            "[&_p]:my-3 [&_p]:text-[1.0625rem]",
            "[&_h2]:mt-10 [&_h2]:mb-3 [&_h3]:mt-8 [&_h3]:mb-2",
            "[&_blockquote]:my-5 [&_blockquote]:border-l-4 [&_blockquote]:border-emerald [&_blockquote]:pl-4",
            "[&_img]:rounded-lg [&_img]:my-5 [&_img]:shadow-sm",
            "[&_ul]:my-4 [&_li]:my-1",
          ].join(" ")}
        >
          <StreamField blocks={post.body} />
          <div className="mt-14 border-t border-line-200 pt-6">
            <Link href="/blog" className="inline-flex items-center gap-1.5 text-sm font-semibold text-blue-700 hover:text-blue-800 transition-colors">
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
