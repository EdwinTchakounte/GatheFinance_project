import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Gathe Finance — Coopérative d'épargne et de crédit",
    short_name: "Gathe Finance",
    description:
      "Coopérative d'épargne et de crédit des entrepreneurs camerounais : crédit, épargne, transferts, investissement communautaire et éducation financière.",
    start_url: "/?source=pwa",
    scope: "/",
    display: "standalone",
    orientation: "portrait-primary",
    background_color: "#ffffff",
    theme_color: "#0e4d92",
    lang: "fr",
    categories: ["finance", "business"],
    icons: [
      { src: "/icon.svg", sizes: "any", type: "image/svg+xml", purpose: "any" },
      { src: "/icon-maskable.svg", sizes: "any", type: "image/svg+xml", purpose: "maskable" },
    ],
    shortcuts: [
      { name: "Devenir membre", url: "/devenir-membre" },
      { name: "Services financiers", url: "/services-financiers" },
      { name: "Contact", url: "/contact" },
    ],
  };
}
