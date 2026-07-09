import type { StreamBlock } from "@/lib/wagtail";

// Styles de base pour le HTML rich_text (pas de plugin typography côté portail).
const richText =
  "text-ink-700 leading-relaxed [&_p]:mb-3 [&_h2]:mt-6 [&_h2]:mb-2 [&_h2]:text-lg [&_h2]:font-semibold [&_h2]:text-ink-900 [&_h3]:mt-4 [&_h3]:font-semibold [&_h3]:text-ink-900 [&_ul]:my-3 [&_ul]:list-disc [&_ul]:pl-5 [&_ol]:my-3 [&_ol]:list-decimal [&_ol]:pl-5 [&_strong]:font-semibold [&_strong]:text-ink-900 [&_a]:text-blue-700 [&_a]:underline";

/**
 * Rend un StreamField Wagtail (articles rédigés par le staff → HTML de
 * confiance). Les types de blocs inconnus sont ignorés.
 */
export function StreamField({ blocks }: { blocks: StreamBlock[] }) {
  if (!blocks?.length) return null;
  return (
    <div className="space-y-1">
      {blocks.map((b) => (
        <Block key={b.id ?? Math.random()} block={b} />
      ))}
    </div>
  );
}

function Block({ block }: { block: StreamBlock }) {
  switch (block.type) {
    case "rich_text": {
      const v = block.value as { body: string };
      return (
        <div className={richText} dangerouslySetInnerHTML={{ __html: v.body }} />
      );
    }
    case "heading": {
      const v = block.value as {
        eyebrow?: string;
        title: string;
        text?: string;
      };
      return (
        <header className="mt-6 flex flex-col gap-1">
          {v.eyebrow ? (
            <span className="text-xs font-semibold uppercase tracking-wide text-blue-700">
              {v.eyebrow}
            </span>
          ) : null}
          <h2 className="text-xl font-semibold text-ink-900">{v.title}</h2>
          {v.text ? (
            <div className={richText} dangerouslySetInnerHTML={{ __html: v.text }} />
          ) : null}
        </header>
      );
    }
    case "callout": {
      const v = block.value as { title?: string; body: string };
      return (
        <div className="mt-4 rounded-md border border-blue-200 bg-blue-50/60 p-4">
          {v.title ? (
            <p className="font-semibold text-ink-900">{v.title}</p>
          ) : null}
          <div className={richText} dangerouslySetInnerHTML={{ __html: v.body }} />
        </div>
      );
    }
    case "quote": {
      const v = block.value as { quote: string; author?: string; role?: string };
      return (
        <figure className="mt-5 border-l-[3px] border-emerald pl-4">
          <blockquote className="text-base italic text-ink-700">
            “{v.quote}”
          </blockquote>
          {v.author ? (
            <figcaption className="mt-1 text-sm text-ink-500">
              {v.author}
              {v.role ? <span> — {v.role}</span> : null}
            </figcaption>
          ) : null}
        </figure>
      );
    }
    case "image": {
      const v = block.value as {
        image: { url?: string; alt?: string } | number;
        caption?: string;
        alt?: string;
      };
      const img = typeof v.image === "object" ? v.image : null;
      if (!img?.url) return null;
      return (
        <figure className="mt-5">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={img.url} alt={v.alt || img.alt || ""} className="rounded-md" />
          {v.caption ? (
            <figcaption className="mt-1 text-sm text-ink-500">
              {v.caption}
            </figcaption>
          ) : null}
        </figure>
      );
    }
    default:
      return null;
  }
}
