# Déploiement Gathe Finance, guide pas à pas

Document de référence pour déployer la stack Gathe Finance sur le VPS Contabo
en utilisant les images Docker publiées sur GitHub Container Registry (GHCR).

Cible : un collaborateur qui n'a jamais déployé ce projet, avec un accès SSH
au VPS et un compte GitHub avec la permission `read:packages` sur le repo.

---

## 1. Vue d'ensemble

### 1.1 Schéma de l'architecture

```
                  Internet
                     |
                     | DNS (5 sous-domaines)
                     v
              +-------------+
              |   Traefik   |   :80 (challenge LE) + :443 (TLS)
              |  + LetsEnc. |   reverse-proxy, termine TLS,
              +------+------+   route par Host: header
                     |
       +-------------+-------------+-------------+-------------+
       |             |             |             |             |
       v             v             v             v             v
   +-------+    +--------+    +--------+    +--------+    +--------+
   | site  |    | portal |    | admin  |    | api    |    | cms    |
   | Next  |    | Next   |    | Next   |    | Django |    | Wagtail|
   | :3000 |    | :3000  |    | :3000  |    | :8000  |    | :8000  |
   +---+---+    +---+----+    +---+----+    +---+----+    +---+----+
       |            |             |              |             |
       +------------+-------------+--------------+-------------+
                                  |
                                  v
                          +---------------+
                          |   backend     |   (memes container que api/cms,
                          |   Django+DRF  |    Wagtail vit dans /cms/admin)
                          |   +Wagtail    |
                          +-------+-------+
                                  |
                                  | psycopg
                                  v
                          +---------------+
                          |   Postgres    |   :5432 (interne uniquement)
                          |   16 alpine   |   volume persistant
                          +-------+-------+
                                  ^
                                  |
                          +-------+-------+
                          |   qcluster    |   django-q2 scheduler
                          |  (same image  |   crons : interets, retards,
                          |   as backend) |   reconciliation Tara
                          +---------------+

                          +---------------+
                          |   backup      |   pg_dump quotidien 03:00 UTC
                          |   alpine+cron |   -> /backups/*.sql.gz
                          +---------------+
```

### 1.2 Role de chaque composant

| Service     | Image                                                          | Role                                                                 | Port interne |
|-------------|----------------------------------------------------------------|----------------------------------------------------------------------|--------------|
| `traefik`   | `traefik:v3.1`                                                 | Reverse-proxy. Expose 80 + 443 vers Internet. Termine TLS via Let's Encrypt. Route les requetes vers les bons services selon le header `Host:`. Profile `traefik` (optionnel si nginx-host existe). | 80, 443 |
| `db`        | `postgres:16-alpine`                                           | Base relationnelle unique. Toutes les donnees metier (members, savings, loans, payments, notifications, wagtail). Healthcheck `pg_isready`. Volume persistant. | 5432 (interne) |
| `backend`   | `ghcr.io/.../backend:latest`                                    | Django 5 + DRF + Wagtail 6. Sert l'API (`/api/v1/*`) et le CMS (`/cms/admin/*`). 2 routes Traefik : `api.gathe-finance.horus-lab.com` et `cms.gathe-finance.horus-lab.com`. Migrations + collectstatic au boot. | 8000 |
| `qcluster`  | `ghcr.io/.../backend:latest`                                    | Meme image que backend, lance `python manage.py qcluster`. Execute les taches programmees (django-q2) : interets epargne 1%/mois, suivi retards, reconciliation Tara horaire, commission collecte fin de mois, anniversaires epargne. | aucun |
| `site`      | `ghcr.io/.../site:latest`                                       | Next.js 15. Vitrine publique sous `gathe-finance.horus-lab.com`. Headless Wagtail, formulaire de contact, devenir-membre. | 3000 |
| `portal`    | `ghcr.io/.../portal:latest`                                     | Next.js 15. Espace membre sous `portail.gathe-finance.horus-lab.com`. Login, dashboard, epargne, credits, retraits, notifications, activation 3 frais. | 3000 |
| `admin`     | `ghcr.io/.../admin:latest`                                      | Next.js 15. Back-office staff sous `admin.gathe-finance.horus-lab.com`. KPIs, membres, credits, paiements, campagnes, formulaires dynamiques, annonces, cron editor. | 3000 |
| `backup`    | `alpine` + `pg_dump`                                            | Cron interne quotidien (03:00 UTC). `pg_dump` compresse vers `/backups/gathe-YYYY-MM-DD.sql.gz`. Retention controlee par `BACKUP_RETENTION_DAYS`. | aucun |

