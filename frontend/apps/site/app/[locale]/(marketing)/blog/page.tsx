import type { Metadata } from "next";
import Image from "next/image";
import { getTranslations, setRequestLocale } from "next-intl/server";
import { ArrowRight } from "lucide-react";

import { Container } from "@gathe/ui";
import { Link } from "@/i18n/navigation";
import { PageHeader } from "@/components/page-shell";
import { CtaBand } from "@/components/cta-band";
import { ArticleCard } from "@/components/article-card";
import { InstitutionalDecor } from "@/components/institutional-decor";
import { Reveal } from "@/components/reveal";
import { formatDate } from "@/lib/format";
import { blogFallbackImage, images } from "@/lib/site-config";
import { getBlogPosts } from "@/lib/wagtail";

type Params = { params: Promise<{ locale: string }> };

export async function generateMetadata({ params }: Params): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "blog" });
  return { title: t("title"), description: t("subtitle") };
}

export default async function BlogIndexPage({ params }: Params) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations({ locale, namespace: "blog" });
  const tn = await getTranslations({ locale, namespace: "nav" });
  const posts = await getBlogPosts(locale, 24);
  const [featured, ...rest] = posts;

  return (
    <>
      <PageHeader
        eyebrow={t("eyebrow")}
        title={t("title")}
        lead={t("subtitle")}
        homeLabel={tn("home")}
        image={images.trainingWorkshop}
      />

      {/* ===== Featured article — large editorial spread ===== */}
      {featured ? (
        <section className="relative isolate overflow-hidden bg-paper py-16 lg:py-20">
          <div aria-hidden="true" className="absolute inset-x-0 top-0 h-px bg-line-200" />
          <InstitutionalDecor variant="nodes" />

          <Container className="relative">
            <Reveal>
              <span className="label-num mx-auto block w-fit">
                01 · {"À la une"}
              </span>
            </Reveal>

            <Reveal delay={120}>
              <Link
                href={`/blog/${featured.slug}`}
                className="group mt-10 grid gap-8 lg:grid-cols-[1.1fr_1fr] lg:gap-14"
              >
                <div className="relative aspect-[16/11] overflow-hidden rounded-md ring-1 ring-line-200 lg:aspect-[4/3.2]">
                  {(() => {
                    const url = featured.coverImage?.url ?? blogFallbackImage(featured.slug);
                    return url ? (
                      <Image
                        src={url}
                        alt={featured.coverImage?.alt ?? featured.title}
                        fill
                        sizes="(min-width: 1024px) 55vw, 100vw"
                        priority
                        className="object-cover transition-transform duration-[900ms] ease-out group-hover:scale-[1.03]"
                      />
                    ) : (
                      <div className="absolute inset-0 bg-cream" />
                    );
                  })()}
                  <div
                    aria-hidden="true"
                    className="pointer-events-none absolute inset-x-0 bottom-0 h-28 bg-gradient-to-t from-blue-950/35 to-transparent"
                  />
                  {featured.categories[0] ? (
                    <span className="absolute left-4 top-4 bg-paper/95 px-3 py-1 font-display text-[0.68rem] font-semibold uppercase tracking-[0.16em] text-blue-700 shadow-sm backdrop-blur-sm">
                      {featured.categories[0].name}
                    </span>
                  ) : null}
                </div>

                <div className="flex flex-col justify-center">
                  <span className="font-display text-[0.62rem] font-medium uppercase tracking-[0.22em] text-emerald">
                    Article à la une
                  </span>
                  <h2 className="mt-4 font-editorial text-[clamp(1.75rem,3vw,2.6rem)] font-medium leading-[1.15] text-ink-900 transition-colors group-hover:text-blue-800">
                    {featured.title}
                  </h2>
                  <p className="mt-5 text-[1.0625rem] leading-[1.65] text-ink-600 line-clamp-4">
                    {featured.excerpt}
                  </p>
                  <div className="mt-6 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-ink-500">
                    <span className="font-medium text-ink-700">
                      {featured.authorName ?? "Gathe"}
                    </span>
                    <span aria-hidden="true" className="text-line-200">·</span>
                    <span>{formatDate(featured.date, locale)}</span>
                  </div>
                  <span className="mt-7 inline-flex items-center gap-2 text-sm font-semibold text-blue-700 transition-colors group-hover:text-blue-800">
                    {t("readArticle")}
                    <ArrowRight aria-hidden="true" className="size-4 transition-transform duration-300 group-hover:translate-x-1" />
                  </span>
                </div>
              </Link>
            </Reveal>
          </Container>
        </section>
      ) : null}

      {/* ===== Rest of articles — clean grid on cream ===== */}
      <section className="relative isolate overflow-hidden bg-cream py-16 lg:py-20">
        <div aria-hidden="true" className="absolute inset-x-0 top-0 h-px bg-line-200" />
        <div aria-hidden="true" className="absolute inset-x-0 bottom-0 h-px bg-line-200" />
        <InstitutionalDecor variant="grid" />

        <Container className="relative">
          {posts.length === 0 ? (
            <p className="rounded-md border border-dashed border-line-200 bg-paper/70 p-10 text-center text-ink-600">
              {t("empty")}
            </p>
          ) : rest.length > 0 ? (
            <>
              <div className="flex items-end justify-between gap-6 border-b border-line-200 pb-6">
                <span className="label-num">
                  02 · Tous les articles
                </span>
                <span className="text-[0.7rem] font-medium uppercase tracking-[0.2em] text-ink-500">
                  {rest.length} {rest.length > 1 ? "articles" : "article"}
                </span>
              </div>
              <div className="mt-10 grid gap-x-6 gap-y-12 sm:grid-cols-2 lg:grid-cols-3 lg:gap-x-8">
                {rest.map((post, i) => (
                  <Reveal key={post.id} delay={i * 70}>
                    <ArticleCard post={post} locale={locale} />
                  </Reveal>
                ))}
              </div>
            </>
          ) : (
            <p className="text-center text-ink-500">Plus d&#39;articles bientôt.</p>
          )}
        </Container>
      </section>

      <CtaBand />
    </>
  );
}
