import { NextResponse, type NextRequest } from "next/server";

/**
 * CH-4 — Same-origin proxy pour récupérer le FormSchema actif d'un kind.
 *
 *   GET /api/forms/schema/adhesion -> backend GET /api/v1/forms/schemas/adhesion/active/
 */
const BACKEND = (process.env.CMS_API_URL ?? "http://localhost:8000").replace(/\/$/, "");
const ALLOWED_KINDS = new Set(["adhesion", "loan_request", "loan_renewal"]);

export async function GET(
  _req: NextRequest,
  ctx: { params: Promise<{ kind: string }> },
) {
  const { kind } = await ctx.params;
  if (!ALLOWED_KINDS.has(kind)) {
    return NextResponse.json({ detail: "unknown kind" }, { status: 404 });
  }
  try {
    const res = await fetch(
      `${BACKEND}/api/v1/forms/schemas/${kind}/active/`,
      { cache: "no-store", headers: { Accept: "application/json" } },
    );
    const text = await res.text();
    return new NextResponse(text, {
      status: res.status,
      headers: {
        "Content-Type": res.headers.get("content-type") ?? "application/json",
      },
    });
  } catch {
    return NextResponse.json(
      { detail: "backend unreachable" },
      { status: 502 },
    );
  }
}
