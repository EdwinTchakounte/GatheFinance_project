# Plan de tests en live — couverture globale (2026-07-28)

Objectif : exercer **en live sur la prod** tous les flows métier, sur le compte de test **Edwin (GF-2026-0003)**, avec écritures réelles.

> Rappel : on écrit dans la vraie base prod. On reste sur le compte Edwin, on ne touche pas aux autres membres.

---

## 0. Deux verrous à débloquer AVANT de continuer

### Verrou 1 — dialogue Chrome (bloque le retrait en cours)
Une confirmation « Confirmer remise espèces » (ou un prompt de permission de l'extension) fige l'automation. Dans la fenêtre Chrome : fermer/valider la pop-up, puis reprendre.

### Verrou 2 — nettoyer GF-CR-2026-0005 (rend Edwin inéligible → bloque tout cycle crédit neuf)
0005 est un record corrompu (non décaissé + clôturé par sa reconduction 0006, elle-même déjà remboursée). Mon garde-fou le compte comme « en cours » → Edwin ne peut pas demander de crédit.

> ⚠️ **Le prompt `root@vmi3289409:~#` = l'HÔTE (VPS), PAS le conteneur.** Sur l'hôte,
> `manage.py` est introuvable et `python` n'existe pas. Il faut d'abord ENTRER dans
> le conteneur (prompt attendu : `root@…:/app#`), où `python` existe et `manage.py`
> est dans `/app`.

**Étape 1 — entrer dans le conteneur :**
```bash
docker exec -it gathe-finance-prod-backend-1 bash
```

**Étape 2 — une fois le prompt `root@…:/app#` affiché, lancer (`python`, pas `python3`) :**

```bash
python manage.py shell -c "
from apps_coop.loans.models import Loan
l = Loan.objects.get(numero_dossier='GF-CR-2026-0005')
print('AVANT:', l.statut, '| en_attente_decaissement =', l.en_attente_decaissement, '| solde =', l.solde_restant)
l.en_attente_decaissement = False
l.save(update_fields=['en_attente_decaissement'])
l.refresh_from_db()
print('APRES:', l.statut, '| en_attente_decaissement =', l.en_attente_decaissement)
print('Edwin bloque ?', Loan.objects.filter(member=l.member).filter(en_attente_decaissement=True).exists())
"
```

Effet : 0005 devient un crédit clôturé normal (obligation déjà soldée via 0006) → Edwin redevient éligible.

---

## 1. Matrice de couverture des flows

| Flow | Code (tests) | Live prod | À faire |
|---|---|---|---|
| Vitrine publique | — | ✅ | fait |
| Admin / dashboard | — | ✅ | fait |
| **Épargne** — dépôt libre manuel | ✅ | ✅ (24 000 → 29 000) | fait |
| **Retrait** — débit au paiement | ✅ | ⏳ bloqué (verrou 1) | confirmer remise → débit 29 000 → 28 000 |
| **Crédit — remboursement + clôture** | ✅ | ✅ (cross-canal) | fait |
| **Crédit — reconduction (unique/à terme)** | ✅ | ✅ (garde-fou mobile) | fait |
| **Crédit — garde-fous** (non décaissé, 1-crédit, gel borné + déficit) | ✅ | ✅ (0005 gel=0 en prod) | fait |
| **Crédit — cycle NEUF complet** (demande → validation → **décaissement manuel réel** → remb → clôture) | ✅ | ❌ | **après verrou 2** — le vrai trou |
| **Crédit — 5 voies** (senior_brc, avaliste, garantie, campagne, apport) | ✅ | ⚠️ avaliste observée | rejouer senior_brc/apport, avaliste, campagne |
| **Crédit — apport rejet auto** (cagnotte < 10 %) | ✅ | ❌ | demande > cagnotte×10 → rejet auto en direct |
| **Collecte** (cotisation + destination fin de mois) | ✅ | ⚠️ mobile lecture | à jouer |
| **Adhésion** complète (vitrine → approbation → 3 frais → actif) | ✅ | ❌ | optionnel (crée un membre) |
| **Funding prêteur** (pool) | ✅ | ❌ (non live-able simplement) | tests only |
| **Contentieux** (retard → pénalité → saisie → judiciaire) | ✅ | ❌ (nécessite backdating + crons) | tests only |

Légende : ✅ fait · ⏳ en cours/bloqué · ⚠️ partiel · ❌ pas encore

---

## 2. Ordre d'exécution (après les 2 verrous)

1. **Retrait** — confirmer remise espèces → vérifier débit (29 000 → 28 000) + réservation nette.
2. **Cycle crédit NEUF** (le trou principal) :
   - nouvelle demande côté **mobile** (une voie),
   - **validation comité** côté admin,
   - **décaissement manuel réel** (« Payer maintenant » / versement décaissement),
   - **remboursement** manuel,
   - **clôture**.
   Idéalement rejoué sur **2-3 voies** : senior_brc/apport, avaliste, campagne.
3. **Apport rejet auto** — demande dont l'apport requis (10 %) dépasse la cagnotte → rejet automatique en direct.
4. **Collecte** — cotisation + choix destination fin de mois.
5. (optionnel) **Adhésion** complète — crée un membre de test « TEST ».

---

## 3. Actions qui restent côté toi (je ne peux pas les faire)
- Saisir identifiants / **PIN mobile** (sécurité).
- Fermer les **dialogues de confirmation** Chrome quand ils figent l'automation.
- Lancer les **commandes shell** (nettoyage 0005, éventuels contrôles).
- Décision de créer/supprimer un **membre de test** pour l'adhésion.

## 4. Rappels environnement
- Freeze récurrent des pages admin **Crédits / Retraits** sous automation → passer par **Paiements → « Saisir versement agence »** (stable) quand possible.
- Nom « Edwin Edwin tchako » sur la page Retraits = donnée Edwin polluée (nom = « Edwin tchako ») ; se corrige en nettoyant la donnée. Optionnel :
  ```bash
  python manage.py shell -c "
  from apps_coop.members.models import Member
  m = Member.objects.get(numero_membre='GF-2026-0003')
  print('avant:', repr(m.prenom), repr(m.nom))
  if m.nom.lower().startswith(m.prenom.lower()):
      m.nom = m.nom[len(m.prenom):].strip() or m.nom
      m.save(update_fields=['nom'])
  print('apres:', repr(m.prenom), repr(m.nom))
  "
  ```
