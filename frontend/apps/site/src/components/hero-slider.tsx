"use client";

import Image from "next/image";
import { useEffect, useRef, useState } from "react";

import { cn } from "@gathe/ui";

export type HeroSlide = { src: string; alt?: string };

/** Background cross-fade slider for the hero with a subtle parallax pull.
 *  - The image layer rotates on a slow cross-fade (1.4s) every `intervalMs`.
 *  - On scroll, the photo layer drifts up by ~10% and scales up by ~6% over
 *    the first ~800 px of scroll. The overlay tints stay still, so the
 *    headline keeps reading cleanly even when the photos move.
 *  - `prefers-reduced-motion` désactive la parallaxe.
 *  - Natif (scroll listener + rAF) — plus de dépendance framer-motion. */
export function HeroSlider({
  slides,
  intervalMs = 5500,
  className,
}: {
  slides: HeroSlide[];
  intervalMs?: number;
  className?: string;
}) {
  const [idx, setIdx] = useState(0);
  const layerRef = useRef<HTMLDivElement>(null);

  // Cross-fade automatique
  useEffect(() => {
    if (slides.length < 2) return;
    const id = setInterval(() => {
      setIdx((i) => (i + 1) % slides.length);
    }, intervalMs);
    return () => clearInterval(id);
  }, [slides.length, intervalMs]);

  // Parallaxe au scroll (throttlée en rAF, désactivée en reduced-motion)
  useEffect(() => {
    const el = layerRef.current;
    if (!el) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    let raf = 0;
    const update = () => {
      raf = 0;
      const p = Math.min(window.scrollY / 800, 1);
      el.style.transform = `translateY(${-10 * p}%) scale(${1 + 0.06 * p})`;
    };
    const onScroll = () => {
      if (!raf) raf = requestAnimationFrame(update);
    };
    update();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => {
      window.removeEventListener("scroll", onScroll);
      if (raf) cancelAnimationFrame(raf);
    };
  }, []);

  return (
    <div aria-hidden="true" className={cn("absolute inset-0 -z-10", className)}>
      {/* Couche photo (parallaxe) */}
      <div ref={layerRef} className="absolute inset-0 will-change-transform">
        {slides.map((s, i) => (
          <div
            key={s.src}
            className={cn(
              "absolute inset-0 transition-opacity duration-[1400ms] ease-out",
              i === idx ? "opacity-100" : "opacity-0",
            )}
          >
            <Image
              src={s.src}
              alt={s.alt ?? ""}
              fill
              priority={i === 0}
              sizes="100vw"
              className="object-cover object-center"
            />
          </div>
        ))}
      </div>

      {/* Overlays statiques — hors parallaxe pour garder le titre lisible.
          Voile CINÉMATIQUE : la photo respire (haut/milieu), on assombrit le
          centre juste ce qu'il faut derrière le titre + le bas pour la bande KPI. */}
      {/* Scrim radial doux derrière le titre — TRANSPARENT sur les bords pour
          laisser respirer la photo (un radial opaque en périphérie noyait tout). */}
      <div className="absolute inset-0 bg-[radial-gradient(78%_60%_at_50%_40%,rgba(4,22,48,0.34)_0%,rgba(4,22,48,0)_70%)]" />
      {/* Dégradé vertical léger : photo visible au milieu, franc en bas (bande KPI). */}
      <div className="absolute inset-0 bg-[linear-gradient(180deg,rgba(4,22,48,0.42)_0%,rgba(4,22,48,0.12)_45%,rgba(4,22,48,0.80)_100%)]" />

      {/* Indicateurs de slide */}
      {slides.length > 1 ? (
        <div className="pointer-events-none absolute inset-x-0 bottom-6 flex items-center justify-center gap-2">
          {slides.map((s, i) => (
            <span
              key={s.src}
              className={cn(
                "h-[3px] w-8 rounded-full bg-surface-50/30 transition-all duration-500",
                i === idx && "bg-emerald/90 w-12",
              )}
            />
          ))}
        </div>
      ) : null}
    </div>
  );
}
