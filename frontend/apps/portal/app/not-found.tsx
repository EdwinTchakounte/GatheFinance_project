import Link from "next/link";

// Global fallback for paths outside the [locale] segment. Localised 404s live in
// app/[locale]/not-found.tsx.
export default function GlobalNotFound() {
  return (
    <html lang="fr">
      <body
        style={{
          fontFamily: "ui-sans-serif, system-ui, sans-serif",
          minHeight: "100vh",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          flexDirection: "column",
          gap: "1rem",
          color: "#0b1320",
          background: "#fff",
        }}
      >
        <p style={{ fontSize: "3.5rem", fontWeight: 700, color: "#0e4d92", margin: 0 }}>404</p>
        <p style={{ margin: 0 }}>Page introuvable / Page not found</p>
        <Link href="/" style={{ color: "#0e4d92", fontWeight: 600 }}>
          Gathe Finance →
        </Link>
      </body>
    </html>
  );
}
