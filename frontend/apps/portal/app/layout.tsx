import type { Metadata } from "next";
import type { ReactNode } from "react";
import { Syne, DM_Sans, JetBrains_Mono } from "next/font/google";

import "./globals.css";

// Design system : Syne (display) / DM Sans (corps) / JetBrains Mono (chiffres).
const syne = Syne({ subsets: ["latin", "latin-ext"], weight: ["600", "700", "800"], variable: "--font-syne", display: "swap" });
const dmSans = DM_Sans({ subsets: ["latin", "latin-ext"], weight: ["400", "500", "600", "700"], variable: "--font-dmsans", display: "swap" });
const jetbrains = JetBrains_Mono({ subsets: ["latin"], weight: ["400", "500", "600"], variable: "--font-jetbrains", display: "swap" });

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
