"use client";

import { useEffect, useState } from "react";

/**
 * Bascule thème clair (défaut) ↔ sombre. Écrit `data-theme` sur <html> et
 * persiste le choix dans localStorage. Le no-flash initial est géré par un
 * script inline dans le layout ; ce composant ne fait que (dé)synchroniser.
 */
export function ThemeToggle({ className = "" }: { className?: string }) {
  const [dark, setDark] = useState(false);

  useEffect(() => {
    const el = document.documentElement;
    setDark(el.dataset.theme === "dark" || el.classList.contains("dark"));
  }, []);

  function toggle() {
    const next = !dark;
    setDark(next);
    const el = document.documentElement;
    if (next) {
      el.dataset.theme = "dark";
      el.classList.add("dark");
    } else {
      delete el.dataset.theme;
      el.classList.remove("dark");
    }
    try {
      localStorage.setItem("gathe-theme", next ? "dark" : "light");
    } catch {
      /* stockage indisponible — on ignore */
    }
  }

  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={dark ? "Passer en thème clair" : "Passer en thème sombre"}
      title={dark ? "Thème clair" : "Thème sombre"}
      className={`inline-flex h-9 w-9 items-center justify-center rounded-full border border-line-200 text-ink-700 transition-colors hover:border-blue-300 hover:text-ink-900 ${className}`}
    >
      {dark ? (
        // Soleil
        <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
          <circle cx="12" cy="12" r="4" />
          <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
        </svg>
      ) : (
        // Lune
        <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
          <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z" />
        </svg>
      )}
    </button>
  );
}
