# Activation des notifications push (FCM) — GATHE Finance

Le code (mobile + backend) est prêt. Il reste **1 seule action manuelle** :
poser la **clé du service account Firebase** sur le VPS.

- Projet Firebase : **`gathe-finance`**
- Backend : `FCM_CREDENTIALS_JSON` (vide = push dormant / no-op ; posé = envoi actif)
- Le code accepte **soit le JSON en clair, soit un chemin de fichier**.

---

## 0. Étapes à suivre sur le VPS (clé JSON en main)

> 📁 Le `.env.prod` est sur le VPS : `/opt/gathe-finance/infra/.env.prod`.
> ⚠️ **Piège n°1** : dans un `.env`, la valeur doit tenir sur **UNE seule ligne**.
> Coller le JSON multi-ligne casse tout (`unexpected character "\"" in variable name`).
> On passe donc par un fichier + `jq -c` pour l'aplatir.

Connecté en SSH sur le VPS :

```bash
cd /opt/gathe-finance/infra

# 1. (si tu avais déjà collé le JSON multi-ligne) NETTOYER .env.prod :
nano .env.prod
#    → supprimer TOUTES les lignes du JSON collé, enregistrer (Ctrl+O, Entrée, Ctrl+X)

# 2. Mettre le JSON dans un fichier (multi-ligne OK dans un fichier normal) :
nano fcm.json
#    → coller TOUT le JSON de la clé de service, enregistrer

# 3. L'aplatir en UNE ligne dans .env.prod (jq requis) :
apt-get install -y jq
printf 'FCM_CREDENTIALS_JSON=%s\n' "$(jq -c . fcm.json)" >> .env.prod
rm fcm.json                      # ne pas garder le secret en clair sur le disque

# 4. Vérifier qu'il n'y a qu'UNE ligne (doit afficher 1) :
grep -c '^FCM_CREDENTIALS_JSON=' .env.prod

# 5. Redémarrer le backend (prend la nouvelle variable) :
docker compose -f docker-compose.prod.yml -f docker-compose.nginx-external.yml --env-file .env.prod up -d backend

# 6. Vérifier (pas d'erreur = ok, dormant jusqu'au 1er envoi) :
docker compose -f docker-compose.prod.yml -f docker-compose.nginx-external.yml --env-file .env.prod logs --tail=30 backend | grep -i "fcm\|push"
```

> ⚠️ Ne **jamais** committer la clé ni l'afficher (`cat`) dans un terminal
> partagé — les commandes ci-dessus l'écrivent sans l'imprimer.

### Plan B — fichier monté (si `.env` rechigne encore sur les guillemets)

Le code accepte aussi un **chemin de fichier**. Alternative 100 % sûre :

```bash
cd /opt/gathe-finance/infra
nano fcm.json                    # coller le JSON, enregistrer
# dans .env.prod, mettre juste :  FCM_CREDENTIALS_JSON=/app/fcm.json
```
+ monter le fichier dans le service `backend` du compose (à faire ajouter au repo) :
```yaml
    volumes:
      - ./fcm.json:/app/fcm.json:ro
```

---

## 1. Récupérer la clé (console Firebase)

`gcloud` n'est pas installé sur la machine de dev → génération via la console.

1. Ouvrir : <https://console.firebase.google.com/project/gathe-finance/settings/serviceaccounts/adminsdk>
2. Cliquer **« Générer une nouvelle clé privée »** → **Générer**.
3. Un fichier JSON se télécharge : `gathe-finance-firebase-adminsdk-XXXXX.json`.

> ⚠️ Fichier **secret** — ne jamais le committer dans le repo.

---

## 2. Poser la clé sur le VPS

`.env.prod` vit **sur le VPS** (`/opt/gathe-finance/.env.prod`, géré à la main, hors repo).

### Option B — JSON en une ligne (recommandée, aucun montage)

```bash
ssh <user>@<vps>
cd /opt/gathe-finance
nano .env.prod
```

Ajouter une ligne (le JSON **sur une seule ligne**) :

```
FCM_CREDENTIALS_JSON={"type":"service_account","project_id":"gathe-finance","private_key_id":"...","private_key":"-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n","client_email":"firebase-adminsdk-...@gathe-finance.iam.gserviceaccount.com","client_id":"...","token_uri":"https://oauth2.googleapis.com/token", ...}
```

> Astuce pour aplatir le JSON en une ligne (en local, avant de copier) :
> ```bash
> jq -c . gathe-finance-firebase-adminsdk-XXXXX.json
> ```

### Option A — fichier + montage (si tu préfères un fichier)

1. Copier le JSON sur le VPS :
   ```bash
   scp gathe-finance-firebase-adminsdk-XXXXX.json <user>@<vps>:/opt/gathe-finance/fcm.json
   ```
2. Monter le fichier dans le conteneur backend (service `backend` de `docker-compose.prod.yml`) :
   ```yaml
   volumes:
     - ./fcm.json:/app/fcm.json:ro
   ```
3. Dans `.env.prod` :
   ```
   FCM_CREDENTIALS_JSON=/app/fcm.json
   ```

---

## 3. Appliquer (redémarrer le backend)

```bash
cd /opt/gathe-finance
docker compose -f docker-compose.prod.yml -f docker-compose.nginx-external.yml --env-file .env.prod up -d backend
```

À partir de ce redémarrage, `push_enabled()` passe à `True` et l'envoi FCM est actif.

---

## 4. Vérifier

```bash
# Logs backend : chercher les traces d'envoi FCM
docker compose -f docker-compose.prod.yml -f docker-compose.nginx-external.yml --env-file .env.prod logs -f backend | grep -i "fcm\|revalidation\|push"
```

- Un push OK → `Revalidation webhook OK` n'est pas lié ; chercher plutôt les 200 FCM.
- Un token invalide → le `DeviceToken` est automatiquement désactivé.

Test bout-en-bout : ouvrir l'app mobile **connectée à internet**, se connecter (le token
se pose via `syncToken`), puis déclencher un événement qui appelle
`create_notification(...)` (ex. une réponse à un commentaire, une décision de crédit).

---

## Rappels — ce qui est déjà en place (code)

- **Mobile** : projet `gathe-finance`, `firebase_options.dart` + `google-services.json`,
  `Firebase.initializeApp()`, `FcmPushTokenProvider`, permission `POST_NOTIFICATIONS`,
  handlers foreground (notif locale) / background, `syncToken`/`clearToken` au login/logout.
- **Backend** : `_deliver()` FCM HTTP v1 (OAuth2 service account), nettoyage auto des tokens
  invalides. Dormant tant que `FCM_CREDENTIALS_JSON` est vide.
