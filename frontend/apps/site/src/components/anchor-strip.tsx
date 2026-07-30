"use client";

import { useEffect, useState } from "react";

import { Container } from "@gathe/ui";

type Anchor = { id: string; label: string };

/**
 * Sticky strip d'ancres — éditorial press style (numéro `0X` en terra,
 * titre fin). Le lien correspondant à la section visible est mis en
 * évidence via IntersectionObserver (scroll-spy). Composant générique
 * réutilisable sur n'importe quelle page longue (Services, À propos, …).
 */
export function AnchorStrip({ anchors }: { anchors: Anchor[] }) {
  const [activeId, setActiveId] = useState<string>(anchors[0]?.id ?? "");

  useEffect(() => {
    if (typeof window === "undefined" || anchors.length === 0) return;
    const sections = anchors
      .map((a) => document.getElementById(a.id))
      .filter((el): el is HTMLElement => el !== null);
    if (sections.length === 0) return;

    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((e) => e.isIntersecting)
          .sort((a, b) => b.intersectionRatio - a.intersectionRatio);
        if (visible[0]) {
          setActiveId(visible[0].target.id);
        }
      },
      {
        // Trigger when section's top crosses the band just under the sticky strip.
        rootMargin: "-30% 0px -55% 0px",
        threshold: [0, 0.25, 0.5, 0.75, 1],
      },
    );

    sections.forEach((s) => observer.observe(s));
    return () => observer.disconnect();
  }, [anchors]);

  return (
    <div className="sticky top-[4.25rem] z-30 border-b border-line-200 bg-paper/95 backdrop-blur lg:top-[6.5rem]">
      <Container className="flex gap-x-6 gap-y-2 overflow-x-auto py-3 text-sm">
        {anchors.map((a, i) => {
          const isActive = a.id === activeId;
          return (
            <a
              key={a.id}
              href={`#${a.id}`}
              aria-current={isActive ? "location" : undefined}
              className={`shrink-0 whitespace-nowrap border-b-2 pb-1 transition-colors ${
                isActive
                  ? "border-blue-700 text-ink-900"
                  : "border-transparent text-ink-600 hover:text-blue-700"
              }`}
            >
              <span className="mr-1.5 text-[0.7rem] font-medium tracking-[0.14em] text-terra-600">
                {`0${i + 1}`}
              </span>
              {a.label}
            </a>
          );
        })}
      </Container>
    </div>
  );
}
