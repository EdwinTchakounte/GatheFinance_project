# Créer un superuser (admin back-office) — GATHE Finance

Un « superuser » = compte staff avec accès complet au back-office
(`https://admin.<domaine>`). Toutes les commandes se lancent **sur le serveur**,
dans le dossier `infra/` du projet.

> **Contexte compose selon le serveur :**
> - **Cliente (prod, DMZ Traefik)** :
>   `docker compose -f docker-compose.prod.yml -f docker-compose.client.yml --env-file .env.prod`
> - **Recette (horus)** :
>   `docker compose -f docker-compose.prod.yml --env-file .env.prod`
>
> On note `COMPOSE` le préfixe correspondant dans la suite.

---

## Méthode 1 — Automatique au déploiement (déjà en place)

`docker-entrypoint.sh` crée le superuser **au démarrage** s'il n'existe pas, à
partir des variables du `.env.prod` :

```env
DJANGO_SUPERUSER_USERNAME=admin
DJANGO_SUPERUSER_EMAIL=admin@gathe-finance.com
DJANGO_SUPERUSER_PASSWORD=********      # mot de passe fort
```

→ Rien à faire : à chaque `up`, le compte est créé s'il manque.
⚠️ **Limite** : si le compte **existe déjà**, l'entrypoint **ne change PAS** le
mot de passe. Pour (re)définir le mot de passe → Méthode 3.

---

## Méthode 2 — Manuelle, non-interactive (création simple)

Sur le serveur, dans `infra/` :

```bash
cd /opt/gathe-finance/infra

# Cliente (prod)
docker compose -f docker-compose.prod.yml -f docker-compose.client.yml --env-file .env.prod \
  exec -T backend python manage.py createsuperuser --noinput \
  --username admin --email admin@gathe-finance.com
```

`createsuperuser --noinput` lit le mot de passe dans **`DJANGO_SUPERUSER_PASSWORD`**
(variable d'environnement du conteneur). Il **crée** le compte ; il ne met pas à
jour un compte existant.

---

## Méthode 3 — Créer OU mettre à jour le mot de passe (garantie)

À utiliser pour **garantir** que l'identifiant + mot de passe du `.env.prod`
fonctionnent, même si le compte existe déjà :

```bash
cd /opt/gathe-finance/infra

docker compose -f docker-compose.prod.yml -f docker-compose.client.yml --env-file .env.prod \
  exec -T backend python manage.py shell -c "
import os
from django.contrib.auth import get_user_model
U = get_user_model()
u, created = U.objects.get_or_create(
    username=os.environ['DJANGO_SUPERUSER_USERNAME'],
    defaults={'email': os.environ.get('DJANGO_SUPERUSER_EMAIL', '')},
)
u.is_staff = u.is_superuser = True
u.set_password(os.environ['DJANGO_SUPERUSER_PASSWORD'])
u.save()
print('superuser', 'créé' if created else 'mis à jour', ':', u.username)
"
```

---

## Méthode 4 — Interactive (saisie manuelle du mot de passe)

```bash
cd /opt/gathe-finance/infra

docker compose -f docker-compose.prod.yml -f docker-compose.client.yml --env-file .env.prod \
  exec backend python manage.py createsuperuser
```

(demande username / email / mot de passe à l'écran — pas de `-T`).

---

## Réinitialiser SEULEMENT le mot de passe d'un compte existant

```bash
cd /opt/gathe-finance/infra

docker compose -f docker-compose.prod.yml -f docker-compose.client.yml --env-file .env.prod \
  exec backend python manage.py changepassword admin
```

---

## Vérifier / lister les superusers

```bash
cd /opt/gathe-finance/infra

docker compose -f docker-compose.prod.yml -f docker-compose.client.yml --env-file .env.prod \
  exec -T backend python manage.py shell -c "
from django.contrib.auth import get_user_model
for u in get_user_model().objects.filter(is_superuser=True):
    print(u.username, '|', u.email, '| actif:', u.is_active)
"
```

Puis tester la connexion sur **`https://admin.gathe-finance.com`**.

---

### Notes
- Ne **jamais** committer le mot de passe : il vit dans `infra/.env.prod` (gitignoré).
- Sur **recette (horus)**, remplacer le préfixe compose par
  `docker compose -f docker-compose.prod.yml --env-file .env.prod` (sans `docker-compose.client.yml`).
