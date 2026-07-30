import createNextIntlPlugin from "next-intl/plugin";

const withNextIntl = createNextIntlPlugin("./src/i18n/request.ts");

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  // Django requires trailing slashes on API paths (e.g. /api/v1/auth/csrf/).
  // Without this flag, Next would 308-redirect /api/v1/foo/ → /api/v1/foo,
  // breaking the rewrite to the backend.
  skipTrailingSlashRedirect: true,
  // Transpile the shared design-system packages (TS source, no build step).
  transpilePackages: ["@gathe/ui", "@gathe/config"],
  images: {
    formats: ["image/avif", "image/webp"],
    remotePatterns: [
      // Wagtail media (local, docker network, and the eventual production domains).
      { protocol: "http", hostname: "localhost", port: "8000" },
      { protocol: "http", hostname: "backend", port: "8000" },
      { protocol: "http", hostname: "backend", port: "8200" },
      { protocol: "https", hostname: "cms.gathe-finance.com" },
      { protocol: "https", hostname: "media.gathe-finance.com" },
      // Serveur CLIENTE (DMZ) : les médias/covers CMS sont servis depuis
      // cms./media./s3./api.gathe-finance.com selon la config MinIO/Wagtail.
      // Wildcard pour couvrir les 4 sans casser next/image (même classe de bug
      // que le fallback horus-lab plus bas).
      { protocol: "https", hostname: "**.gathe-finance.com" },
      // Production prod actuelle . Contabo VPS sur horus-lab.com.
      // Wildcard : couvre cms/media/api.* (les covers d'articles sont servies
      // depuis cms.gathe-finance.horus-lab.com = WAGTAILADMIN_BASE_URL) — sans
      // ça, next/image bloque l'image téléversée (seul le fallback Unsplash
      // passait) → « lecture » cassée sur la vitrine.
      { protocol: "https", hostname: "**.gathe-finance.horus-lab.com" },
      { protocol: "https", hostname: "api.gathe-finance.horus-lab.com" },
      { protocol: "https", hostname: "gathe-finance.horus-lab.com" },
      { protocol: "https", hostname: "*.backblazeb2.com" },
      // Unsplash fallback pour covers d'articles de demo
      { protocol: "https", hostname: "images.unsplash.com" },
      { protocol: "https", hostname: "source.unsplash.com" },
    ],
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "SAMEORIGIN" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
        ],
      },
    ];
  },
  // Le portail sociétaire a été extrait vers `apps/portal/` (sur son propre
  // port en dev). Le site marketing parle au backend uniquement via les
  // route handlers `/api/forms/*` (cf. app/api/forms/[action]/route.ts) ;
  // plus aucun rewrite `/api/v1` n'est nécessaire ici.
  // 301 redirects from the old WordPress URLs (preserve SEO).
  async redirects() {
    return [
      { source: "/a-propos-gathe-finance", destination: "/a-propos", permanent: true },
      { source: "/devenir-membre-gathe-finance", destination: "/devenir-membre", permanent: true },
      {
        source: "/les-avantages-du-credit-pour-booster-le-developpement-de-votre-pme",
        destination: "/blog/les-avantages-du-credit-pour-booster-le-developpement-de-votre-pme",
        permanent: true,
      },
      {
        source: "/pret-immobilier-comment-acceder-a-votre-propriete-en-toute-serenite",
        destination: "/blog/pret-immobilier-comment-acceder-a-votre-propriete-en-toute-serenite",
        permanent: true,
      },
      {
        source: "/comment-planifier-leducation-de-vos-enfants-grace-a-la-caisse-scolaire",
        destination: "/blog/comment-planifier-leducation-de-vos-enfants-grace-a-la-caisse-scolaire",
        permanent: true,
      },
    ];
  },
};

export default withNextIntl(nextConfig);
