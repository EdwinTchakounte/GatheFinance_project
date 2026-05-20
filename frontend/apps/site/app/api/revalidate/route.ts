import { revalidatePath, revalidateTag } from "next/cache";
import { NextResponse, type NextRequest } from "next/server";

/**
 * On-demand ISR revalidation webhook, called by the Wagtail backend when content
 * is published/unpublished (see backend/apps/cms/signals.py). Authenticated with
 * the shared REVALIDATE_SECRET. Body: { "paths": ["/", "/blog", "/en/blog", ...] }.
 */
export async function POST(req: NextRequest) {
  const secret = req.headers.get("x-revalidate-secret");
  if (!process.env.REVALIDATE_SECRET || secret !== process.env.REVALIDATE_SECRET) {
    return NextResponse.json({ ok: false, error: "unauthorized" }, { status: 401 });
  }

  let paths: string[] = [];
  try {
    const body = (await req.json()) as { paths?: unknown };
    if (Array.isArray(body?.paths)) paths = body.paths.filter((p): p is string => typeof p === "string");
  } catch {
    // ignore malformed bodies — fall through to a tag-only revalidation
  }

  // Everything that reads the CMS is tagged "cms"; this covers all dependent routes.
  revalidateTag("cms");
  for (const p of paths) {
    try {
      revalidatePath(p);
    } catch {
      // ignore unknown paths
    }
  }

  return NextResponse.json({ ok: true, revalidated: paths });
}
