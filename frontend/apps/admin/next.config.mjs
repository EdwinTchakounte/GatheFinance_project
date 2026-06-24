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
      // Proxy des fichiers média (BRC, flyers campagne, règlement intérieur,
      // attestations, etc.). Sans ça, le serializer Django renvoie une URL
      // relative `/media/...` que le browser tente sur :3202 → 404.
      { source: "/media/:path*", destination: `${backend}/media/:path*` },
    ];
  },
  async headers() {
    return [
      {
        // SAMEORIGIN au lieu de DENY pour permettre les <iframe> de preview
        // PDF servies via le proxy /media (même origine que l'admin).
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "SAMEORIGIN" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          // Admin = sensible — discourage indexation.
          { key: "X-Robots-Tag", value: "noindex, nofollow" },
        ],
      },
    ];
  },
};

export default nextConfig;
