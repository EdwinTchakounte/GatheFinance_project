# Obtenir les valeurs DMZ pour `.env.prod` (serveur cliente)

Ces valeurs se lisent depuis **Docker sur le serveur cliente** (`gathe@169.58.69.78`).
Elles remplissent `EDGE_NETWORK`, `DATA_NETWORK`, `TRAEFIK_CERTRESOLVER` (+ `TRAEFIK_ENTRYPOINT`) dans `infra/.env.prod`.

> 💡 Le plus rapide : `bash infra/scripts/inspect-dmz.sh` sort les 4 valeurs d'un coup (section §2 de son rapport). Ci-dessous la méthode manuelle.

---

## 0. Repérer les conteneurs

```bash
docker ps --format '{{.Names}}'      # repère traefik, postgres, minio
```

---

## 1. `EDGE_NETWORK` et `DATA_NETWORK`

Ce sont des **réseaux Docker**.

```bash
docker network ls
```

Identifier lequel est lequel :

```bash
# EDGE_NETWORK = réseau auquel TRAEFIK est rattaché (ingress + TLS)
docker inspect <traefik_container> -f '{{range $k,$v := .NetworkSettings.Networks}}{{$k}}{{"\n"}}{{end}}'

# DATA_NETWORK = réseau où sont POSTGRES et MINIO (souvent "internal: true")
docker inspect <postgres_container> -f '{{range $k,$v := .NetworkSettings.Networks}}{{$k}}{{"\n"}}{{end}}'
```

- `EDGE_NETWORK` = le réseau de Traefik.
- `DATA_NETWORK` = le réseau de Postgres/MinIO.

---

## 2. `TRAEFIK_CERTRESOLVER`

C'est le **nom du resolver ACME** (Let's Encrypt) défini dans la config statique de leur Traefik.

```bash
# a) depuis la commande/args du conteneur Traefik
docker inspect <traefik_container> -f '{{range .Config.Cmd}}{{println .}}{{end}}' | grep -i certificatesresolvers

# b) depuis le fichier de conf monté (traefik.yml / traefik.toml)
docker inspect <traefik_container> -f '{{range .Mounts}}{{.Source}} -> {{.Destination}}{{"\n"}}{{end}}'
grep -riE "certificatesresolvers|acme" /srv/edge/    # ou le dossier de conf trouvé ci-dessus
```

Le resolver est la clé sous `certificatesResolvers:` (ex. `letsencrypt`, `myresolver`).

---

## 3. 🎯 Raccourci le plus fiable — copier un service qui marche déjà

Un conteneur déjà exposé par leur Traefik (ex. derrière `console.` ou `s3.`) porte **toutes les réponses dans ses labels** :

```bash
docker inspect <un_conteneur_qui_marche> \
  -f '{{range $k,$v := .Config.Labels}}{{if (hasPrefix $k "traefik.")}}{{$k}}={{$v}}{{"\n"}}{{end}}{{end}}'
```

On y lit directement :

| Label trouvé | Variable `.env.prod` |
|---|---|
| `traefik.docker.network=YYY` | `EDGE_NETWORK=YYY` |
| `...tls.certresolver=XXX` | `TRAEFIK_CERTRESOLVER=XXX` |
| `...entrypoints=ZZZ` | `TRAEFIK_ENTRYPOINT=ZZZ` (souvent `websecure`) |

---

## 4. Report dans `infra/.env.prod`

```bash
EDGE_NETWORK=........
DATA_NETWORK=........
TRAEFIK_CERTRESOLVER=........
TRAEFIK_ENTRYPOINT=websecure
```

---

## ⚠️ Note — le déploiement a échoué sur la clé SSH (pas sur ces valeurs)

Le run `deploy.yml` s'est arrêté **avant** (étape « Upload infra/ ») sur :

```
ssh: handshake failed: unable to authenticate, attempted methods [none], no supported methods remain
```

→ La clé que GitHub Actions utilise (`CLIENT_VPS_SSH_PRIVATE_KEY`) **ne correspond pas** à une clé publique autorisée pour l'utilisateur `gathe` sur le serveur.

**À corriger avant de relancer :**
- la **clé publique** correspondant au secret `CLIENT_VPS_SSH_PRIVATE_KEY` doit être dans `/home/gathe/.ssh/authorized_keys` du serveur cliente ;
- vérifier que `CLIENT_VPS_USER = gathe` (et `CLIENT_VPS_HOST = 169.58.69.78`) ;
- permissions : `chmod 700 /home/gathe/.ssh` et `chmod 600 /home/gathe/.ssh/authorized_keys`.

Vérifier depuis une machine avec la clé privée :
```bash
ssh -i <cle_privee> gathe@169.58.69.78 'echo OK'
```

**Ordre final :** (1) remplir `.env.prod` (ces valeurs + base + MinIO), (2) régler la clé SSH du déploiement, (3) relancer `gh workflow run deploy.yml -f image_tag=main`.
