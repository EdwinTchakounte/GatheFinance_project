import { NextResponse } from "next/server";

/**
 * Proxy same-origin → backend DRF : liste publique des campagnes micro-crédit
 * ouvertes. Évite CORS + n'expose pas l'URL backend au navigateur.
 *   GET /api/campaigns -> backend GET /api/v1/loans/campaigns/active/
 */
const BACKEND = (process.env.CMS_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

export async function GET() {
  try {
    const res = await fetch(`${BACKEND}/api/v1/loans/campaigns/active/?limit=50`, {
      cache: "no-store",
      headers: { Accept: "application/json" },
    });
    const text = await res.text();
    return new NextResponse(text, {
      status: res.status,
      headers: { "Content-Type": res.headers.get("content-type") ?? "application/json" },
    });
  } catch {
    return NextResponse.json({ results: [] }, { status: 502 });
  }
}
