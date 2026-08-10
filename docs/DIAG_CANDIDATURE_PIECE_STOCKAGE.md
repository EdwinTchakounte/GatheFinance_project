# DIAG — Candidature campagne avec pièce jointe échoue (400 générique)

> **Statut du diagnostic (2026-08-07)**
> Test live sur le serveur cliente (`*.gathe-finance.com`) :
>
> | Scénario | Résultat |
> |---|---|
> | Campagne **sans** pièce requise → candidature | ✅ **HTTP 201** (visible + actionnable dans l'admin) |
> | Campagne **avec** pièce requise → candidature multipart + fichier | ❌ **HTTP 400 générique** |
>
> Le réseau est OK (plus de 502) et le cœur de la candidature fonctionne
> (201 sans pièce). Le seul pas qui casse est l'**écriture du fichier joint dans
> le stockage objet (MinIO/S3)** :
> `CampaignApplicationDocument.objects.create(..., fichier=<fichier>)`.
> Le `except Exception` de `public_campaign_apply` masque la vraie erreur en 400.
>
> **But de ce doc : récupérer le vrai traceback pour corriger la cause exacte.**

---

## ✅✅ RÉSOLU (2026-08-07)

Candidature avec pièce jointe = **HTTP 201** en prod cliente (direct backend +
via proxy vitrine). Deux correctifs cumulés :

1. **PR #52** — `prod.py` : `addressing_style` piloté par `AWS_S3_ADDRESSING_STYLE`
   (défaut `virtual`). MinIO exige `path`.
2. **PR #53** — `docker-compose.prod.yml` : **déclarer** `AWS_S3_ADDRESSING_STYLE`
   dans le bloc `environment:` du backend (sinon `--env-file` ne l'injecte pas
   dans le conteneur — il ne sert qu'à interpoler le compose).

+ côté serveur : `AWS_S3_ADDRESSING_STYLE=path` dans `infra/.env.prod`.

> Piège clé : une variable de `.env.prod` n'atteint le conteneur **que** si elle
> est listée dans `environment:` du service. `--env-file` ≠ injection.

---

## 🎯 CAUSE RACINE (2026-08-07) — addressing_style « virtual » sur MinIO

Host fautif révélé par le test §2 :

```
Could not connect to the endpoint URL: "http://gathe-media.minio:9000/debug/test.txt"
Failed to resolve 'gathe-media.minio'
```

`gathe-media.minio` = `gathe-media` (**bucket**) + `minio` (**endpoint**) : botocore
est en addressing **« virtual »** (`<bucket>.<host>`), alors que **MinIO exige
« path »** (`<host>/<bucket>`). Le style était **codé en dur** dans
`backend/config/settings/prod.py:114` (`"addressing_style": "virtual"`, pensé pour
Backblaze B2 à DNS wildcard).

**Fix code (fait)** : rendu configurable par env, défaut `virtual` inchangé —

```python
# backend/config/settings/prod.py
"addressing_style": env("AWS_S3_ADDRESSING_STYLE", default="virtual"),
```

### TEST path-style (valide la correction SANS déployer)

Dans le shell backend (`dc exec backend python manage.py shell`), coller :

```python
import os, boto3
from botocore.config import Config

s3 = boto3.client(
    "s3",
    endpoint_url=os.environ["AWS_S3_ENDPOINT_URL"],
    aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
    aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
    config=Config(s3={"addressing_style": "path"}),
)
print("endpoint =", os.environ["AWS_S3_ENDPOINT_URL"], "| bucket =", os.environ["AWS_STORAGE_BUCKET_NAME"])
print(s3.put_object(Bucket=os.environ["AWS_STORAGE_BUCKET_NAME"], Key="debug/test.txt", Body=b"hello")["ResponseMetadata"]["HTTPStatusCode"])
```

| Résultat | Signification | Action |
|---|---|---|
| **`200`** ✅ | path-style résout tout (hôte joignable + bucket OK) | déployer le fix code + poser `AWS_S3_ADDRESSING_STYLE=path` |
| `NameResolutionError` sur l'hôte | l'endpoint lui-même n'est pas résolvable | corriger `AWS_S3_ENDPOINT_URL` (bon nom du conteneur MinIO sur le réseau `data`) |
| `NoSuchBucket` | hôte OK, bucket absent | créer le bucket `gathe-media` dans MinIO |

### Correction complète (après test 200)

1. **Déployer le fix code** (image actuelle a encore `"virtual"` en dur) : commit → PR → merge → deploy.
2. Ajouter dans **`infra/.env.prod`** :
   ```
   AWS_S3_ADDRESSING_STYLE=path
   ```
3. `dc up -d --no-deps --force-recreate backend` (fait aussi par le deploy) →
   re-tester une candidature avec pièce → **201** attendu.

---

## ✅ CAUSE CONFIRMÉE (2026-08-07) — DNS de l'endpoint MinIO/S3

Traceback serveur obtenu (`dc logs backend`) :

```
File ".../microcampaign_services.py", line 296, in create_public_application
    CampaignApplicationDocument.objects.create(...)
  ...
File ".../django/db/models/fields/files.py", line 338, in pre_save
    file.save(file.name, file.file, save=False)
  ...  (botocore / urllib3)
socket.gaierror: [Errno -2] Name or service not known
```

**Ce n'est ni le code, ni le réseau vitrine.** Quand le backend écrit le fichier
joint, botocore/S3 **ne résout pas le nom d'hôte de `AWS_S3_ENDPOINT_URL`** →
`gaierror: Name or service not known`. L'hôte MinIO configuré n'est pas
résolvable/joignable depuis le conteneur `backend`.

> Les `WARN POSTGRES_* not set` en tête des logs sont **normaux** (on passe par
> `DATABASE_URL`, pas `POSTGRES_*`). Sans rapport : la base fonctionne
> (candidature sans pièce = 201).

### Confirmer l'hôte fautif

```bash
dc exec backend printenv | grep -iE "AWS_|S3_|MEDIA|STORAGE"

dc exec backend python -c "import os,socket; from urllib.parse import urlparse; u=urlparse(os.environ['AWS_S3_ENDPOINT_URL']); print('host =', u.hostname); print('résolu ->', socket.gethostbyname(u.hostname))"
```
La 2ᵉ commande replante avec le même `gaierror` → confirmé.

### Correction (dans `infra/.env.prod`, côté serveur)

`AWS_S3_ENDPOINT_URL` doit pointer sur un hôte **joignable depuis le backend** :

1. **MinIO = conteneur sur le réseau `data`** (backend déjà rattaché :
   `networks: [internal, edge, data]`) → mettre le **nom exact du service/conteneur
   MinIO**, ex. `AWS_S3_ENDPOINT_URL=http://minio:9000`.
   Vérifier le vrai nom :
   ```bash
   docker network inspect $(grep DATA_NETWORK .env.prod | cut -d= -f2)
   ```
   (les conteneurs attachés = le nom à utiliser).
2. **MinIO exposé sur un domaine public** → mettre ce domaine complet
   (ex. `https://s3.gathe-finance.com`).

Puis :
```bash
dc up -d --no-deps --force-recreate backend
```
et re-tester une candidature avec pièce → doit passer en **201**.

---

## 0. Se placer au bon endroit (serveur cliente, en SSH)

```bash
cd /opt/gathe-finance/infra

# raccourci pour ne pas retaper les 2 compose à chaque fois :
alias dc='docker compose -f docker-compose.prod.yml -f docker-compose.client.yml --env-file .env.prod'
```

---

## 1. Le traceback réel (LE PLUS IMPORTANT — ~90 % du diagnostic)

Le code logue l'exception via `logger.exception("public_campaign_apply a échoué…")`.

```bash
# 1) Refais d'abord UNE candidature AVEC pièce depuis la vitrine
#    (pour générer l'erreur fraîche dans les logs), puis :
dc logs --tail=300 backend | grep -B2 -A40 "public_campaign_apply"
```

Les ~40 lignes qui suivent contiennent la vraie exception Python (celle qui est
masquée en 400 générique).

---

## 2. Test DÉCISIF : écrire un fichier dans le stockage, à la main

Reproduit exactement l'étape qui casse (`FileField.save` → MinIO/S3), sans
passer par toute la chaîne HTTP.

```bash
dc exec backend python manage.py shell
```

puis coller :

```python
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

name = default_storage.save("debug/test.txt", ContentFile(b"hello"))
print("OK écrit ->", name)
print("URL ->", default_storage.url(name))
print("backend ->", default_storage.__class__.__module__, default_storage.__class__.__name__)
```

- **Ça plante** → c'est bien le stockage. L'exception dit pourquoi (endpoint,
  creds, bucket, SSL…).
- **Ça marche** → le stockage est OK, le bug est ailleurs (retour dans le code).

---

## 3. Vérifier la config stockage passée au backend

```bash
dc exec backend printenv | grep -iE "AWS_|S3|MEDIA|STORAGE"
```

On regarde : `AWS_S3_ENDPOINT_URL`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`,
`AWS_STORAGE_BUCKET_NAME`. Une valeur vide ou fausse = cause directe.

---

## 4. Le backend voit-il MinIO ? (réseau + bucket)

```bash
dc exec backend python -c "import os,urllib.request; u=os.environ.get('AWS_S3_ENDPOINT_URL'); print('endpoint=',u); print(urllib.request.urlopen(u, timeout=5).status)"
```

- **Timeout / refus** → problème réseau (le backend n'est pas sur le réseau
  `data` de MinIO, ou l'endpoint est faux).
- **Réponse HTTP (même 403)** → MinIO est joignable → c'est les creds ou le
  **bucket manquant**.

---

## Interprétation rapide

La candidature **sans** pièce marche (201) ⇒ **Django + Postgres OK**. Seule
l'**écriture fichier** casse ⇒ cause la plus probable :

1. **Bucket inexistant** sur leur MinIO (`AWS_STORAGE_BUCKET_NAME`)
2. **Creds MinIO fausses** (`AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY`)
3. **`AWS_S3_ENDPOINT_URL`** non résolu / non joignable depuis le conteneur backend

Selon la sortie :
- **Config stockage** → corriger `infra/.env.prod` (variables `AWS_S3_*`) sur le
  serveur, puis `dc up -d --no-deps --force-recreate backend`.
- **Autre** → correction côté code (+ durcir le message d'erreur pour distinguer
  une erreur de stockage — prévu au plan LOT 6a).

---

## Ménage post-test (données de test en base cliente)

Le test live a laissé, sur la prod cliente :

- Campagne **id 1** — « TEST Candidature Live 07-08 » (avec pièce requise)
- Campagne **id 2** — « TEST No-Doc Live 07-08 »
- Candidature **id 3** — TestLive Probe / probe.nodoc@example.com (En attente)

À clôturer / supprimer depuis l'admin (`admin.gathe-finance.com` → Campagnes)
une fois le diagnostic terminé.

---

## Références code

- `backend/apps_coop/loans/microcampaign_public.py` → `public_campaign_apply`
  (le `except Exception` qui masque en 400).
- `backend/apps_coop/loans/microcampaign_services.py` → `create_public_application`
  (ligne `CampaignApplicationDocument.objects.create(..., fichier=…)` = l'étape
  qui écrit dans le stockage).
- `infra/docker-compose.client.yml` → variables `AWS_S3_*` / réseau `data`.
