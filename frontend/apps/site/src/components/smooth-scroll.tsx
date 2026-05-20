"use client";

import { useEffect } from "react";
import Lenis from "lenis";

/**
 * Site-wide smooth scroll powered by Lenis.
 *
 * Mounted once in the locale layout. Reads `prefers-reduced-motion` and
 * disables itself entirely if the user has the OS preference set, so the
 * site still works for accessibility-conscious visitors.
 *
 * Lenis hijacks wheel/touch events to interpolate scrollY natively, which
 * Framer Motion's `useScroll()` consumes transparently — no wiring needed
 * for downstream parallax components.
 */
export function SmoothScroll() {
  useEffect(() => {
    if (typeof window === "undefined") return;

    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    if (mq.matches) return;

    const lenis = new Lenis({
      duration: 1.05,
      // ease-out-expo — feels premium without lag
      easing: (t) => Math.min(1, 1.001 - Math.pow(2, -10 * t)),
      orientation: "vertical",
      smoothWheel: true,
      wheelMultiplier: 1,
      touchMultiplier: 1.4,
      lerp: 0.085,
    });

    let rafId = 0;
    function raf(time: number) {
      lenis.raf(time);
      rafId = requestAnimationFrame(raf);
    }
    rafId = requestAnimationFrame(raf);

    return () => {
      cancelAnimationFrame(rafId);
      lenis.destroy();
    };
  }, []);

  return null;
}
