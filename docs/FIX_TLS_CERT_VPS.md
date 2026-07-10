# Fix — certificat TLS des domaines GATHE (VPS mutualisé)

## ⚡ TL;DR — cause confirmée (2026-07-10) : nginx afrikamode recréé

Ça **marchait**, puis le login mobile a cassé. Cause : le **conteneur nginx
d'afrikamode (`backend-nginx-1`) a été recréé**. La conf GATHE avait été
*copiée dans* le conteneur (pas montée en volume) → **effacée** à la recréation.
Sans les blocs `server` GATHE, nginx retombe sur son `default_server`
(afrikamode) et sert **son** cert pour tous les domaines gathe → l'app rejette.

> ⚠️ **Piège 502 après restauration de la conf** : `nginx.gathe-finance.container.conf`
> route vers les upstreams **`gathe-site` / `gathe-portal` / `gathe-admin` /
> `gathe-backend`**. Ces alias UNIQUES viennent de `docker-compose.nginx-external.yml`.
> Si un conteneur front a été recréé sans l'override (ou avec une version qui ne
> déclare pas l'alias), nginx ne résout que `gathe-backend` → **API OK mais
> vitrine/portail/admin en 502**. Vérifier :
> ```bash
> for h in gathe-site gathe-portal gathe-admin gathe-backend; do
>   docker exec backend-nginx-1 getent hosts "$h" >/dev/null 2>&1 && echo "$h OK" || echo "$h ECHEC"
> done
> ```
> Rétablir un alias manquant (immédiat) :
> ```bash
> docker network disconnect backend_default gathe-finance-prod-site-1
> docker network connect --alias gathe-site backend_default gathe-finance-prod-site-1
> # idem portal→gathe-portal, admin→gathe-admin. Puis: docker exec backend-nginx-1 nginx -s reload
> ```
> Durable : les alias sont dans `docker-compose.nginx-external.yml` → un
> `up -d site portal admin` avec l'override les repose.

### Réparation immédiate (≈ 30 s)

```bash
# 1. Restaurer la conf GATHE dans le conteneur nginx
docker cp /opt/gathe-finance/infra/nginx.gathe-finance.container.conf \
  backend-nginx-1:/etc/nginx/conf.d/gathe-finance.conf

# 2. Tester + recharger
docker exec backend-nginx-1 nginx -t && docker exec backend-nginx-1 nginx -s reload

# 3. Confirmer le BON cert (doit afficher gathe, plus afrikamode)
echo | openssl s_client -connect api.gathe-finance.horus-lab.com:443 \
  -servername api.gathe-finance.horus-lab.com 2>/dev/null \
  | openssl x509 -noout -subject -dates
```

- `nginx -t` **OK** + `openssl` montre `CN = gathe-finance…` → **login mobile OK direct**.
- `nginx -t` **erreur `certificate ... No such file`** → le volume letsencrypt n'a
  pas survécu non plus : ré-émettre le cert (**§2bis étape B**) puis reprendre au 2.

### Pour que ça ne se reperde JAMAIS (à faire une fois)

Monter la conf GATHE en **volume** dans le nginx d'afrikamode (au lieu de la
copier). Trouver le dossier conf.d monté depuis l'hôte :

```bash
docker inspect backend-nginx-1 --format '{{range .Mounts}}{{.Source}} -> {{.Destination}}{{"\n"}}{{end}}'
```

Si une ligne `… -> /etc/nginx/conf.d` apparaît, **copier la conf dans ce dossier
hôte (Source)** au lieu du `docker cp` → elle survivra à toute recréation du
conteneur. Idéalement, ajouter `nginx.gathe-finance.container.conf` au montage
conf.d dans le `docker-compose` d'afrikamode.

> 💡 Le volume `letsencrypt` (le cert) est en général déjà persistant et survit
> à la recréation — c'est **la conf** qui se reperd. C'est pourquoi le fix
> immédiat est juste de re-déposer la conf.

---

