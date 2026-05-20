import createMiddleware from "next-intl/middleware";
import { routing } from "@/i18n/routing";

export default createMiddleware(routing);

// Le middleware ne touche pas aux routes API (proxifiées vers Django) ni aux
// assets internes Next.js.
export const config = {
  matcher: ["/((?!api|_next|_vercel|.*\\..*).*)"],
};
