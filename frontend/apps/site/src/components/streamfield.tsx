import { cn } from "@gathe/ui";
import type { StreamBlock } from "@/lib/wagtail";

/**
 * Renders a Wagtail StreamField (as returned by the API) into React.
 * Block content authored in the CMS by trusted editors → rich_text HTML is
 * rendered with dangerouslySetInnerHTML. Unknown block types are skipped.
 */
export function StreamField({ blocks, className }: { blocks: StreamBlock[]; className?: string }) {
  if (!blocks?.length) return null;
  return (
    <div className={className}>
      {blocks.map((block) => (
        <BlockView key={block.id ?? Math.random()} block={block} />
      ))}
    </div>
  );
}

const calloutStyles: Record<string, string> = {
  info: "border-blue-300 bg-blue-100 text-ink-700",
  success: "border-blue-300 bg-blue-100 text-ink-700",
  neutral: "border-line-200 bg-surface-50 text-ink-700",
};

function BlockView({ block }: { block: StreamBlock }) {
  switch (block.type) {
    case "rich_text": {
      const v = block.value as { body: string };
      return <div className="prose-gathe max-w-2xl" dangerouslySetInnerHTML={{ __html: v.body }} />;
    }
    case "heading": {
      const v = block.value as { eyebrow?: string; title: string; text?: string; alignment?: "left" | "center" };
      return (
        <header className={cn("mt-12 flex flex-col gap-2", v.alignment === "center" && "items-center text-center")}>
          {v.eyebrow ? (
            <span className="text-eyebrow font-semibold uppercase tracking-[0.08em] text-blue-700">{v.eyebrow}</span>
          ) : null}
          <h2 className="text-balance text-2xl font-bold text-ink-900 sm:text-3xl">{v.title}</h2>
          {v.text ? <div className="prose-gathe max-w-2xl" dangerouslySetInnerHTML={{ __html: v.text }} /> : null}
        </header>
      );
    }
    case "callout": {
      const v = block.value as { style?: string; title?: string; body: string };
      return (
        <div className={cn("mt-6 max-w-2xl rounded-[var(--radius-lg)] border p-5", calloutStyles[v.style ?? "info"] ?? calloutStyles.info)}>
          {v.title ? <p className="font-semibold text-ink-900">{v.title}</p> : null}
          <div className="prose-gathe" dangerouslySetInnerHTML={{ __html: v.body }} />
        </div>
      );
    }
    case "quote": {
      const v = block.value as { quote: string; author?: string; role?: string };
      return (
        <figure className="mt-8 max-w-2xl border-l-[3px] border-green-400 pl-5">
          <blockquote className="text-lg italic text-ink-700">“{v.quote}”</blockquote>
          {v.author ? (
            <figcaption className="mt-2 text-sm text-ink-500">
              {v.author}
              {v.role ? <span> — {v.role}</span> : null}
            </figcaption>
          ) : null}
        </figure>
      );
    }
    case "image": {
      const v = block.value as { image: { url?: string; alt?: string } | number; caption?: string; alt?: string };
      const img = typeof v.image === "object" ? v.image : null;
      if (!img?.url) return null;
      return (
        <figure className="mt-8">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={img.url} alt={v.alt || img.alt || ""} className="rounded-[var(--radius-xl)]" />
          {v.caption ? <figcaption className="mt-2 text-sm text-ink-500">{v.caption}</figcaption> : null}
        </figure>
      );
    }
    default:
      return null;
  }
}