### 1.3 Flux des donnees

1. Un client (navigateur ou app mobile) envoie une requete HTTPS vers un sous-domaine.
2. Traefik termine TLS, lit le header `Host:`, route vers le service correspondant.
3. Pour les apps Next.js, la page est rendue cote serveur. Les appels API du SPA passent par `/api/v1/*` qui sont proxies vers `backend:8000` via le reseau Docker interne.
4. Backend Django parle a Postgres via `psycopg` (reseau Docker `internal`, jamais expose au public).
5. Backend emet des emails via l'API HTTPS Brevo (pas de SMTP) et des paiements Mobile Money via l'API Tara MoMo.
6. qcluster picke periodiquement des taches dans la table `django_q_task` et les execute.
7. Backup quotidien : pg_dump compresse vers le volume `backups`.

### 1.4 Topologie reseau Docker

Trois reseaux internes :
- `internal` : db + backend + qcluster + backup. Aucune exposition publique.
- `web` : traefik + backend + site + portal + admin. C'est par la que Traefik route les requetes.
- Par defaut Docker bridge pour ce qui n'a pas besoin de routage explicite.

Seul Traefik expose des ports vers le host (`80:80` + `443:443`). Tous les autres services sont accessibles uniquement via le reseau interne.

### 1.5 DNS attendu

Cinq enregistrements A pointant vers l'IP du VPS Contabo :

| Sous-domaine                              | Pointe vers      | Sert                                  |
|-------------------------------------------|------------------|---------------------------------------|
| `gathe-finance.horus-lab.com`             | IP VPS Contabo   | Vitrine publique (`site`)             |
| `portail.gathe-finance.horus-lab.com`     | IP VPS Contabo   | Espace membre (`portal`)              |
| `admin.gathe-finance.horus-lab.com`       | IP VPS Contabo   | Back-office staff (`admin`)           |
| `api.gathe-finance.horus-lab.com`         | IP VPS Contabo   | API REST + webhook Tara (`backend`)   |
| `cms.gathe-finance.horus-lab.com`         | IP VPS Contabo   | Wagtail admin (`backend`)             |

Les 5 doivent etre crees AVANT de lancer la stack, sinon Let's Encrypt echouera a emettre les certificats (challenge HTTP-01 sur le port 80).

### 1.6 Pipeline GHCR (zero build cote VPS)

A chaque push sur la branche `main` :

```
[dev pousse main] -> [GitHub Actions release.yml]
                         |
                         | matrix 4 jobs en parallele
                         v
                  [docker buildx build + push]
                         |
                         v
   ghcr.io/edwintchakounte/gathefinance_project/{backend,site,portal,admin}:latest
                                                                          :main
                                                                          :sha-XXXXXXX
                         |
                         | "docker compose pull"
                         v
                    [VPS Contabo]
                         |
                         | "docker compose up -d"
                         v
                    [services live]
```

Cote VPS, plus de `git pull` ni de `--build`. Juste `pull` + `up -d`.

---

## 2. Pre-requis avant de commencer

Cocher cette liste avant d'attaquer le deploiement :

