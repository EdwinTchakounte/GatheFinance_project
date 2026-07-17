export type Campaign = {
  id: number;
  nom: string;
  profil_cible: string;
  date_fin: string;
  montant_min: string;
  montant_max: string;
  taux_interet: string;
  nb_jours_recouvrement: number;
  flyer_url: string;
  frais_etude_montant?: string | null;
  documents_requis?: string[];
  is_open?: boolean;
};

export function fmtXAF(v: string): string {
  const n = Number(v);
  return Number.isFinite(n) ? n.toLocaleString("fr-FR") + " XAF" : v;
}

export function fmtDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString("fr-FR", {
      day: "2-digit",
      month: "short",
      year: "numeric",
    });
  } catch {
    return iso;
  }
}
