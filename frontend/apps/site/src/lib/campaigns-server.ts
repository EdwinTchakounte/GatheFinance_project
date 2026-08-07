import type { Campaign } from "@/lib/campaign-format";

/**
 * Fetch serveur (RSC/ISR) des campagnes micro-crédit ouvertes — rendu dans le
 * HTML initial pour un affichage immédiat (fini le pop-in du fetch client).
 * ISR court (60 s) : une campagne nouvellement ouverte apparaît sans que le
 * visiteur ait à réactualiser. Dégrade proprement en `[]` si le backend est
 * injoignable au moment de la (re)génération.
 */
const BACKEND = (process.env.CMS_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

export async function getActiveCampaigns(limit = 50): Promise<Campaign[]> {
  try {
    const res = await fetch(
      `${BACKEND}/api/v1/loans/campaigns/active/?limit=${limit}`,
      {
        next: { revalidate: 60, tags: ["campaigns"] },
        headers: { Accept: "application/json" },
      },
    );
    if (!res.ok) return [];
    const data = (await res.json()) as { results?: Campaign[] };
    return Array.isArray(data?.results) ? data.results : [];
  } catch {
    return [];
  }
}