- [ ] Acces SSH au VPS Contabo (IP + user, demander a Edwin).
- [ ] Compte GitHub ajoute en collaborateur du repo `EdwinTchakounte/GatheFinance_project`. Invitation acceptee sur `https://github.com/EdwinTchakounte/GatheFinance_project/invitations`.
- [ ] Cle Brevo recuperee aupres d'Edwin (`BREVO_API_KEY`, format `xkeysib-...`).
- [ ] DNS prepare : les 5 sous-domaines listes en 1.5 pointent vers l'IP du VPS.
- [ ] Ports 80 + 443 ouverts cote firewall VPS (Hetzner Cloud, Contabo Panel, ou `ufw allow 80,443/tcp`).
- [ ] Docker et Docker Compose v2 installes sur le VPS. Verifier : `docker --version` et `docker compose version`.

---

## 3. Etape 1 : creer un Personal Access Token GitHub

Le VPS doit s'authentifier aupres de GHCR pour tirer les images privees.

Sur `https://github.com` :

1. Photo de profil en haut a droite, cliquer **Settings**.
2. Tout en bas a gauche, **Developer settings**.
3. **Personal access tokens** puis **Tokens (classic)**.
4. Bouton **Generate new token** puis **Generate new token (classic)**.
5. Remplir :
   - **Note** : `Gathe Finance VPS deploy`
   - **Expiration** : `90 days` (ou *No expiration* pour un VPS de prod stable)
   - **Select scopes** : cocher uniquement `read:packages` (sous la section *write:packages*)
6. Bouton vert **Generate token** en bas.
7. Sur l'ecran suivant, le token apparait UNE SEULE FOIS (format `ghp_...`). Copier immediatement et le stocker dans un gestionnaire de mots de passe.

Si on ferme la page sans copier, regenerer un nouveau token.

---

## 4. Etape 2 : SSH au VPS

```bash
ssh <user>@<ip-contabo>
```

Verifier qu'on est bien la :

```bash
hostname
docker --version
docker compose version
df -h /
```

---

## 5. Etape 3 : verifier le DNS

```bash
for d in gathe-finance portail.gathe-finance admin.gathe-finance api.gathe-finance cms.gathe-finance; do
  echo -n "$d.horus-lab.com -> "
  dig +short ${d}.horus-lab.com | head -1
done
```

Resultat attendu : les 5 lignes retournent EXACTEMENT la meme IP (celle du VPS).

Si une IP manque, retourner chez le registrar DNS, creer l'enregistrement A manquant, attendre 5 a 60 minutes la propagation, puis re-tester. Ne pas demarrer la stack tant que les 5 DNS ne sont pas OK.

---

## 6. Etape 4 : cloner ou mettre a jour le repo

### Cas A, premiere installation sur le VPS

```bash
sudo mkdir -p /opt/gathe-finance
sudo chown $USER:$USER /opt/gathe-finance
git clone https://github.com/EdwinTchakounte/GatheFinance_project.git /opt/gathe-finance
cd /opt/gathe-finance/infra
```

### Cas B, repo deja present

```bash
cd /opt/gathe-finance
git fetch origin
git checkout main
git pull origin main
cd infra
```

---

## 7. Etape 5 : login GHCR

Coller le PAT a la place de `ghp_PASTE_PAT_HERE` et remplacer le username GitHub :

```bash
echo "ghp_PASTE_PAT_HERE" | docker login ghcr.io -u <ton-username-github> --password-stdin
```

Resultat attendu : `Login Succeeded`.

Le token est ecrit dans `~/.docker/config.json` (chmod 600 par defaut). Persistant entre reboots, pas besoin de relogin.

Verifier :

```bash
cat ~/.docker/config.json | grep ghcr
```

---

## 8. Etape 6 : configurer le fichier `.env.prod`

```bash
cd /opt/gathe-finance/infra
cp .env.prod.example .env.prod
nano .env.prod
```

Remplir au minimum les variables suivantes (les autres restent OK avec les defauts) :

