# Inspection — refus de transfert vers un crédit (apport gelé / épargne)

## Ce qu'on a découvert

Le message mobile « **Nos serveurs rencontrent un souci** » sur le transfert de
l'apport gelé n'était **pas un vrai 500**. Les logs backend montrent un **400
Bad Request** :

```
django.request Bad Request: /api/v1/loans/me/loans/26/repay-from-frozen/
```

→ Le backend **refuse proprement** (règle métier), mais le mobile affichait un
message générique « souci serveur » au lieu du vrai motif.

**Corrigé côté mobile** (commit `5467e81`) : le transfert affiche désormais le
**vrai message** du refus. Un rebuild APK est nécessaire pour le voir sur le
device.

Il reste à confirmer **pourquoi** un crédit donné refuse le transfert : garde-fou
normal, ou anomalie de données. La commande ci-dessous le dit — **sans rien
modifier** (lecture seule, elle n'exécute pas le transfert).

---

## Commande d'inspection (lecture seule)

Sur le serveur (`/opt/gathe-finance`), remplacer `26` par l'ID du crédit visé :

```bash
docker compose -f infra/docker-compose.prod.yml exec -T backend python manage.py shell -c "
from decimal import Decimal
from apps_coop.loans.models import Loan
from apps_coop.loans.transfer_services import available_for_transfer
l = Loan.objects.get(pk=26)
lr = getattr(l,'loan_request',None)
frozen = Decimal(getattr(lr,'montant_gele_demandeur',0) or 0) if lr else Decimal('0')
print('dossier=', l.numero_dossier, '| membre=', l.member.numero_membre)
print('statut=', l.statut, '| en_attente_decaissement=', l.en_attente_decaissement)
print('solde_restant=', l.solde_restant)
print('apport_gele=', frozen)
print('dispo_transfert=', available_for_transfer(l.member))
"
```

> `-T` = pas de TTY (nécessaire pour `exec … -c`). Les avertissements
> `WARN … variable is not set` sont normaux et sans effet ici.

---

## Interprétation du résultat

Le service `repay_loan_from_frozen` refuse (400) dans ces cas — et voici le
message que le membre verra **désormais** (après rebuild APK) :

| État constaté | Refus (400) — message affiché au membre | Normal ? |
|---|---|---|
| `statut` ∉ {ACTIF, EN_RETARD} (ex. CLOTURE, CONTENTIEUX) | « Ce crédit n'est pas remboursable (déjà clôturé ?). » | ✅ garde-fou |
| `en_attente_decaissement = True` | « Ce crédit n'a pas encore été décaissé… remboursement impossible tant que la mise à disposition n'a pas eu lieu. » | ✅ garde-fou |
| `apport_gele = 0` | « Aucun apport gelé n'est disponible pour ce crédit. » | ✅ garde-fou |
| `solde_restant ≤ 0` | « Ce crédit est déjà soldé. » | ✅ garde-fou |
| `apport_gele > 0` **mais** solde classique < apport | « Épargne classique introuvable ou insuffisante pour transférer l'apport gelé. » | ⚠️ à examiner |

### Cas ⚠️ « apport gelé > 0 mais épargne insuffisante »
Signifie que l'UI propose un apport gelé (`apportGele > 0`) alors que le solde
classique réel ne le couvre pas (gel désynchronisé du solde). Si tu tombes sur
ce cas, envoie-moi la sortie : c'est un correctif backend (borner l'apport gelé
transférable au solde réel, comme le gel de garantie l'a déjà été).

---

## Rappel endpoints

| Action | Endpoint | Refus attendu |
|---|---|---|
| Transférer apport gelé → crédit | `POST /loans/me/loans/<id>/repay-from-frozen/` | 400 `TransferError` (voir table) |
| Transférer épargne → crédit | `POST /loans/me/loans/<id>/repay-from-savings/` | 400 `TransferError` |
| Écran Transfert (chargement) | `GET /loans/transfer/available/` | 200 |

Si un jour c'est un **vrai 500** (et non 400), repasser par
`docs/DIAG_TRANSFERT_APPORT_GELE_500.md` (capture de la stack trace).

---

## Cas résolu — GF-CR-2026-0026 (2026-08-04)

Sortie de la commande d'inspection :

```
dossier= GF-CR-2026-0026 | membre= GF-2026-0003
statut= actif | en_attente_decaissement= True
solde_restant= 18000.00
apport_gele= 20000.00
dispo_transfert= {'classic': 0, 'collecte': 1000.00, 'total': 1000.00}
```

**Diagnostic** : `en_attente_decaissement = True` → crédit approuvé **mais pas
encore décaissé**. Refus 400 **légitime** (« Ce crédit n'a pas encore été
décaissé… »). Ce n'était donc pas un bug serveur, juste un message mobile
trompeur (corrigé, commit `5467e81`).

**Action** : décaisser le crédit côté admin pour débloquer le cycle
(remboursement/transfert possibles une fois `en_attente_decaissement=False`).

> Note produit : un crédit `statut=actif` **et** `en_attente_decaissement=True`
> est un état transitoire normal (décaissement manuel, cf. décaissement=rôle
> admin). Amélioration UX possible : masquer/désactiver les actions
> « Rembourser » / « Transférer » tant que le crédit n'est pas décaissé, plutôt
> que de laisser le membre tenter puis lire le refus.

