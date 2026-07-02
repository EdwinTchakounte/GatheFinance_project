import { NextResponse, type NextRequest } from "next/server";

/**
 * Proxy same-origin → backend DRF : candidature publique d'un visiteur à une
 * campagne micro-crédit (``membre_requis=False``). Relaie l'IP client pour
 * l'anti-spam backend. Le body inclut ``campaign_id`` + identité + montant.
 *   POST /api/campaigns/apply -> backend POST /api/v1/loans/campaigns/<id>/apply/
 */
const BACKEND = (process.env.CMS_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

function clientIp(req: NextRequest): string | null {
  const xff = req.headers.get("x-forwarded-for");
  if (xff) return xff.split(",")[0]!.trim();
  return req.headers.get("x-real-ip");
}

export async function POST(req: NextRequest) {
  let body: Record<string, unknown>;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ detail: "Corps JSON invalide." }, { status: 400 });
  }
  const id = body?.campaign_id;
  if (!id) {
    return NextResponse.json({ detail: "campaign_id requis." }, { status: 400 });
  }
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    Accept: "application/json",
  };
  const ip = clientIp(req);
  if (ip) {
    headers["X-Forwarded-For"] = ip;
    headers["X-Real-IP"] = ip;
  }
  try {
    const res = await fetch(`${BACKEND}/api/v1/loans/campaigns/${id}/apply/`, {
      method: "POST",
      headers,
      body: JSON.stringify(body),
      cache: "no-store",
    });
    const text = await res.text();
    return new NextResponse(text, {
      status: res.status,
      headers: { "Content-Type": res.headers.get("content-type") ?? "application/json" },
    });
  } catch {
    return NextResponse.json({ detail: "Backend injoignable." }, { status: 502 });
  }
}