```env
# Domaines, deja corrects dans l'example
SITE_DOMAIN=gathe-finance.horus-lab.com
PORTAL_DOMAIN=portail.gathe-finance.horus-lab.com
ADMIN_DOMAIN=admin.gathe-finance.horus-lab.com
API_DOMAIN=api.gathe-finance.horus-lab.com
CMS_DOMAIN=cms.gathe-finance.horus-lab.com
DJANGO_ALLOWED_HOSTS=gathe-finance.horus-lab.com,portail.gathe-finance.horus-lab.com,admin.gathe-finance.horus-lab.com,api.gathe-finance.horus-lab.com,cms.gathe-finance.horus-lab.com

# Secrets Django (deja generes par Edwin, a remplacer par les valeurs envoyees par message)
DJANGO_SECRET_KEY=__valeur_fournie_par_edwin__
REVALIDATE_SECRET=__valeur_fournie_par_edwin__

# Superuser bootstrap (cree au 1er demarrage, sera deja la ensuite)
DJANGO_SUPERUSER_USERNAME=admin
DJANGO_SUPERUSER_EMAIL=admin@horus-lab.com
DJANGO_SUPERUSER_PASSWORD=__valeur_fournie_par_edwin__

# Postgres
POSTGRES_DB=gathe_prod
POSTGRES_USER=gathe
POSTGRES_PASSWORD=__valeur_fournie_par_edwin__

# Brevo (email transactionnel)
BREVO_API_KEY=__cle_brevo_fournie__
DEFAULT_FROM_EMAIL="Gathe Finance <noreply@horus-lab.com>"
CONTACT_NOTIFICATION_EMAIL=contact@gathe-finance.com

# Tara MoMo : laisser vide pour le 1er deploy (mode mock)
TARA_API_KEY=
TARA_BUSINESS_ID=
TARA_WEBHOOK_SECRET=

# Let's Encrypt
ACME_EMAIL=ops@horus-lab.com

# Tag d'images GHCR a tirer
GATHE_IMAGE_TAG=latest

# Backups
BACKUP_RETENTION_DAYS=30
```

Sauvegarder : `Ctrl+O` puis `Enter` puis `Ctrl+X`.

Note importante : ne jamais committer ce fichier. Il est deja dans `.gitignore`.

---

## 9. Etape 7 : stopper la stack precedente si elle tourne

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod ps
```

Si des conteneurs sont listes :

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod down
```

