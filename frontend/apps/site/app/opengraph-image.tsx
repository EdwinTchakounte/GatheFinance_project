import { ImageResponse } from "next/og";

// Image de partage social (Open Graph / Twitter) générée dynamiquement.
// Héritée par toutes les routes → cartes de partage brandées + `image` du
// JSON-LD (json-ld.tsx référence ${siteUrl}/opengraph-image) enfin résolue.
export const alt = "GATHE Finance — Coopérative d'épargne et de crédit au Cameroun";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function OpengraphImage() {
  return new ImageResponse(
    (
      <div
        style={{
          height: "100%",
          width: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          padding: "72px 80px",
          background:
            "linear-gradient(135deg, #081a33 0%, #0e4d92 62%, #0b3f78 100%)",
          color: "white",
          fontFamily: "sans-serif",
        }}
      >
        {/* Bandeau haut : marque + puce accent émeraude */}
        <div style={{ display: "flex", alignItems: "center", gap: 20 }}>
          <div
            style={{
              width: 18,
              height: 18,
              borderRadius: 9999,
              background: "#3aaa35",
              boxShadow: "0 0 30px rgba(58,170,53,0.8)",
            }}
          />
          <div
            style={{
              fontSize: 30,
              fontWeight: 700,
              letterSpacing: 2,
              textTransform: "uppercase",
              color: "rgba(255,255,255,0.82)",
            }}
          >
            GATHE Finance
          </div>
        </div>

        {/* Titre principal */}
        <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
          <div
            style={{
              fontSize: 74,
              fontWeight: 800,
              lineHeight: 1.05,
              maxWidth: 960,
            }}
          >
            {"L'auto-financement solidaire au service du Cameroun"}
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
            <div style={{ width: 64, height: 5, background: "#3aaa35", borderRadius: 4 }} />
            <div style={{ fontSize: 30, color: "rgba(255,255,255,0.78)" }}>
              Épargne · Crédit · Placement · Douala
            </div>
          </div>
        </div>
      </div>
    ),
    { ...size },
  );
}
