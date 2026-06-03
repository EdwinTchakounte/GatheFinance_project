/**
 * Static site configuration (links, default coordinates).
 *
 * The coordinates here are the verbatim values of the existing site and act as
 * the fallback; in the integrated build they come from the Wagtail
 * `SiteSettings` singleton (see src/lib/wagtail.ts → getSiteSettings()).
 */
export const siteConfig = {
  name: "Gathe Finance",
  url: process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000",
  contact: {
    address: "Rue Mermoz, Akwa, Douala, Cameroun",
    phone: "+237 6 56 13 06 72",
    phoneHref: "tel:+237656130672",
    landline: "233 42 48 47",
    email: "contact@gathe-finance.com",
    emailHref: "mailto:contact@gathe-finance.com",
    openingHours: "Lundi – Vendredi : 8h00 à 17h",
    whatsapp: "237656130672",
  },
  social: {
    facebook: "https://www.facebook.com/Gathe237",
    linkedin: "https://www.linkedin.com/company/gathe237/",
  },
  brc: { name: "Broad Range Consulting Group", url: "https://www.cga-brcgroup.com/" },
} as const;

/** Photos of the existing site + BRC group library (sourced from
 *  cga-brcgroup.com — the parent company), served from /public/images/. */
export const images = {
  entrepreneurs: "/images/entrepreneurs.jpg",
  family: "/images/family.jpg",
  businesswoman: "/images/businesswoman.jpg",
  entrepreneurFamily: "/images/entrepreneur-family.jpg",
  fcfaBills: "/images/cemac-bills-2022.jpg",
  fatherDaughterSaving: "/images/father-daughter-saving.jpg",
  cooperativeInvestment: "/images/cooperative-investment.jpg",
  trainingWorkshop: "/images/training-workshop.jpg",
  onlineSupport: "/images/online-support.jpg",
  // BRC group library — entrepreneurs and consulting context, Cameroon
  brcBusinessFormation: "/images/brc-business-formation.webp",
  brcTeamEnterprise: "/images/brc-team-enterprise.jpg",
  brcFormFilling: "/images/brc-form-filling.jpg",
  brcTeamSupport: "/images/brc-team-support.webp",
  brcCompletion: "/images/brc-completion.webp",
  brcTeamGroup: "/images/brc-team-group.webp",
} as const;

/** People shown on the floating cards of the hero photo (from the original site). */
export const heroPeople = [
  { name: "Carole Biteck", role: "Commerçante" },
  { name: "Franck Tchaleu", role: "Entrepreneur" },
] as const;

/** Fallback cover image per blog slug (until the editor uploads one in the CMS). */
const blogImageMap: Record<string, string> = {
  "les-avantages-du-credit-pour-booster-le-developpement-de-votre-pme": "/images/blog-pme.jpg",
  "pret-immobilier-comment-acceder-a-votre-propriete-en-toute-serenite": "/images/blog-property.jpg",
  "comment-planifier-leducation-de-vos-enfants-grace-a-la-caisse-scolaire": "/images/blog-school.jpg",
};
export function blogFallbackImage(slug: string): string | null {
  return blogImageMap[slug] ?? null;
}

/** Top-level navigation with submenus (mirrors the original gathe-finance.com nav).
 *  `href` values are passed to next-intl's locale-aware <Link>; `descKey` (optional)
 *  is a short i18n key shown under the submenu item. */
export type NavChild = { key: string; href: string; descKey?: string };
export type NavItem = { key: string; href: string; children?: readonly NavChild[] };

export const mainNav: readonly NavItem[] = [
  { key: "home", href: "/" },
  {
    key: "about",
    href: "/a-propos",
    children: [
      { key: "aboutMission", href: "/a-propos#mission" },
      { key: "aboutTeam", href: "/a-propos#equipe" },
      { key: "aboutAgencies", href: "/a-propos#agences" },
    ],
  },
  {
    key: "services",
    href: "/services-financiers",
    children: [
      { key: "servicesCredit", href: "/services-financiers#credit", descKey: "servicesCreditDesc" },
      { key: "servicesTransfers", href: "/services-financiers#transferts", descKey: "servicesTransfersDesc" },
      { key: "servicesSavings", href: "/services-financiers#epargne", descKey: "servicesSavingsDesc" },
      { key: "servicesInvestment", href: "/services-financiers#investissement", descKey: "servicesInvestmentDesc" },
      { key: "servicesEducation", href: "/services-financiers#education", descKey: "servicesEducationDesc" },
    ],
  },
  { key: "blog", href: "/blog" },
  { key: "contact", href: "/contact" },
];

export const serviceAnchors = [
  { key: "servicesCredit", href: "/services-financiers#credit" },
  { key: "servicesTransfers", href: "/services-financiers#transferts" },
  { key: "servicesSavings", href: "/services-financiers#epargne" },
  { key: "servicesInvestment", href: "/services-financiers#investissement" },
  { key: "servicesEducation", href: "/services-financiers#education" },
] as const;

/** Homepage "services" overview — the 5 pillars of the existing site with their photo. */
export const servicePillars = [
  { key: "credit", labelKey: "servicesCredit", anchor: "credit", image: images.fcfaBills, alt: "Billets de FCFA", items: ["consumption", "micro", "realEstate", "personal"] },
  { key: "transfers", labelKey: "servicesTransfers", anchor: "transferts", image: images.onlineSupport, alt: "Support en ligne Gathe Finance", items: ["sendReceive", "deposit"] },
  { key: "savings", labelKey: "servicesSavings", anchor: "epargne", image: images.fatherDaughterSaving, alt: "Père et sa fille qui épargnent", items: ["accounts", "plans"] },
  { key: "investment", labelKey: "servicesInvestment", anchor: "investissement", image: images.cooperativeInvestment, alt: "Investissement en coopérative", items: ["community", "secured"] },
  { key: "education", labelKey: "servicesEducation", anchor: "education", image: images.trainingWorkshop, alt: "Atelier de formation de Gathe Finance", items: ["workshops", "advice"] },
] as const;
