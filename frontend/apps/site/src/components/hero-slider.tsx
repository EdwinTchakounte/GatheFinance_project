"use client";

import Image from "next/image";
import { useEffect, useRef, useState } from "react";
import { motion, useReducedMotion, useScroll, useTransform } from "framer-motion";

import { cn } from "@gathe/ui";

export type HeroSlide = { src: string; alt?: string };

/** Background cross-fade slider for the hero with a subtle parallax pull.
 *  - The image layer rotates on a slow cross-fade (1.4s) every `intervalMs`.
 *  - On scroll, the photo layer drifts up by ~10% and scales up by ~6% over
 *    the first ~800 px of scroll. The overlay tints stay still, so the
 *    headline keeps reading cleanly even when the photos move.
 *  - `prefers-reduced-motion` collapses the parallax to a no-op via Framer's
 *    `useReducedMotion`. */
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
  const ref = useRef<HTMLDivElement>(null);
  const reduce = useReducedMotion();

  // Framer reads window scrollY transparently — Lenis interpolation is
  // already pumping that value, so we don't need to wire anything else.
  const { scrollY } = useScroll();
  const y = useTransform(scrollY, [0, 800], reduce ? ["0%", "0%"] : ["0%", "-10%"]);
  const scale = useTransform(scrollY, [0, 800], reduce ? [1, 1] : [1, 1.06]);

  useEffect(() => {
    if (slides.length < 2) return;
    const id = setInterval(() => {
      setIdx((i) => (i + 1) % slides.length);
    }, intervalMs);
    return () => clearInterval(id);
  }, [slides.length, intervalMs]);

  return (
    <div aria-hidden="true" className={cn("absolute inset-0 -z-10", className)} ref={ref}>
      {/* Parallax photo layer */}
      <motion.div style={{ y, scale }} className="absolute inset-0 will-change-transform">
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
      </motion.div>

      {/* Static overlay tints — kept outside parallax so the headline stays
          readable at any scroll depth */}
      <div className="absolute inset-0 bg-[linear-gradient(96deg,rgba(5,29,58,0.95)_0%,rgba(5,29,58,0.78)_45%,rgba(5,29,58,0.45)_90%)]" />
      <div className="absolute inset-0 bg-blue-950/30" />

      {/* Slide indicators — sober hairline dots */}
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
