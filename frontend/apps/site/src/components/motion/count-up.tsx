"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import { useInView, useReducedMotion } from "framer-motion";

/** Animates a number from 0 to `value` when it enters the viewport (once). */
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
  const inView = useInView(ref, { once: true, margin: "0px 0px -15% 0px" });
  const reduce = useReducedMotion();
  const [display, setDisplay] = useState(0);

  useEffect(() => {
    if (reduce || !inView) {
      setDisplay(value);
      return;
    }
    let raf = 0;
    const start = performance.now();
    const tick = (now: number) => {
      const p = Math.min(1, (now - start) / (duration * 1000));
      const eased = 1 - Math.pow(1 - p, 3); // ease-out-cubic
      setDisplay(Math.round(eased * value));
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [inView, value, duration, reduce]);

  const bcp47 = locale === "en" ? "en-GB" : "fr-FR";
  return (
    <span ref={ref} className={className}>
      {display.toLocaleString(bcp47)}
      {suffix}
    </span>
  );
}
