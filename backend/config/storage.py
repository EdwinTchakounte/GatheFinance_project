"""Storage média custom pour le déploiement S3/MinIO.

Problème : ``S3Storage.url()`` fabrique l'URL du fichier à partir de
l'``endpoint_url`` (en DMZ cliente = ``http://minio:9000``, hôte Docker
INTERNE). Le backend l'atteint (l'upload marche), mais le navigateur de
l'admin/portail NON → les pièces ne s'affichent jamais.

Solution : on ne sert JAMAIS MinIO directement au navigateur. ``url()`` renvoie
l'URL du proxy backend ``<PUBLIC_BASE_URL>/media/<clé>`` (vue ``protected_media``
dans ``config/urls.py``), qui :
  - streame le fichier depuis le storage (MinIO) côté serveur,
  - garde les pièces PRIVÉES (CNI, plans, photos d'adhésion, BRC…) derrière
    une autorisation staff, tout en laissant publics les préfixes autorisés
    (flyers, avatars, assets…).

Aucun domaine MinIO public n'est donc requis, et rien de sensible n'est exposé.
"""

from urllib.parse import quote

from django.conf import settings
from storages.backends.s3 import S3Storage


class ProxiedMediaS3Storage(S3Storage):
    """S3Storage dont ``url()`` pointe sur le proxy média du backend."""

    def url(self, name, parameters=None, expire=None, http_method=None):
        base = (getattr(settings, "PUBLIC_BASE_URL", "") or "").rstrip("/")
        # ``name`` est la clé relative au bucket (ex. coop/adhesion/2026/08/cni.png).
        # quote() préserve les « / » et encode le reste (espaces, accents…).
        return f"{base}/media/{quote(name.lstrip('/'))}"