CRITIQUE : ne JAMAIS ajouter `-v` au `down`. Le flag `-v` supprimerait les volumes nommes (DB Postgres, media uploads, certificats Let's Encrypt deja emis, backups). Le `down` simple garde tout, on peut re-up sans rien perdre.

Verifier que tout est bien stoppe :

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod ps
```

Doit retourner une liste vide.

---

## 10. Etape 8 : tirer les 4 images GHCR

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod pull
```

Devrait tirer en parallele :
- `ghcr.io/edwintchakounte/gathefinance_project/backend:latest`
- `ghcr.io/edwintchakounte/gathefinance_project/site:latest`
- `ghcr.io/edwintchakounte/gathefinance_project/portal:latest`
- `ghcr.io/edwintchakounte/gathefinance_project/admin:latest`

Plus les images d'infra : `postgres:16-alpine` + `traefik:v3.1` + `alpine` (backup).

Duree typique : 1 a 3 minutes selon la bande passante du VPS.

En cas d'echec `denied: permission_denied` ou `unauthorized` : revoir l'etape 5 (login GHCR) et l'etape 1 (PAT et permissions sur le repo).

---

## 11. Etape 9 : demarrer la stack

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod --profile traefik up -d
```

Le flag `--profile traefik` active le reverse-proxy Traefik integre.

Cas alternatif : si un nginx host existe deja devant ce VPS et fait reverse-proxy vers les apps, omettre `--profile traefik` et utiliser `docker-compose.nginx-external.yml` a la place.

Verifier que tout est demarre :

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod --profile traefik ps
```

Resultat attendu, tous les services en `running`, `healthy` apres 30 a 60s :

```
NAME                          STATUS                   PORTS
gathe-finance-prod-db-1       Up 1m (healthy)          5432/tcp
gathe-finance-prod-backend-1  Up 1m (healthy)          8000/tcp
gathe-finance-prod-qcluster-1 Up 1m                    8000/tcp
gathe-finance-prod-site-1     Up 1m                    3000/tcp
gathe-finance-prod-portal-1   Up 1m                    3000/tcp
gathe-finance-prod-admin-1    Up 1m                    3000/tcp
gathe-finance-prod-traefik-1  Up 1m                    0.0.0.0:80,443->80,443/tcp
gathe-finance-prod-backup-1   Up 1m                    -
```

Le backend prend 30 a 60s pour devenir `healthy` : il applique les migrations + collectstatic au demarrage.

---

## 12. Etape 10 : suivre l'emission des certificats Let's Encrypt

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod --profile traefik logs -f traefik | grep -iE "obtain|register|error|challenge"
```

On doit voir, pour chacun des 5 domaines, des lignes du genre :

```
... Trying to challenge certificate for domain "api.gathe-finance.horus-lab.com" ...
... Certificate obtained successfully ...
```

Duree : 1 a 3 minutes pour les 5 certificats. `Ctrl+C` une fois OK.

Cas d'erreur frequents :
- `unable to authorize, connection refused` : port 80 bloque par firewall. Verifier `ufw status` ou le panel Contabo.
- `dns lookup failed` : le sous-domaine ne pointe pas sur le VPS. Re-faire l'etape 5.
- `too many requests for ... LimitsExceeded` : quota Let's Encrypt atteint (5 certs / heure / domaine racine). Attendre 1h et retry.

Les certificats sont stockes dans le volume `letsencrypt`. Ils sont renouveles automatiquement par Traefik 30 jours avant expiration.

---

## 13. Etape 11 : seeder la base de donnees

Migrations deja appliquees automatiquement par l'entrypoint backend. On seede maintenant les donnees de reference (idempotent, peut etre relance sans risque) :

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod exec backend python manage.py seed_email_templates
docker compose -f docker-compose.prod.yml --env-file .env.prod exec backend python manage.py seed_event_catalog
docker compose -f docker-compose.prod.yml --env-file .env.prod exec backend python manage.py seed_q_schedules
docker compose -f docker-compose.prod.yml --env-file .env.prod exec backend python manage.py seed_loan_tiers
```

Detail de chaque seed :
- `seed_email_templates` : 15 templates HTML (welcome, credit decaisse, retard, retrait, avaliste, funding...).
- `seed_event_catalog` : catalogue des evenements metier auxquels les notifications se branchent.
- `seed_q_schedules` : programme les crons django-q2 (interets epargne mensuel, retards quotidien, reconciliation Tara horaire, commission fin de mois, anniversaires annuels).
- `seed_loan_tiers` : 3 paliers de credit selon le reglement interieur (montants + duree maxi).

Optionnel, pour peupler une demo de credits visible dans l'admin :

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod exec backend python manage.py seed_demo_credits
```

---

## 14. Etape 12 : smoke tests

Depuis le VPS ou n'importe quel poste avec internet :

```bash
curl -sI https://api.gathe-finance.horus-lab.com/api/v1/healthz/
curl -sI https://gathe-finance.horus-lab.com/
curl -sI https://portail.gathe-finance.horus-lab.com/
curl -sI https://admin.gathe-finance.horus-lab.com/
curl -sI https://cms.gathe-finance.horus-lab.com/admin/
```

Chacun doit retourner `HTTP/2 200` ou `HTTP/2 30x`. Pas de `HTTP/2 502` ni `503`.

Ouvrir dans un navigateur et verifier :
- Le cadenas TLS est vert, pas d'avertissement certificat.
- La vitrine charge correctement (https://gathe-finance.horus-lab.com).
- Le login admin fonctionne (https://admin.gathe-finance.horus-lab.com), user `admin`, password = `DJANGO_SUPERUSER_PASSWORD` du `.env.prod`.
- Wagtail charge (https://cms.gathe-finance.horus-lab.com/admin/), memes identifiants.

Test e-mail Brevo :
- Aller sur la vitrine, soumettre le formulaire `/contact`.
- Verifier dans Brevo > Logs que l'email est envoye.

---

## 15. Mises a jour futures (CD automatique)

Une fois le 1er bootstrap fait (sections 1 a 14), les mises a jour
suivantes sont entierement automatiques :

```
Edwin push main
  -> CI (ci.yml)         : tests pytest + lint + flutter, build 4 images GHCR
  -> Deploy (deploy.yml) : SSH au VPS, pull + up -d, healthcheck, rollback si KO
```

Cycle complet : commit -> ~10 min plus tard, prod a jour. Aucune action
humaine sur le VPS.

### 15.1 Configurer les secrets GitHub (une seule fois)

Le workflow `deploy.yml` a besoin de 3 secrets pour SSH sur le VPS.
Sur GitHub : **Settings > Secrets and variables > Actions > New repository secret**.

| Secret | Valeur | Comment l'obtenir |
|---|---|---|
| `VPS_HOST` | IP ou hostname du VPS Contabo | Demande a ton hebergeur Contabo |
| `VPS_USER` | utilisateur SSH (souvent `root` ou un user sudo) | Celui que tu utilises pour `ssh user@host` |
| `VPS_SSH_PRIVATE_KEY` | cle privee SSH (format OpenSSH, ed25519 recommande) | Voir 15.2 |
| `VPS_DEPLOY_PATH` (optionnel) | chemin du repo sur le VPS, defaut `/opt/gathe-finance` | Ou tu as fait `git clone` |

### 15.2 Generer une cle SSH dediee au CD

Sur ton poste local (ou le VPS lui-meme) :

```bash
# Cree une cle ed25519 dediee au CI/CD (pas ta cle perso)
ssh-keygen -t ed25519 -C "gathe-finance-ci" -f ~/.ssh/gathe_ci -N ""

# Voir la cle publique a installer sur le VPS
cat ~/.ssh/gathe_ci.pub

# Voir la cle privee a coller dans le secret GitHub
cat ~/.ssh/gathe_ci
```

Sur le VPS, ajoute la cle publique aux cles autorisees :

```bash
mkdir -p ~/.ssh && chmod 700 ~/.ssh
echo "ssh-ed25519 AAAA... gathe-finance-ci" >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
```

Test depuis ton poste local :

```bash
ssh -i ~/.ssh/gathe_ci <user>@<vps> "hostname && docker compose version"
# Doit retourner sans demander de mot de passe.
```

Une fois OK, colle le contenu de `~/.ssh/gathe_ci` (cle PRIVEE) dans
le secret GitHub `VPS_SSH_PRIVATE_KEY`. Inclus les lignes
`-----BEGIN OPENSSH PRIVATE KEY-----` et `-----END OPENSSH PRIVATE KEY-----`.

### 15.3 Comportement du workflow `deploy.yml`

Une fois les secrets en place, le deploy auto fonctionne ainsi :

1. Push sur `main` -> CI tourne (5-10 min).
2. CI verte -> `deploy.yml` se declenche automatiquement.
3. SSH au VPS, lit l'ancien `GATHE_IMAGE_TAG` du `.env.prod` (pour rollback).
4. Met a jour le tag (par defaut `latest`), `docker compose pull`.
5. `docker compose up -d --profile traefik` (recree uniquement les services dont l'image a change).
6. Boucle 90s pour attendre que le healthcheck backend passe `healthy`.
7. Si timeout, repin l'ancien tag dans `.env.prod` et re-up -> rollback automatique.
8. Smoke test depuis le runner GitHub : 5 URLs publiques attendues en 2xx/3xx.
9. Echec smoke -> job rouge, alerte (mais services deja redeployes au step 5).

### 15.4 Deploy manuel (rollback ou rejouer)

Pour deployer une version specifique sans push :

1. Va sur https://github.com/EdwinTchakounte/GatheFinance_project/actions
2. Clic sur le workflow **Deploy to prod** dans la sidebar.
3. Bouton **Run workflow** -> renseigne `image_tag` (ex `sha-d1a416d` pour rollback).
4. Lance.

Mise a jour manuelle classique (sans le CD auto) :

```bash
ssh <user>@<ip-contabo>
cd /opt/gathe-finance/infra
docker compose -f docker-compose.prod.yml --env-file .env.prod pull
docker compose -f docker-compose.prod.yml --env-file .env.prod --profile traefik up -d
```

---

## 16. Rollback en cas de regression

Si une nouvelle version casse la prod :

1. Trouver le SHA de l'avant-derniere version qui marchait, par exemple en regardant `git log --oneline` ou les tags d'images sur GHCR (`https://github.com/users/EdwinTchakounte/packages`).

2. Editer `/opt/gathe-finance/infra/.env.prod` :

```env
GATHE_IMAGE_TAG=sha-d1a416d
```

3. Tirer + re-up :

```bash
cd /opt/gathe-finance/infra
docker compose -f docker-compose.prod.yml --env-file .env.prod pull
docker compose -f docker-compose.prod.yml --env-file .env.prod --profile traefik up -d
```

Attention : si la regression est une migration DB destructive, le rollback du code seul ne suffira pas. Il faudra restaurer un backup Postgres (section 17). Pour eviter ce cas, toute migration risque doit etre testee en staging d'abord.

Pour revenir a `latest` :

```env
GATHE_IMAGE_TAG=latest
```

---

## 17. Backups Postgres

### Strategie automatique

Le service `backup` lance un cron interne qui execute `pg_dump` tous les jours a 03:00 UTC.
- Fichiers : `/backups/gathe-YYYY-MM-DD.sql.gz` dans le volume Docker `backups`.
- Retention : controlee par `BACKUP_RETENTION_DAYS` du `.env.prod` (defaut 30 jours).

Lister les backups :

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod exec backup ls -lh /backups/
```

### Backup manuel a la demande

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod exec backup /backup.sh
```

### Restauration depuis un backup

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod exec -T db \
  bash -c "gunzip -c /backups/gathe-2026-06-21.sql.gz | psql -U gathe -d gathe_prod"
```

### Recommandation forte

Le volume Docker `backups` vit sur le disque du VPS. Si le VPS est compromis (rancongiciel, suppression accidentelle), on perd la DB et ses sauvegardes en meme temps.

Solution : monter le volume sur un stockage externe (NAS, Backblaze B2, OVH PCA) via un override compose ou un `rsync` push quotidien :

```bash
# Exemple de cron host (a ajouter dans /etc/cron.daily/gathe-backup-sync)
docker compose -f /opt/gathe-finance/infra/docker-compose.prod.yml --env-file /opt/gathe-finance/infra/.env.prod cp backup:/backups /mnt/backup-external/
```

---

## 18. Operations courantes

### Lire les logs d'un service

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod logs -f backend
docker compose -f docker-compose.prod.yml --env-file .env.prod logs -f portal
docker compose -f docker-compose.prod.yml --env-file .env.prod --profile traefik logs -f traefik
```

### Redemarrer un service

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod restart backend
```

### Recreer un service (apres edit du `.env.prod` par exemple)

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --force-recreate backend qcluster
```

### Acceder a un shell Django

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod exec backend python manage.py shell
```

### Acceder a psql

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod exec db psql -U gathe -d gathe_prod
```

### Voir la conso ressources

```bash
docker stats
```

### Bascule mode Tara mock vers prod

1. Remplir dans `.env.prod` :
   ```env
   TARA_API_KEY=...
   TARA_BUSINESS_ID=...
   TARA_WEBHOOK_SECRET=...
   ```
2. Recreer backend + qcluster :
   ```bash
   docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --force-recreate backend qcluster
   ```
3. Dans le dashboard Tara, configurer l'URL de webhook :
   ```
   https://api.gathe-finance.horus-lab.com/api/v1/payments/webhook/tara/
   ```

---

## 19. Troubleshooting

### `docker login ghcr.io` retourne 401 unauthorized

- Verifier que le PAT a bien le scope `read:packages`.
- Verifier que le compte GitHub est bien collaborateur du repo (invitation acceptee).
- Regenerer un PAT et reessayer.

### `docker compose pull` retourne `denied: installation not allowed`

- Le PAT n'a pas acces aux packages d'Edwin. Verifier la collaboration sur le repo cote GitHub UI.

### Traefik n'emet pas le certificat

Symptome : `curl https://api.gathe-finance.horus-lab.com/` retourne une erreur SSL.

Causes possibles :
1. DNS pas encore propage. Verifier avec `dig +short`.
2. Port 80 bloque par firewall (LE fait le challenge HTTP-01 sur le 80).
3. Quota LE atteint. Attendre 1h.
4. ACME_EMAIL invalide. Verifier dans `.env.prod`.

Voir les logs Traefik :
```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod --profile traefik logs traefik | grep -iE "error|challenge"
```

### Backend renvoie HTTP 502 derriere Traefik

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod logs -f backend
```

Causes typiques :
1. Migration en cours (60s au demarrage), patienter.
2. Erreur de connexion DB : `.env.prod` mal renseigne (POSTGRES_PASSWORD different).
3. Crash a l'import (exception Python). Logs Django tres explicites.

### Erreur `Invalid HTTP_HOST header`

Symptome : `Bad Request (400)` quand on visite un sous-domaine.

Cause : ce domaine n'est pas dans `DJANGO_ALLOWED_HOSTS` du `.env.prod`. Ajouter le domaine en cause (separer par virgules), puis :

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --force-recreate backend qcluster
```

### Erreur CSRF dans l'admin Django

Symptome : `CSRF Failed: Origin checking failed`.

Solution : ajouter le domaine dans la variable optionnelle `CSRF_TRUSTED_ORIGINS` du `.env.prod`, avec le scheme :

```env
CSRF_TRUSTED_ORIGINS=https://admin.gathe-finance.horus-lab.com,https://cms.gathe-finance.horus-lab.com
```

Puis recreer le backend.

### Emails Brevo ne partent pas

Verifier dans cet ordre :
1. `BREVO_API_KEY` bien renseigne dans `.env.prod` (format `xkeysib-...`).
2. L'expediteur de `DEFAULT_FROM_EMAIL` est un domaine **verifie** dans Brevo (dashboard > Senders & IPs). Sinon Brevo rejette silencieusement.
3. Logs Django :
   ```bash
   docker compose -f docker-compose.prod.yml --env-file .env.prod logs backend | grep -i brevo
   ```

### Disk full

Le VPS arrive en `No space left on device`. Cleanup :

```bash
docker system prune -af --volumes
# Attention : "--volumes" supprime aussi les volumes orphelins. Ne pas
# le passer si tu as des volumes detaches d'anciens deploys que tu veux garder.
```

---

## 20. Contacts et ressources

- Repo : `https://github.com/EdwinTchakounte/GatheFinance_project`
- CI / images GHCR : `https://github.com/EdwinTchakounte/GatheFinance_project/actions`
- Rapport d'audit : `audit/AUDIT_2026-06-20.md` (cote repo)
- Plan de tests : `audit/TESTS_PLAN.md`
- Checklist Play Store mobile : `audit/PLAY_STORE.md`
- Tara sandbox setup : `architecture/sandbox-tara.md` (si present dans le repo)
- Edwin (lead dev) : horus8391@gmail.com

---

Fin du guide. Toute coquille ou incoherence a signaler a Edwin pour mise a jour.
