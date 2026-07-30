"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";

/** Animates a number from 0 to `value` when it enters the viewport (once).
 *  Natif (IntersectionObserver + matchMedia) — pas de dépendance framer-motion. */
export function CountUp({
  value,
  locale = "fr",
  duration = 1.6,
  suffix,
  className,
}: {
  value: number;
  locale?: string;
  duration?: number;
  suffix?: ReactNode;
  className?: string;
}) {
  const ref = useRef<HTMLSpanElement>(null);
  const [display, setDisplay] = useState(0);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduce) {
      setDisplay(value);
      return;
    }

    let raf = 0;
    const run = () => {
      const start = performance.now();
      const tick = (now: number) => {
        const p = Math.min(1, (now - start) / (duration * 1000));
        const eased = 1 - Math.pow(1 - p, 3); // ease-out-cubic
        setDisplay(Math.round(eased * value));
        if (p < 1) raf = requestAnimationFrame(tick);
      };
      raf = requestAnimationFrame(tick);
    };

    // `once` : on se déconnecte dès la première entrée dans le viewport.
    const io = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          io.disconnect();
          run();
        }
      },
      { rootMargin: "0px 0px -15% 0px" },
    );
    io.observe(el);

    return () => {
      io.disconnect();
      cancelAnimationFrame(raf);
    };
  }, [value, duration]);

  const bcp47 = locale === "en" ? "en-GB" : "fr-FR";
  return (
    <span ref={ref} className={className}>
      {display.toLocaleString(bcp47)}
      {suffix}
    </span>
  );
}
