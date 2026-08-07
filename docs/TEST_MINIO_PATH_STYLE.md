# TEST à faire — écriture MinIO en path-style

> Objectif : confirmer que le bug « candidature avec pièce jointe » se corrige
> en passant l'addressing S3 de `virtual` à `path` (obligatoire pour MinIO).
> À lancer **sur le serveur cliente**, en SSH.

## 1. Se placer au bon endroit

```bash
cd /home/gathe/gathe-finance/infra
alias dc='docker compose -f docker-compose.prod.yml -f docker-compose.client.yml --env-file .env.prod'
```

## 2. Ouvrir le shell Django du backend

```bash
dc exec backend python manage.py shell
```

## 3. Coller ce bloc dans le shell

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

Pour sortir du shell : `exit()`

## 4. Lire le résultat

| Ce qui s'affiche | Signification | Suite |
|---|---|---|
| **`200`** ✅ | path-style résout tout (hôte joignable + bucket OK) | Coller le `200` → je fais le commit/PR/deploy du fix |
| `NameResolutionError` / `EndpointConnectionError` | l'endpoint MinIO n'est pas résolvable depuis le backend | Coller l'erreur → on corrige `AWS_S3_ENDPOINT_URL` |
| `NoSuchBucket` | hôte OK mais le bucket n'existe pas | Coller l'erreur → créer le bucket dans MinIO |

## 5. Me renvoyer

Copie-colle simplement les 2 lignes de sortie (le `endpoint = … | bucket = …`
et le code, ex. `200`) ou l'erreur complète si ça plante.

---

**Rappel** : ce test ne modifie rien de définitif (il écrit juste un petit
`debug/test.txt`). Il sert uniquement à valider la correction avant de déployer.
Le diagnostic complet est dans `DIAG_CANDIDATURE_PIECE_STOCKAGE.md`.
