import Image from "next/image";
import { getTranslations } from "next-intl/server";
import { ArrowRight } from "lucide-react";

import { Link } from "@/i18n/navigation";
import { formatDate } from "@/lib/format";
import { blogFallbackImage } from "@/lib/site-config";
import type { BlogListItem } from "@/lib/wagtail";

/** Editorial article card — press cutout style: photo on top with a hairline
 *  caption, italic byline, serif H3 title in Lora, three-line excerpt, and a
 *  bottom "read article" link. No card chrome — the photo + filets do the work. */
export async function ArticleCard({ post, locale }: { post: BlogListItem; locale: string }) {
  const t = await getTranslations({ locale, namespace: "blog" });
  const date = formatDate(post.date, locale);
  const imageUrl = post.coverImage?.url ?? blogFallbackImage(post.slug);
  const imageAlt = post.coverImage?.alt ?? post.title;
  return (
    <Link
      href={`/blog/${post.slug}`}
      className="group flex h-full flex-col border-t border-line-200 pt-5 transition-colors hover:border-blue-700"
    >
      <div className="relative aspect-[16/10] overflow-hidden bg-line-100">
        {imageUrl ? (
          <Image
            src={imageUrl}
            alt={imageAlt}
            fill
            sizes="(min-width: 1024px) 33vw, (min-width: 640px) 50vw, 100vw"
            className="object-cover transition-transform duration-700 group-hover:scale-[1.03]"
          />
        ) : null}
        {post.categories[0] ? (
          <span className="absolute left-3 top-3 bg-paper px-2.5 py-1 text-[0.68rem] font-semibold uppercase tracking-[0.14em] text-blue-700">
            {post.categories[0].name}
          </span>
        ) : null}
      </div>
      <div className="flex grow flex-col gap-2 pt-4">
        <span className="caption">{t("byline", { author: post.authorName ?? "GATHE", date })}</span>
        <h3 className="font-editorial text-lg font-medium leading-snug text-ink-900 transition-colors group-hover:text-blue-700">
          {post.title}
        </h3>
        <p className="line-clamp-3 grow text-sm leading-relaxed text-ink-600">{post.excerpt}</p>
        <span className="mt-2 inline-flex items-center gap-1.5 text-sm font-semibold text-blue-700">
          {t("readArticle")}
          <ArrowRight aria-hidden="true" className="size-4 transition-transform group-hover:translate-x-1" />
        </span>
      </div>
    </Link>
  );
}
