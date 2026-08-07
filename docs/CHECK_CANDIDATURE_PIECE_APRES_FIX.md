# CHECK — candidature avec pièce après le fix path-style

> Contexte : PR #52 déployée (code `addressing_style` pilotable par env) +
> `AWS_S3_ADDRESSING_STYLE=path` posé dans `.env.prod`.
> Symptôme observé après manœuvre : candidature **avec pièce** renvoie encore
> **400**, mais désormais après **~22 s** (timeout de connexion, plus le gaierror
> DNS instantané d'avant). Donc il faut vérifier 2 points sur le serveur.
> À lancer **sur le serveur cliente**, en SSH.

## 0. Préparation

```bash
cd /home/gathe/gathe-finance/infra
alias dc='docker compose -f docker-compose.prod.yml -f docker-compose.client.yml --env-file .env.prod'
```

## A. Le conteneur backend voit-il bien la variable ?

```bash
dc exec backend printenv | grep -iE "AWS_S3_ADDRESSING_STYLE|AWS_S3_ENDPOINT_URL"
```

Attendu :
```
AWS_S3_ADDRESSING_STYLE=path
AWS_S3_ENDPOINT_URL=http://minio:9000
```

- **Ligne `AWS_S3_ADDRESSING_STYLE` absente ou vide** → le backend n'a pas rechargé
  `.env.prod`. Forcer un vrai redémarrage :
  ```bash
  dc stop backend
  dc up -d --no-deps backend
  # re-vérifier :
  dc exec backend printenv | grep AWS_S3_ADDRESSING_STYLE
  ```

## B. Le vrai traceback de l'échec courant

```bash
# 1) Relancer d'abord UNE candidature avec pièce depuis la vitrine
#    (campagne « TEST Candidature Live 07-08 »), PUIS :
dc logs --tail=150 backend | grep -B2 -A40 "public_campaign_apply" | tail -50
```

Lecture :

| Ce que montre le traceback | Signification | Action |
|---|---|---|
| encore `gathe-media.minio` | la variable `path` n'est PAS prise en compte | refaire la manœuvre §A (stop + up), vérifier `.env.prod` |
| `minio:9000` + **timeout / Connection refused / timed out** | style OK, mais le backend n'atteint pas le port 9000 de MinIO dans le vrai flux | voir §C (réseau) |
| plus d'erreur / `201` | c'est bon | faire §D (check complet) |

## C. Réseau backend → MinIO (si timeout sur `minio:9000`)

```bash
# le backend est-il sur le même réseau que MinIO, et le port répond-il ?
dc exec backend python -c "import socket; s=socket.create_connection(('minio',9000),5); print('TCP minio:9000 OK'); s.close()"

# quels réseaux porte le conteneur backend ?
docker inspect $(dc ps -q backend) --format '{{json .NetworkSettings.Networks}}' | tr ',' '\n' | grep -i name
```

- **`TCP minio:9000 OK`** mais l'upload échoue quand même → me le signaler (cas à
  creuser côté django-storages).
- **Échec ici** → le conteneur backend n'est pas (ou plus) rattaché au réseau
  `data` où vit MinIO, ou MinIO est down. Vérifier `DATA_NETWORK` dans `.env.prod`
  et que MinIO tourne.

## D. Check complet (une fois §A/§B OK)

Petit fichier de test :
```bash
printf 'test' > /tmp/piece.txt
```

Candidature avec pièce, en direct sur le backend (campagne id 1 = exige une pièce) :
```bash
curl -sS -o /tmp/mp.json -w "HTTP %{http_code}\n" \
  -X POST "https://api.gathe-finance.com/api/v1/loans/campaigns/1/apply/" \
  -H "Accept: application/json" \
  -F "nom=PieceOK" -F "prenom=Probe" -F "phone=699000111" \
  -F "email=probe.piece@example.com" -F "montant=15000" -F "motif=check" \
  -F "doc_0=@/tmp/piece.txt;type=text/plain"
cat /tmp/mp.json; echo
```

Attendu : **`HTTP 201`** avec un corps `{"id":..., "statut":"en_attente", ...}`.

Puis vérifier côté admin (`admin.gathe-finance.com` → Campagnes → « TEST
Candidature Live 07-08 » → Détail) que la candidature **PieceOK Probe** apparaît
avec sa pièce jointe.

## À me renvoyer

Copie-colle la sortie de **§A** et **§B** (et §C si timeout). J'identifie la
correction exacte.

---

Réf. cause racine + fix : `DIAG_CANDIDATURE_PIECE_STOCKAGE.md`.
