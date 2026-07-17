import { NextResponse } from "next/server";

/**
 * Proxy same-origin → backend DRF : détail public d'une campagne (deep-link).
 *   GET /api/campaigns/:id -> backend GET /api/v1/loans/campaigns/:id/
 */
const BACKEND = (process.env.CMS_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

export async function GET(
  _req: Request,
  ctx: { params: Promise<{ id: string }> },
) {
  const { id } = await ctx.params;
  try {
    const res = await fetch(`${BACKEND}/api/v1/loans/campaigns/${encodeURIComponent(id)}/`, {
      cache: "no-store",
      headers: { Accept: "application/json" },
    });
    const text = await res.text();
    return new NextResponse(text, {
      status: res.status,
      headers: {
        "Content-Type": res.headers.get("content-type") ?? "application/json",
      },
    });
  } catch {
    return NextResponse.json({ detail: "Campagne indisponible." }, { status: 502 });
  }
}
