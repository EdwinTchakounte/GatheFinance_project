import type { Metadata } from "next";
import type { ReactNode } from "react";
import localFont from "next/font/local";

import "./globals.css";

// Design system : Syne (display) / DM Sans (corps) / JetBrains Mono (chiffres).
// Polices variables AUTO-HÉBERGÉES (subset latin, couvre le français) : plus
// aucune dépendance réseau à Google Fonts au moment du build.
const syne = localFont({ src: "../../../fonts/syne-latin.woff2", weight: "600 800", variable: "--font-syne", display: "swap" });
const dmSans = localFont({ src: "../../../fonts/dmsans-latin.woff2", weight: "400 700", variable: "--font-dmsans", display: "swap" });
const jetbrains = localFont({ src: "../../../fonts/jetbrains-latin.woff2", weight: "400 600", variable: "--font-jetbrains", display: "swap" });

export const metadata: Metadata = {
  title: "GATHE Finance · Espace membre",
  description: "Portail membre de la coopérative GATHE Finance.",
  robots: { index: false, follow: false },
};

/**
 * Le `<html>`/`<body>` racine doit vivre ici (App Router) ; le shell visuel
 * (top bar + footer + chrome du portail) est dans `app/[locale]/layout.tsx`
 * pour rester scopé aux pages avec préfixe de locale.
 */
export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="fr" className={`${syne.variable} ${dmSans.variable} ${jetbrains.variable}`} suppressHydrationWarning>
      <body>{children}</body>
    </html>
  );
}
