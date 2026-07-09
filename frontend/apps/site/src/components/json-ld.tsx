import { siteConfig } from "@/lib/site-config";

/** Renders a JSON-LD <script> tag. */
export function JsonLd({ data }: { data: object | object[] }) {
  return (
    <script
      type="application/ld+json"
      // JSON.stringify output is safe to inline in a script element.
      dangerouslySetInnerHTML={{ __html: JSON.stringify(data).replace(/</g, "\\u003c") }}
    />
  );
}

/** Site-wide Organization / FinancialService structured data. */
export function organizationJsonLd(siteUrl: string) {
  return {
    "@context": "https://schema.org",
    "@type": "FinancialService",
    name: siteConfig.name,
    alternateName: "GATHE Finance — Coopérative d'épargne et de crédit",
    url: siteUrl,
    logo: `${siteUrl}/icon.svg`,
    image: `${siteUrl}/opengraph-image`,
    description:
      "Coopérative d'épargne et de crédit des entrepreneurs camerounais : crédit, épargne, transferts, investissement communautaire et éducation financière.",
    email: siteConfig.contact.email,
    telephone: siteConfig.contact.phone,
    address: {
      "@type": "PostalAddress",
      streetAddress: "Rue Mermoz, Akwa",
      addressLocality: "Douala",
      addressCountry: "CM",
    },
    areaServed: "CM",
    openingHoursSpecification: [
      {
        "@type": "OpeningHoursSpecification",
        dayOfWeek: ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
        opens: "08:00",
        closes: "17:00",
      },
    ],
    sameAs: [siteConfig.social.facebook, siteConfig.social.linkedin],
  };
}

export function websiteJsonLd(siteUrl: string) {
  return {
    "@context": "https://schema.org",
    "@type": "WebSite",
    name: siteConfig.name,
    url: siteUrl,
    inLanguage: ["fr", "en"],
  };
}

export function articleJsonLd(opts: {
  siteUrl: string;
  url: string;
  title: string;
  description: string;
  datePublished: string;
  author: string;
  image?: string | null;
}) {
  return {
    "@context": "https://schema.org",
    "@type": "Article",
    headline: opts.title,
    description: opts.description,
    datePublished: opts.datePublished,
    author: { "@type": "Organization", name: opts.author || "GATHE Finance" },
    publisher: {
      "@type": "Organization",
      name: siteConfig.name,
      logo: { "@type": "ImageObject", url: `${opts.siteUrl}/icon.svg` },
    },
    image: opts.image ?? `${opts.siteUrl}/opengraph-image`,
    mainEntityOfPage: opts.url,
    inLanguage: "fr",
  };
}

export function breadcrumbJsonLd(siteUrl: string, items: { name: string; path: string }[]) {
  return {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: items.map((it, i) => ({
      "@type": "ListItem",
      position: i + 1,
      name: it.name,
      item: `${siteUrl}${it.path}`,
    })),
  };
}
