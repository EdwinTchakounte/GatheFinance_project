/** Nom complet dé-dupliqué « nom prénom » — source unique.
 * Si `nom` contient déjà le prénom (formulaire public = nom complet), on le
 * renvoie tel quel ; sinon on compose « nom prénom ». Les salutations affichent
 * le prénom seul, pas ce nom complet. */
export function fullName(prenom?: string | null, nom?: string | null): string {
  const p = (prenom ?? "").trim();
  const n = (nom ?? "").trim();
  if (!p) return n;
  if (!n) return p;
  const words = n.toLowerCase().split(/\s+/);
  if (words.includes(p.toLowerCase())) return n;
  return `${n} ${p}`;
}
