"use client";

import type { PointerEvent as ReactPointerEvent, ReactNode } from "react";
import { useRef } from "react";

import { cn } from "@gathe/ui";

/**
 * Magnetic interaction — wraps any focusable element (button, link, etc.) and
 * makes it follow the pointer when the cursor is inside its bounding box.
 * Subtle by default (`strength: 0.28`), un retour élastique (transition CSS)
 * ramène l'élément au repos au pointer-leave.
 *
 *  - Respecte `prefers-reduced-motion` (aucun transform).
 *  - Wrapper `inline-flex` pour ne pas casser la mise en page du bouton.
 *  - Pointer events (souris + stylet, pas le tactile — flourish desktop).
 *  - Natif : plus de dépendance framer-motion (transform manipulé en direct).
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

  function prefersReduce() {
    return (
      typeof window !== "undefined" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches
    );
  }

  function handleMove(e: ReactPointerEvent<HTMLSpanElement>) {
    if (e.pointerType === "touch" || prefersReduce()) return;
    const el = ref.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const cx = rect.left + rect.width / 2;
    const cy = rect.top + rect.height / 2;
    el.style.transition = "transform 120ms ease-out";
    el.style.transform = `translate(${(e.clientX - cx) * strength}px, ${(e.clientY - cy) * strength}px)`;
  }

  function handleLeave() {
    const el = ref.current;
    if (!el) return;
    // Retour au repos élastique (ease-out cubic).
    el.style.transition = "transform 350ms cubic-bezier(0.22, 1, 0.36, 1)";
    el.style.transform = "translate(0px, 0px)";
  }

  return (
    <span
      ref={ref}
      onPointerMove={handleMove}
      onPointerLeave={handleLeave}
      style={{ willChange: "transform" }}
      className={cn("inline-flex", className)}
    >
      {children}
    </span>
  );
}