## Symptôme
- **Login mobile impossible** (l'app valide le TLS → rejette la connexion).
- Le web affiche (ou devrait afficher) un **avertissement de certificat**.

## Cause racine
Le VPS héberge plusieurs projets (gathe, afrikamode…) derrière un **nginx
partagé**. Pour **tous** les sous-domaines `*.gathe-finance.horus-lab.com`, ce
nginx sert le certificat d'**afrikamode** au lieu de celui de GATHE :

```
api / admin / cms / gathe-finance  →  CN = backend.afrikamode.horus-lab.com   ❌ (attendu : gathe)
```

→ certificat qui ne correspond pas au domaine → clients stricts (mobile) rejettent.

**Pourquoi** : la conf nginx GATHE (`infra/nginx.gathe-finance.container.conf`)
pointe vers `/etc/letsencrypt/live/gathe-finance.horus-lab.com/…`, mais soit ce
**certificat n'existe pas**, soit la **conf n'est pas chargée** dans le nginx
partagé → il retombe sur le certificat par défaut (afrikamode).

Vérification (depuis n'importe où) :
```bash
echo | openssl s_client -connect api.gathe-finance.horus-lab.com:443 \
  -servername api.gathe-finance.horus-lab.com 2>/dev/null \
  | openssl x509 -noout -subject
# Doit afficher CN = *.gathe-finance.horus-lab.com (PAS afrikamode)
```

---

## 1. Diagnostic (sur le VPS, en root)

```bash
# La conf nginx de GATHE est-elle chargée ?
ls -la /etc/nginx/conf.d/ | grep -i gathe

# Le certificat Let's Encrypt de GATHE existe-t-il ?
ls -la /etc/letsencrypt/live/ | grep -i gathe
ls -la /etc/letsencrypt/live/gathe-finance.horus-lab.com/ 2>/dev/null

# Le reverse-proxy : nginx host ou conteneur ?
which nginx && nginx -v 2>&1
docker ps --format '{{.Names}} {{.Image}}' | grep -iE "nginx|proxy|certbot|acme"
```

### ✅ Résultat constaté (2026-07-09)

```
/etc/nginx/conf.d/            → n'existe pas
/etc/letsencrypt/live/        → n'existe pas
openssl … api.gathe-finance   → CN = backend.afrikamode.horus-lab.com
```

**Conclusion : PAS de nginx/certbot sur l'hôte → le proxy est CONTENEURISÉ (Cas B).**
Un nginx partagé (afrikamode) termine le TLS pour tous les domaines mais n'a
**aucun cert GATHE** → il sert son cert par défaut → mobile rejette.

### 1bis. Identifier le conteneur proxy (à lancer)

```bash
# Quel conteneur écoute sur 80/443 (le proxy au bord) ?
docker ps --format '{{.Names}}\t{{.Image}}\t{{.Ports}}' | grep -E ':80->|:443->'

# Y a-t-il un companion Let's Encrypt automatique (acme / certbot) ?
docker ps --format '{{.Names}} {{.Image}}' | grep -iE 'acme|certbot|letsencrypt'
```

### ✅ Proxy identifié (2026-07-09)

```
backend-nginx-1     nginx:alpine          0.0.0.0:80->80, 0.0.0.0:443->443
backend-certbot-1   certbot/certbot:latest
```

→ **nginx « nu » + certbot séparé** (projet `backend` = afrikamode, réseau
partagé). C'est le **Cas B-2**. certbot est déjà présent : on émet le cert GATHE
avec, on dépose la conf `nginx.gathe-finance.container.conf` du repo dans le
conf.d du conteneur, puis reload. Les services GATHE sont déjà joignables par
`gathe-backend` / `gathe-site` / `gathe-portal` / `gathe-admin` sur ce réseau.

DNS confirmé : `gathe-finance`, `api`, `admin`, **`portail`** (FR), `cms`
résolvent tous vers `81.0.246.144`. (`portal.` EN n'existe pas → la conf du repo
utilise bien `portail.`.)

---

## 2bis. RECETTE CONFIRMÉE (Cas B-2 — backend-nginx-1 + backend-certbot-1)

### Étape A — relever les montages (adapter les chemins ci-dessous)

```bash
echo "=== nginx mounts ==="   ; docker inspect backend-nginx-1  --format '{{range .Mounts}}{{.Source}} -> {{.Destination}}{{"\n"}}{{end}}'
echo "=== certbot mounts ===" ; docker inspect backend-certbot-1 --format '{{range .Mounts}}{{.Source}} -> {{.Destination}}{{"\n"}}{{end}}'
echo "=== réseaux nginx ==="  ; docker inspect backend-nginx-1  --format '{{range $k,$v := .NetworkSettings.Networks}}{{$k}} {{end}}'
docker exec backend-nginx-1 sh -c 'ls /etc/nginx/conf.d/; echo ---; ls /etc/letsencrypt/live/ 2>/dev/null'
```

Repérer dans la sortie :
- `CONF_D_HOST`  = Source montée sur `/etc/nginx/conf.d` du **nginx**
- `WEBROOT`      = Destination du webroot ACME (souvent `/var/www/certbot`),
  **partagée** entre nginx et certbot
- le volume `/etc/letsencrypt` doit être **partagé** nginx ↔ certbot (sinon le
  cert émis par certbot n'est pas vu par nginx)

### Étape B — émettre le certificat (5 domaines, challenge webroot)

```bash
docker exec backend-certbot-1 certbot certonly --webroot -w /var/www/certbot \
  -d gathe-finance.horus-lab.com \
  -d api.gathe-finance.horus-lab.com \
  -d admin.gathe-finance.horus-lab.com \
  -d portail.gathe-finance.horus-lab.com \
  -d cms.gathe-finance.horus-lab.com \
  -m horus8391@gmail.com --agree-tos --no-eff-email
```

> Le webroot `/.well-known/acme-challenge/` est déjà servi par le **server 80**
> de la conf GATHE (`root /var/www/certbot`). Si le cert n'existe pas encore,
> nginx ne peut pas charger la conf (bloc 443 sans cert). Deux options :
> 1. **émettre AVANT de déposer la conf** — mais alors le server 80 GATHE
>    n'existe pas encore pour servir le challenge. Utiliser plutôt l'ordre
>    ci-dessous (conf HTTP d'abord).

### Étape C — déposer la conf + reload (ordre qui évite le blocage)

```bash
# 1. Copier la conf GATHE dans le conf.d du conteneur nginx
#    (remplacer CONF_D_HOST par le chemin relevé à l'étape A)
cp /opt/gathe-finance/infra/nginx.gathe-finance.container.conf \
   CONF_D_HOST/gathe-finance.conf

# 2. Recharger nginx AVEC uniquement le bloc HTTP:80 valide — si le bloc 443
#    casse (cert absent), commenter temporairement les 4 blocs `listen 443`
#    OU faire l'étape B d'abord. Le plus simple :
#    a) test conf
docker exec backend-nginx-1 nginx -t
#    b) si "certificate ... No such file" → lancer l'étape B (le server 80 est
#       chargé donc le challenge passe), PUIS re-tester :
docker exec backend-nginx-1 nginx -t && docker exec backend-nginx-1 nginx -s reload
```

> Astuce robuste si `nginx -t` refuse de charger tant que le cert manque :
> déposer d'abord une version *HTTP-only* (garder uniquement le `server {listen 80…}`),
> `reload`, lancer l'étape B, puis remettre la conf complète et `reload`.

### Étape D — renouvellement auto

Le conteneur `backend-certbot-1` tourne déjà en boucle `renew` pour afrikamode ;
le nouveau cert GATHE sera renouvelé avec les autres. Vérifier après coup :
`docker exec backend-certbot-1 certbot certificates`.

---

## 2. Fix

### Cas A — nginx host + certbot (le plus courant)

```bash
# 2.1 (si la conf GATHE n'est pas dans conf.d) la déposer
cp /opt/gathe-finance/infra/nginx.gathe-finance.container.conf \
   /etc/nginx/conf.d/gathe-finance.conf

# 2.2 Émettre le certificat Let's Encrypt pour TOUS les sous-domaines GATHE
#     (le port 80 doit router le challenge HTTP-01 vers ce nginx)
certbot --nginx \
  -d gathe-finance.horus-lab.com \
  -d api.gathe-finance.horus-lab.com \
  -d admin.gathe-finance.horus-lab.com \
  -d portal.gathe-finance.horus-lab.com \
  -d cms.gathe-finance.horus-lab.com

# 2.3 Vérifier + recharger nginx
nginx -t && nginx -s reload
```

> Si `certbot --nginx` n'est pas dispo, utiliser `certbot certonly --webroot -w <webroot> -d …`
> ou `--standalone` (arrêter nginx le temps du challenge), puis pointer
> `ssl_certificate` vers `/etc/letsencrypt/live/gathe-finance.horus-lab.com/fullchain.pem`.

### Cas B — nginx dans un conteneur (proxy partagé) — **c'est notre cas**

#### Cas B-1 — proxy `nginx-proxy` + `acme-companion` (émission auto par env)

Si le proxy est `nginxproxy/nginx-proxy` (+ `acme-companion`), il génère un cert
Let's Encrypt **automatiquement** dès qu'un conteneur du réseau partagé porte les
variables `VIRTUAL_HOST` + `LETSENCRYPT_HOST`. Nos services GATHE ne les ont
**pas** → aucun cert émis. Fix : les ajouter dans le compose.

Sur chaque service exposé (`backend`, `site`, `portal`, `admin`) de
`infra/docker-compose.nginx-external.yml`, ajouter :

```yaml
    environment:
      VIRTUAL_HOST: api.gathe-finance.horus-lab.com        # le sous-domaine du service
      VIRTUAL_PORT: "8000"                                  # 8000 backend / 3000 front
      LETSENCRYPT_HOST: api.gathe-finance.horus-lab.com
      LETSENCRYPT_EMAIL: horus8391@gmail.com
```

| service | VIRTUAL_HOST                          | VIRTUAL_PORT |
|---------|---------------------------------------|--------------|
| backend | api.gathe-finance.horus-lab.com       | 8000         |
| site    | gathe-finance.horus-lab.com           | 3000         |
| portal  | portal.gathe-finance.horus-lab.com    | 3000         |
| admin   | admin.gathe-finance.horus-lab.com     | 3000         |

Puis `up -d` les services → l'acme-companion détecte les nouveaux hosts et émet
les certs (30 s à 2 min). Vérifier avec la section 3.

#### Cas B-2 — nginx « nu » (conf montée à la main)

Le cert doit être émis **puis** monté dans le conteneur nginx :

```bash
# 1. Émettre le cert (certbot en standalone/webroot depuis l'hôte, port 80 libre)
#    ou via l'outil du proxy. Ex. standalone (coupe le proxy le temps du challenge) :
docker run --rm -p 80:80 \
  -v /opt/letsencrypt:/etc/letsencrypt \
  certbot/certbot certonly --standalone \
  -d gathe-finance.horus-lab.com -d api.gathe-finance.horus-lab.com \
  -d admin.gathe-finance.horus-lab.com -d portal.gathe-finance.horus-lab.com \
  -m horus8391@gmail.com --agree-tos --no-eff-email

# 2. Monter le cert + un server block gathe dans le conteneur nginx partagé,
#    puis recharger :
docker exec <nom_conteneur_nginx> nginx -t
docker exec <nom_conteneur_nginx> nginx -s reload
```

> ⚠️ Vérifier l'orthographe du domaine portail : le repo utilise `portal.` (EN).
> Aligner `server_name` + `-d` de certbot sur le **vrai** domaine DNS.

---

## 3. Vérification (le login mobile passera ensuite)

```bash
# Le bon certificat est servi ?
echo | openssl s_client -connect api.gathe-finance.horus-lab.com:443 \
  -servername api.gathe-finance.horus-lab.com 2>/dev/null \
  | openssl x509 -noout -subject -dates

# L'API répond en TLS strict (plus besoin de -k) :
curl -s -o /dev/null -w "HTTP %{http_code}\n" https://api.gathe-finance.horus-lab.com/api/v1/auth/csrf/
```

Attendu : `subject` sur `*.gathe-finance.horus-lab.com` + `HTTP 200`.
→ **Login mobile OK immédiatement** (l'app est correcte ; seul le certificat bloquait).

---

## Note
L'app mobile est bonne : URL prod correcte (`https://api.gathe-finance.horus-lab.com`,
build release), push validé de bout en bout, token FCM OK. Le seul blocage login
= ce certificat TLS côté VPS.
