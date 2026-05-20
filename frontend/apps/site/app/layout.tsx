import type { ReactNode } from "react";
import "./globals.css";

// A root layout is required by Next.js even though the per-locale layout
// (app/[locale]/layout.tsx) renders <html> / <body>. This just passes through.
export default function RootLayout({ children }: { children: ReactNode }) {
  return children;
}
