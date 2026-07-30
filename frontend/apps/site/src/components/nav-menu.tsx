"use client";

import { useEffect, useRef, useState } from "react";
import { ChevronDown } from "lucide-react";

import { cn } from "@gathe/ui";
import { Link, usePathname } from "@/i18n/navigation";

export type NavChild = { label: string; href: string; desc?: string };
export type NavEntry = { label: string; href: string; children?: NavChild[] };

/** Desktop primary navigation with hover/focus dropdowns (À propos, Services financiers). */
export function NavMenu({ items }: { items: NavEntry[] }) {
  const [openIdx, setOpenIdx] = useState<number | null>(null);
  const closeTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const navRef = useRef<HTMLElement | null>(null);
  const pathname = usePathname();

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpenIdx(null);
    }
    function onClick(e: MouseEvent) {
      if (navRef.current && !navRef.current.contains(e.target as Node)) setOpenIdx(null);
    }
    document.addEventListener("keydown", onKey);
    document.addEventListener("click", onClick);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("click", onClick);
    };
  }, []);

  function open(i: number) {
    if (closeTimer.current) clearTimeout(closeTimer.current);
    setOpenIdx(i);
  }
  function scheduleClose() {
    if (closeTimer.current) clearTimeout(closeTimer.current);
    closeTimer.current = setTimeout(() => setOpenIdx(null), 140);
  }

  return (
    <nav ref={navRef} aria-label="Navigation principale" className="hidden items-center gap-1 lg:flex">
      {items.map((item, i) => {
        const hasChildren = !!item.children?.length;
        const isOpen = openIdx === i;
        const isCurrent = pathname === (item.href.split("#")[0] || "/");
        return (
          <div
            key={item.href}
            className="relative"
            onMouseEnter={() => hasChildren && open(i)}
            onMouseLeave={() => hasChildren && scheduleClose()}
          >
            <Link
              href={item.href}
              aria-current={isCurrent ? "page" : undefined}
              className={cn(
                "group/nav relative inline-flex items-center gap-1 px-3 py-2.5 text-[0.9rem] font-medium text-ink-700 transition-colors",
                "hover:text-blue-700",
                (isOpen || isCurrent) && "text-blue-700",
              )}
              aria-haspopup={hasChildren || undefined}
              aria-expanded={hasChildren ? isOpen : undefined}
              onFocus={() => hasChildren && open(i)}
              onClick={() => setOpenIdx(null)}
            >
              <span className="relative">
                {item.label}
                {/* Soft underline that grows on hover */}
                <span
                  aria-hidden="true"
                  className={cn(
                    "absolute -bottom-1 left-0 h-px w-full origin-left scale-x-0 bg-terra-500 transition-transform duration-300",
                    "group-hover/nav:scale-x-100",
                    isOpen && "scale-x-100",
                  )}
                />
              </span>
              {hasChildren ? (
                <ChevronDown
                  aria-hidden="true"
                  className={cn("size-3 transition-transform duration-200", isOpen && "rotate-180")}
                />
              ) : null}
            </Link>

            {hasChildren && isOpen ? (
              <div className="absolute left-0 top-full pt-3" onMouseEnter={() => open(i)} onMouseLeave={scheduleClose}>
                <div className="w-72 overflow-hidden rounded-md border border-line-200 bg-paper p-2 shadow-[var(--shadow-md)]">
                  {item.children!.map((c) => (
                    <Link
                      key={c.href}
                      href={c.href}
                      onClick={() => setOpenIdx(null)}
                      className="group/sub block rounded-sm px-3.5 py-2.5 transition-colors hover:bg-cream"
                    >
                      <span className="block text-sm font-medium text-ink-900 transition-colors group-hover/sub:text-blue-700">
                        {c.label}
                      </span>
                      {c.desc ? (
                        <span className="mt-0.5 block text-xs leading-snug text-ink-500">{c.desc}</span>
                      ) : null}
                    </Link>
                  ))}
                </div>
              </div>
            ) : null}
          </div>
        );
      })}
    </nav>
  );
}
