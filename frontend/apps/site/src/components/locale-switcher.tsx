"use client";

import { useLocale } from "next-intl";
import { usePathname, useRouter } from "@/i18n/navigation";
import { locales } from "@/i18n/routing";
import { cn } from "@gathe/ui";

const labels: Record<string, string> = { fr: "FR", en: "EN" };

export function LocaleSwitcher({ className }: { className?: string }) {
  const locale = useLocale();
  const pathname = usePathname();
  const router = useRouter();

  return (
    <div
      role="group"
      aria-label="Language"
      className={cn("inline-flex items-center rounded-full border border-line-200 bg-surface-0 p-0.5 text-xs font-semibold", className)}
    >
      {locales.map((l) => {
        const active = l === locale;
        return (
          <button
            key={l}
            type="button"
            aria-current={active ? "true" : undefined}
            onClick={() => {
              if (!active) router.replace(pathname, { locale: l });
            }}
            className={cn(
              "rounded-full px-2.5 py-1 transition-colors",
              active ? "bg-blue-700 text-white" : "text-ink-500 hover:text-blue-700",
            )}
          >
            {labels[l] ?? l.toUpperCase()}
          </button>
        );
      })}
    </div>
  );
}
