/**
 * Pastille de statut unique pour tout le back-office.
 *
 * Deux problèmes qu'elle résout :
 *
 * 1. **Longueur** — les libellés côté serveur sont des phrases
 *    (« En attente (frais à payer) », « En attente de réponse de
 *    l'avaliste »…). Dans une colonne de tableau ça déborde, ça coupe et ça
 *    déséquilibre la ligne. On mappe donc chaque code métier vers un libellé
 *    court ; le libellé long reste en `title` (survol) pour ne rien perdre.
 *
 * 2. **Cohérence visuelle** — chaque page choisissait ses propres classes
 *    (`bg-emerald-100`, `bg-ink-100`, `pill pill-success`…). Ici une seule
 *    échelle de tons douce : point coloré + fond très léger, jamais de bloc
 *    saturé.
 */

export type StatusTone =
  | "neutral"
  | "wait"
  | "progress"
  | "success"
  | "danger";

/** Libellés courts par code métier. Clé = `statut` renvoyé par l'API. */
const SHORT_LABELS: Record<string, string> = {
  // Demandes de crédit
  en_attente: "Frais à payer",
  en_attente_avaliste: "Avaliste sollicité",
  attente_frais: "Avaliste désigné",
  en_validation_campagne: "Validation campagne",
  en_attente_funding: "Financement",
  en_instruction: "En instruction",
  approuvee_provisoire: "Accord provisoire",
  approuvee: "Approuvée",
  rejetee: "Rejetée",
  annulee: "Annulée",

  // Mandats d'avaliste
  pending: "À répondre",
  accepted: "Acceptée",
  refused: "Refusée",

  // Adhésions / justificatifs
  approuvee_adhesion: "Approuvée",
  rejetee_adhesion: "Rejetée",
  valide: "Validé",
  rejete: "Rejeté",

  // Membres
  actif: "Actif",
  suspendu: "Suspendu",
  radie: "Radié",

  // Crédits en cours
  en_cours: "En cours",
  solde: "Soldé",
  en_retard: "En retard",
  contentieux: "Contentieux",
};

/** Ton par code métier. Défaut = neutre. */
const TONES: Record<string, StatusTone> = {
  en_attente: "wait",
  attente_frais: "wait",
  en_attente_avaliste: "wait",
  en_validation_campagne: "wait",
  en_attente_funding: "wait",
  pending: "wait",
  suspendu: "wait",
  en_retard: "wait",

  en_instruction: "progress",
  approuvee_provisoire: "progress",
  en_cours: "progress",

  approuvee: "success",
  approuvee_adhesion: "success",
  accepted: "success",
  valide: "success",
  actif: "success",
  solde: "success",

  rejetee: "danger",
  rejetee_adhesion: "danger",
  refused: "danger",
  rejete: "danger",
  radie: "danger",
  contentieux: "danger",
  annulee: "neutral",
};

const TONE_CLASSES: Record<StatusTone, string> = {
  neutral: "bg-line-100/70 text-ink-600",
  wait: "bg-amber-500/10 text-amber-800",
  progress: "bg-blue-700/10 text-blue-800",
  success: "bg-emerald-600/10 text-emerald-800",
  danger: "bg-red-600/10 text-red-700",
};

const DOT_CLASSES: Record<StatusTone, string> = {
  neutral: "bg-ink-400",
  wait: "bg-amber-500",
  progress: "bg-blue-700",
  success: "bg-emerald-600",
  danger: "bg-red-600",
};

export function shortStatusLabel(statut: string, fallback?: string): string {
  return SHORT_LABELS[statut] ?? fallback ?? statut;
}

export function statusTone(statut: string): StatusTone {
  return TONES[statut] ?? "neutral";
}

export function StatusPill({
  statut,
  label,
  tone,
  className = "",
}: {
  /** Code métier renvoyé par l'API (`en_attente`, `accepted`…). */
  statut: string;
  /** Libellé long de l'API — sert de repli et de `title` au survol. */
  label?: string;
  /** Force un ton si le code n'est pas dans la table. */
  tone?: StatusTone;
  className?: string;
}) {
  const resolved = tone ?? statusTone(statut);
  const short = shortStatusLabel(statut, label);
  return (
    <span
      title={label && label !== short ? label : undefined}
      className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 py-1 text-[0.7rem] font-medium ${TONE_CLASSES[resolved]} ${className}`}
    >
      <span
        aria-hidden="true"
        className={`size-1.5 shrink-0 rounded-full ${DOT_CLASSES[resolved]}`}
      />
      {short}
    </span>
  );
}
