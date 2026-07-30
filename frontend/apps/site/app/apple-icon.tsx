import { ImageResponse } from "next/og";

// Icône iOS (écran d'accueil / raccourci) — appleWebApp est activé dans le
// layout ; sans ce fichier, iOS affiche une capture par défaut.
export const size = { width: 180, height: 180 };
export const contentType = "image/png";

export default function AppleIcon() {
  return new ImageResponse(
    (
      <div
        style={{
          height: "100%",
          width: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "linear-gradient(140deg, #0e4d92 0%, #081a33 100%)",
          color: "white",
          fontSize: 116,
          fontWeight: 800,
          fontFamily: "sans-serif",
          position: "relative",
        }}
      >
        G
        {/* Swoosh accent émeraude */}
        <div
          style={{
            position: "absolute",
            bottom: 34,
            width: 74,
            height: 8,
            borderRadius: 4,
            background: "#3aaa35",
          }}
        />
      </div>
    ),
    { ...size },
  );
}
