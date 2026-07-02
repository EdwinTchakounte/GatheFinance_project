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
  const headers: Record<string, string> = { Accept: "application/json" };
  const ip = clientIp(req);
  if (ip) {
    headers["X-Forwarded-For"] = ip;
    headers["X-Real-IP"] = ip;
  }

  const incomingCT = (req.headers.get("content-type") ?? "").toLowerCase();
  let id: string | number | null = null;
  let body: BodyInit;

  if (incomingCT.startsWith("multipart/form-data")) {
    // Candidature avec pièces justificatives : on relaie le multipart brut
    // (boundary préservé). ``campaign_id`` est lu dans le FormData.
    headers["Content-Type"] = incomingCT;
    const buf = await req.arrayBuffer();
    // Extraire campaign_id sans consommer le body : reparse une copie.
    const form = await new Response(buf.slice(0), {
      headers: { "content-type": incomingCT },
    }).formData();
    id = (form.get("campaign_id") as string) || null;
    body = buf;
  } else {
    let json: Record<string, unknown>;
    try {
      json = await req.json();
    } catch {
      return NextResponse.json({ detail: "Corps invalide." }, { status: 400 });
    }
    id = (json?.campaign_id as string | number) ?? null;
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(json);
  }

  if (!id) {
    return NextResponse.json({ detail: "campaign_id requis." }, { status: 400 });
  }
  try {
    const res = await fetch(`${BACKEND}/api/v1/loans/campaigns/${id}/apply/`, {
      method: "POST",
      headers,
      body,
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
