"use client";

import { type ElementType, type ReactNode } from "react";
import { motion, useReducedMotion } from "framer-motion";

const EASE = [0.16, 1, 0.3, 1] as const;

/**
 * Reveals text "monumental" style — each line slides up from behind a mask,
 * staggered. Pass the text already split into lines via the `lines` prop
 * (so we control wrapping precisely). Honours prefers-reduced-motion.
 */
export function SplitText({
  lines,
  as: Tag = "h1",
  className,
  delay = 0,
  accentLineIndex,
  accentClassName = "text-emerald",
}: {
  lines: ReactNode[];
  as?: ElementType;
  className?: string;
  delay?: number;
  /** index of a line to colour with `accentClassName` */
  accentLineIndex?: number;
  accentClassName?: string;
}) {
  const reduce = useReducedMotion();
  return (
    <Tag className={className}>
      {lines.map((line, i) => (
        <span key={i} className="block overflow-hidden pb-[0.06em]">
          <motion.span
            className={`block ${i === accentLineIndex ? accentClassName : ""}`}
            initial={reduce ? false : { y: "115%" }}
            whileInView={reduce ? undefined : { y: "0%" }}
            viewport={{ once: true, margin: "0px 0px -8% 0px" }}
            transition={{ duration: 0.9, ease: EASE, delay: delay + i * 0.09 }}
          >
            {line}
          </motion.span>
        </span>
      ))}
    </Tag>
  );
}
