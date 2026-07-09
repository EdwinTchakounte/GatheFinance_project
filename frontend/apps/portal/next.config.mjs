import createNextIntlPlugin from "next-intl/plugin";

const withNextIntl = createNextIntlPlugin("./src/i18n/request.ts");

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  transpilePackages: ["@gathe/ui", "@gathe/config"],
  // Django requires trailing slashes — pin them when proxying.
  skipTrailingSlashRedirect: true,
  async rewrites() {
    // `gathe-backend` = alias unique posé par infra/docker-compose.nginx-external.yml.
    // Evite la collision avec un autre `backend` sur le reseau Docker mutualise
    // du VPS (ex. afrikamode, edlearning) qui provoquait des 400 aleatoires
    // en round-robin DNS.
    const backend = process.env.BACKEND_INTERNAL_URL ?? "http://gathe-backend:8000";
    return [
      { source: "/api/v1/:path+", destination: `${backend}/api/v1/:path+/` },
      { source: "/api/v1", destination: `${backend}/api/v1/` },
      // Wagtail read API v2 (fil d'actualités membre).
      { source: "/api/v2/:path+", destination: `${backend}/api/v2/:path+/` },
      { source: "/api/v2", destination: `${backend}/api/v2/` },
    ];
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
          // Sociétaire-only surface — keep search engines out.
          { key: "X-Robots-Tag", value: "noindex, nofollow" },
        ],
      },
    ];
  },
};

export default withNextIntl(nextConfig);
