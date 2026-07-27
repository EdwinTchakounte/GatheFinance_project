/// Formatage canonique du nom d'un membre — source unique de vérité côté mobile.
///
/// Le formulaire public d'adhésion ne collecte qu'UN champ `nom` (souvent le nom
/// complet, ex. « MBALLA Jean »), le `prenom` étant renseigné à part par l'admin.
/// Une concaténation naïve « $prenom $nom » duplique alors le prénom
/// (« Jean MBALLA Jean »). [nomComplet] dé-duplique : si `nom` contient déjà le
/// prénom, il est renvoyé tel quel ; sinon on compose « nom prénom » (ordre
/// canonique). Les salutations affichent le prénom seul, pas ce nom complet.
String nomComplet(String? prenom, String? nom) {
  final p = (prenom ?? '').trim();
  final n = (nom ?? '').trim();
  if (p.isEmpty) return n;
  if (n.isEmpty) return p;
  final words = n.toLowerCase().split(RegExp(r'\s+'));
  if (words.contains(p.toLowerCase())) return n;
  return '$n $p';
}
