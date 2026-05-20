/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  transpilePackages: ["@gathe/ui", "@gathe/config"],
  // Django requires trailing slashes — pin them when proxying.
  skipTrailingSlashRedirect: true,
  async rewrites() {
    const backend = process.env.BACKEND_INTERNAL_URL ?? "http://backend:8000";
    return [
      { source: "/api/v1/:path+", destination: `${backend}/api/v1/:path+/` },
      { source: "/api/v1", destination: `${backend}/api/v1/` },
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
          // Admin = sensible — discourage indexation.
          { key: "X-Robots-Tag", value: "noindex, nofollow" },
        ],
      },
    ];
  },
};

export default nextConfig;
