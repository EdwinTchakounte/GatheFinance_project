"use client";

import type { PointerEvent as ReactPointerEvent, ReactNode } from "react";
import { useRef } from "react";
import { motion, useMotionValue, useReducedMotion, useSpring } from "framer-motion";

import { cn } from "@gathe/ui";

/**
 * Magnetic interaction — wraps any focusable element (button, link, etc.) and
 * makes it follow the pointer when the cursor is inside its bounding box.
 * Subtle by default (`strength: 0.28` → max ≈ 5-8 px of pull on a standard
 * lg button), the spring eases the element back to rest on pointer-leave.
 *
 *  - Respects `prefers-reduced-motion` (no transform, just renders children).
 *  - Wrapper is `inline-flex` so it doesn't break button layout.
 *  - Pointer events used (works for mouse + pen, but not touch — desktop-only
 *    flourish by design).
 */
export function Magnetic({
  children,
  strength = 0.28,
  className,
}: {
  children: ReactNode;
  strength?: number;
  className?: string;
}) {
  const ref = useRef<HTMLSpanElement>(null);
  const reduce = useReducedMotion();

  const x = useMotionValue(0);
  const y = useMotionValue(0);
  const xs = useSpring(x, { stiffness: 240, damping: 22, mass: 0.55 });
  const ys = useSpring(y, { stiffness: 240, damping: 22, mass: 0.55 });

  function handleMove(e: ReactPointerEvent<HTMLSpanElement>) {
    if (reduce || e.pointerType === "touch") return;
    const el = ref.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const cx = rect.left + rect.width / 2;
    const cy = rect.top + rect.height / 2;
    x.set((e.clientX - cx) * strength);
    y.set((e.clientY - cy) * strength);
  }

  function handleLeave() {
    x.set(0);
    y.set(0);
  }

  return (
    <motion.span
      ref={ref}
      onPointerMove={handleMove}
      onPointerLeave={handleLeave}
      style={reduce ? undefined : { x: xs, y: ys }}
      className={cn("inline-flex", className)}
    >
      {children}
    </motion.span>
  );
}
