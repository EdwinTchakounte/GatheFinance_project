import type { Metadata } from "next";
import { setRequestLocale } from "next-intl/server";

import { Container } from "@gathe/ui";
import { PageHeader } from "@/components/page-shell";
import { CampaignsPublic } from "@/components/campaigns-public";
import { images } from "@/lib/site-config";
import { pageAlternates } from "@/lib/seo";

type Params = { params: Promise<{ locale: string }> };

export async function generateMetadata({ params }: Params): Promise<Metadata> {
  const { locale } = await params;
  return {
    title: "Campagnes micro-crédit",
    description:
      "Obtiens un micro-crédit via une campagne GATHE Finance — même sans être membre. Postule en ligne, sans frais d'adhésion.",
    alternates: pageAlternates(locale, "/campagnes"),
  };
}

export default async function CampagnesPage({ params }: Params) {
  const { locale } = await params;
  setRequestLocale(locale);

  return (
    <>
      <PageHeader
        eyebrow="Micro-crédit"
        title="Campagnes ouvertes"
        lead="Des campagnes ciblées permettent d'obtenir un micro-crédit — pour certaines, même sans être membre. Choisis une campagne, postule en ligne : si tu es accepté(e), ton compte est créé automatiquement, sans frais d'adhésion."
        homeLabel="Accueil"
        image={images.brcBusinessFormation}
      />

      <section className="section-pad bg-cream">
        <Container>
          <CampaignsPublic />
        </Container>
      </section>
    </>
  );
}
