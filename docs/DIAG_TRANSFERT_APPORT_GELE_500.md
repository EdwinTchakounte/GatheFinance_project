# Diagnostic — 500 « Nos serveurs rencontrent un souci » (transfert apport gelé & co)

Runbook pour capturer la **stack trace** d'une erreur 500 vue en live (mobile/portail)
sur **recette (horus)** ou **prod (cliente)**, puis me la transmettre pour correction.

Cas déclencheur principal : **membre → « Transférer mon apport gelé » pour rembourser un
crédit → 500**. La même méthode vaut pour n'importe quel 500 côté API.

> Rappel projet : sur le serveur, tout tourne en Docker Compose dans le dossier du projet
> (`/opt/gathe-finance` en prod). Service backend = **`backend`**. On ne fait JAMAIS
> `git pull` / `--build` ici : on lit seulement des logs.

---

## 0. Se connecter au serveur

```bash
ssh <utilisateur>@<hôte-horus-ou-prod>
cd /opt/gathe-finance        # dossier du projet (adapter si différent)
```

Repérer le conteneur backend (si le nom exact est inconnu) :

```bash
docker ps --format '{{.Names}}\t{{.Image}}\t{{.Status}}' | grep -i backend
```

---

## 1. Méthode rapide — reproduire puis lire la trace

1. Sur le serveur, vider l'écran puis suivre les logs backend en direct :

```bash
docker compose -f infra/docker-compose.prod.yml logs -f --tail=0 backend
```

2. **Sur le téléphone / portail**, refaire l'action qui échoue (transférer l'apport gelé).
3. Revenir au terminal : la **stack trace** s'affiche (lignes `Traceback (most recent call last)` …).
   `Ctrl-C` pour arrêter le suivi, puis copier tout le bloc.

---

## 2. Méthode « capture » — extraire la trace des dernières minutes

Si l'erreur vient d'avoir lieu :

```bash
# Dernières 10 minutes de logs backend → fichier
docker compose -f infra/docker-compose.prod.yml logs --since 10m backend > /tmp/gathe_backend.log 2>&1

# Extraire chaque traceback avec 60 lignes de contexte
grep -n -A60 -iE 'traceback|internal server error|unhandled' /tmp/gathe_backend.log
```

Ou directement les 200 dernières lignes :

```bash
docker compose -f infra/docker-compose.prod.yml logs --tail=200 backend 2>&1 | tail -150
```

---

## 3. Depuis TON poste, en une ligne (sortie ramenée ici)

Dans cette session Claude, tu peux préfixer par `!` pour que la sortie arrive directement :

```bash
! ssh <hôte-horus> 'cd /opt/gathe-finance && docker compose -f infra/docker-compose.prod.yml logs --tail=300 backend 2>&1 | grep -B3 -A60 -i traceback'
```

> Reproduis l'erreur sur le tél **juste avant** de lancer cette commande.

---

## 4. Inspecter l'état du compte (Django shell) — pourquoi CE compte plante

Utile pour un 500 qui ne se produit que sur un membre précis (état de données particulier) :

```bash
docker compose -f infra/docker-compose.prod.yml exec backend python manage.py shell
```

```python
from apps_coop.members.models import Member
from apps_coop.loans.models import Loan, LoanRequest
from apps_coop.loans.transfer_services import available_for_transfer

m = Member.objects.get(numero_membre="GF-2026-0003")      # adapter le n°

# Crédits du membre + éligibilité au transfert gelé
for l in Loan.objects.filter(member=m):
    lr = getattr(l, "loan_request", None)
    print(l.numero_dossier, l.statut,
          "décaissé?" , not l.en_attente_decaissement,
          "solde_restant=", l.solde_restant,
          "gelé=", getattr(lr, "montant_gele_demandeur", None))

# Argent mobilisable (le calcul qui alimente l'écran Transfert)
print(available_for_transfer(m))
```

Reproduire l'appel exact du transfert (déclenche la vraie exception dans le shell) :

```python
from apps_coop.loans.transfer_services import repay_loan_from_frozen
loan = Loan.objects.get(numero_dossier="GF-CR-2026-XXXX")  # le crédit visé
repay_loan_from_frozen(loan)        # → la stack trace s'affiche ICI si ça plante
```

---

## 5. Sentry (si activé)

`SENTRY_DSN` est câblé (`config/settings/prod.py`). S'il est renseigné en recette/prod, la
trace complète est déjà capturée : ouvre le projet dans **Sentry** → l'issue la plus récente
« Internal Server Error » sur `/api/v1/loans/me/loans/<id>/repay-from-frozen/ » → copie la
stack trace.

Vérifier s'il est actif :

```bash
docker compose -f infra/docker-compose.prod.yml exec backend printenv | grep -i sentry
```

---

## 6. Ce qu'il me faut (copier-coller ici)

- Le **bloc `Traceback …`** complet (§1, §2, §3 ou Sentry), **ou**
- La sortie du **§4** (état du compte + exception du shell).

Avec ça je corrige à la source, j'ajoute un test de non-régression, et je déploie
(staging → recette, puis main → prod).

---

## Endpoints concernés (pour info)

| Action mobile/portail | Endpoint API |
|---|---|
| Écran « Transfert » (chargement) | `GET /api/v1/loans/transfer/available/` |
| Transférer épargne → crédit | `POST /api/v1/loans/me/loans/<id>/repay-from-savings/` |
| **Transférer apport gelé → crédit** | `POST /api/v1/loans/me/loans/<id>/repay-from-frozen/` |
| Payer frais d'étude (MoMo) | `POST /api/v1/payments/init/` (`type=frais_demande_credit`) |
| Payer frais d'étude (épargne) | `POST /api/v1/loans/requests/<id>/study-fee/from-savings/` |
