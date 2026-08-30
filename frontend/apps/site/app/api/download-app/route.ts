import type { NextRequest } from "next/server";

// Proxy de téléchargement de l'APK : relaie le fichier hébergé sur Google Drive
// en RÉ-EXPOSANT sa taille (Content-Length) et un Content-Disposition
// « attachment », pour que le navigateur (et notre composant client) puisse
// afficher un VRAI pourcentage de progression. Sans ce proxy, Drive est
// cross-origin et le % réel est impossible.
export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const APK_DRIVE_FILE_ID = "1kJEkKbHthwVWTdF47SazLJKqbL-5T88f";
const DRIVE_URL = `https://drive.google.com/uc?export=download&id=${APK_DRIVE_FILE_ID}&confirm=t`;

export async function GET(_req: NextRequest) {
  let upstream: Response;
  try {
    upstream = await fetch(DRIVE_URL, { redirect: "follow" });
  } catch {
    return new Response("Téléchargement indisponible pour le moment.", {
      status: 502,
    });
  }

  const contentType = upstream.headers.get("content-type") ?? "";
  // Drive renvoie parfois une page HTML (interstitiel anti-virus) au lieu du
  // binaire : on refuse plutôt que de servir du HTML nommé .apk.
  if (!upstream.ok || !upstream.body || contentType.includes("text/html")) {
    return new Response(
      "Téléchargement momentanément indisponible. Réessaie dans un instant.",
      { status: 502 },
    );
  }

  const headers = new Headers();
  headers.set("Content-Type", "application/vnd.android.package-archive");
  headers.set(
    "Content-Disposition",
    'attachment; filename="Gathe-Finance.apk"',
  );
  const len = upstream.headers.get("content-length");
  if (len) headers.set("Content-Length", len);
  headers.set("Cache-Control", "no-store");

  return new Response(upstream.body, { status: 200, headers });
}
