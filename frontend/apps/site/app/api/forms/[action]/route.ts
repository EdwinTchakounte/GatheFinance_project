import { NextResponse, type NextRequest } from "next/server";

/**
 * Same-origin proxy for the public form endpoints, forwarding to the Django/DRF
 * backend (`/api/forms/...`). Keeps the browser talking to its own origin (no
 * CORS, no public backend URL needed) while still passing the client IP along
 * for the backend's anti-spam / rate-limiting.
 *
 *   GET  /api/forms/captcha     -> backend GET  /api/forms/captcha/
 *   POST /api/forms/contact     -> backend POST /api/forms/contact/
 *   POST /api/forms/adhesion    -> backend POST /api/forms/adhesion/
 *   POST /api/forms/newsletter  -> backend POST /api/forms/newsletter/
 */
const BACKEND = (process.env.CMS_API_URL ?? "http://localhost:8000").replace(/\/$/, "");
const ALLOWED = new Set(["captcha", "contact", "adhesion", "newsletter"]);

function clientIp(req: NextRequest): string | null {
  const xff = req.headers.get("x-forwarded-for");
  if (xff) return xff.split(",")[0]!.trim();
  return req.headers.get("x-real-ip");
}

async function forward(req: NextRequest, action: string, method: "GET" | "POST") {
  if (!ALLOWED.has(action)) {
    return NextResponse.json({ ok: false, error: "unknown form" }, { status: 404 });
  }
  const ip = clientIp(req);
  const headers: Record<string, string> = { Accept: "application/json" };
  if (ip) {
    headers["X-Forwarded-For"] = ip;
    headers["X-Real-IP"] = ip;
  }
  let body: BodyInit | undefined;
  if (method === "POST") {
    // Adhésion = multipart (uploads CNI/plan/photo). Le reste (contact,
    // newsletter) reste JSON. On reflète le Content-Type entrant côté backend.
    const incomingCT = req.headers.get("content-type") ?? "";
    if (incomingCT.toLowerCase().startsWith("multipart/form-data")) {
      // Préserver le boundary du multipart : on relaie le header brut tel quel.
      headers["Content-Type"] = incomingCT;
      const buf = await req.arrayBuffer();
      body = buf;
    } else {
      headers["Content-Type"] = "application/json";
      body = await req.text();
    }
  }
  try {
    const res = await fetch(`${BACKEND}/api/forms/${action}/`, { method, headers, body, cache: "no-store" });
    const text = await res.text();
    return new NextResponse(text, {
      status: res.status,
      headers: { "Content-Type": res.headers.get("content-type") ?? "application/json" },
    });
  } catch {
    return NextResponse.json({ ok: false, error: "backend unreachable" }, { status: 502 });
  }
}

export async function GET(req: NextRequest, ctx: { params: Promise<{ action: string }> }) {
  const { action } = await ctx.params;
  return forward(req, action, "GET");
}

export async function POST(req: NextRequest, ctx: { params: Promise<{ action: string }> }) {
  const { action } = await ctx.params;
  return forward(req, action, "POST");
}
