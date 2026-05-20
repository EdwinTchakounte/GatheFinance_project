import type { Metadata } from "next";
import type { ReactNode } from "react";
import { Inter, Plus_Jakarta_Sans, Lora } from "next/font/google";

import "./globals.css";

const jakarta = Plus_Jakarta_Sans({
  subsets: ["latin"],
  weight: ["500", "600", "700"],
  variable: "--font-jakarta",
  display: "swap",
});
const inter = Inter({ subsets: ["latin"], variable: "--font-inter", display: "swap" });
const lora = Lora({ subsets: ["latin"], variable: "--font-lora", display: "swap" });

export const metadata: Metadata = {
  title: "Gathe Finance · Espace membre",
  description: "Portail membre de la coopérative Gathe Finance.",
  robots: { index: false, follow: false },
};

/**
 * Le `<html>`/`<body>` racine doit vivre ici (App Router) ; le shell visuel
 * (top bar + footer + chrome du portail) est dans `app/[locale]/layout.tsx`
 * pour rester scopé aux pages avec préfixe de locale.
 */
export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="fr" className={`${jakarta.variable} ${inter.variable} ${lora.variable}`} suppressHydrationWarning>
      <body>{children}</body>
    </html>
  );
}
