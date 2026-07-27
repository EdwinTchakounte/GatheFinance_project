"""Formatage canonique du nom d'un membre — source unique de vérité.

Contexte : le formulaire public d'adhésion ne collecte QU'UN champ ``nom`` (qui
contient souvent le nom complet, ex. « MBALLA Jean » — convention nom de famille
en premier), et l'admin renseigne ``prenom`` séparément. Une concaténation naïve
``f"{prenom} {nom}"`` produit alors « Jean MBALLA Jean » (prénom dupliqué).

``full_name`` dé-duplique : si ``nom`` contient déjà le ``prenom`` (au niveau
d'un mot), il est renvoyé tel quel ; sinon on compose « nom prénom » (ordre
canonique retenu). Les SALUTATIONS n'utilisent pas cette fonction — elles
affichent le prénom seul (« Bonjour, Jean »).
"""
from __future__ import annotations


def full_name(prenom: str | None, nom: str | None) -> str:
    """Nom complet dé-dupliqué au format « nom prénom »."""
    prenom = (prenom or "").strip()
    nom = (nom or "").strip()
    if not prenom:
        return nom
    if not nom:
        return prenom
    # ``nom`` contient déjà le prénom (formulaire public = nom complet) → tel
    # quel, pour ne pas dupliquer ni mal réordonner un champ combiné.
    if prenom.lower() in {w.lower() for w in nom.split()}:
        return nom
    return f"{nom} {prenom}"
