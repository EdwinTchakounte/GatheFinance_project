"""Production settings (VPS Contabo)."""
from .base import *  # noqa: F401,F403
from .base import (
    ALLOWED_HOSTS,
    CORS_ALLOWED_ORIGINS,
    CSRF_TRUSTED_ORIGINS,
    EMAIL_FALLBACK_BACKEND,
    MIDDLEWARE,
    REST_FRAMEWORK,
    STORAGES,
    env,
)
from .email_routing import resolve_email_backends

DEBUG = False
SECRET_KEY = env("DJANGO_SECRET_KEY")  # required in production

# --- Hosts internes auto-ajoutes (rewrite Next.js / SSR / healthcheck) ------
# Les conteneurs Next.js (admin, portal, site) appellent le backend via leurs
# rewrites/SSR avec l'URL interne `http://gathe-backend:8000`. Django reçoit
# alors `Host: gathe-backend` qui doit être dans ALLOWED_HOSTS, sinon il
# repond 400 (Disallowed Host) — ecran blanc cote admin/portal.
# On les force ici, en plus de ce qui est defini via DJANGO_ALLOWED_HOSTS dans
# l'env, pour que la stack reste fonctionnelle meme si l'override
# `docker-compose.nginx-external.yml` n'est pas applique au lancement.
_INTERNAL_HOSTS = ["gathe-backend", "backend", "localhost", "127.0.0.1"]
for _host in _INTERNAL_HOSTS:
    if _host not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(_host)

# --- CSRF_TRUSTED_ORIGINS auto-deriva depuis ALLOWED_HOSTS -------------------
# Tout sous-domaine public (sans IP, sans host technique interne) devient une
# origine CSRF de confiance pour les requetes POST/PATCH/DELETE des SPA admin
# et portail. Cela evite un oubli silencieux du `CSRF_TRUSTED_ORIGINS` dans
# `.env.prod` qui rendrait toute mutation impossible.
_PUBLIC_HOSTS = [
    h for h in ALLOWED_HOSTS
    if h not in _INTERNAL_HOSTS and not h.replace(".", "").isdigit()
]
for _host in _PUBLIC_HOSTS:
    _origin = f"https://{_host}"
    if _origin not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append(_origin)
    # Même dérivation pour CORS : le portail/admin (sous-domaines distincts de
    # l'API) font des fetch credentialed cross-origin. Si l'origine n'est pas
    # dans CORS_ALLOWED_ORIGINS, le navigateur JETTE le `Set-Cookie` de la
    # réponse /auth/csrf/ → pas de cookie csrftoken → tout POST échoue en 403
    # ("Session de sécurité expirée"). On l'auto-dérive pour ne jamais dépendre
    # d'un oubli dans `.env.prod`.
    if _origin not in CORS_ALLOWED_ORIGINS:
        CORS_ALLOWED_ORIGINS.append(_origin)

# --- Email : Brevo (API HTTP) avec repli SMTP en production ------------------
# Voie nominale = ce que demande l'env (Brevo par défaut). Le backend à DOUBLE
# VOIE ne s'interpose QUE si un SMTP de secours est réellement configuré.
#
# ⚠️ Pourquoi la décision est prise ICI et jamais dans le docker-compose :
# `deploy.yml` téléverse `infra/` à chaque déploiement, mais deux chemins
# gardent l'ANCIENNE image — le repli sur les images en cache quand le pull
# GHCR échoue, et le rollback quand le healthcheck ne passe pas. Un compose
# qui nommerait `FailoverEmailBackend` se retrouverait alors devant une image
# où ce module n'existe pas : ImportError à chaque envoi, donc TOUS les
# e-mails muets — la panne de septembre reproduite par un rollback.
# En décidant ici, le réglage voyage avec le code qui l'implémente : une
# ancienne image porte un ancien `prod.py`, qui retombe simplement sur Brevo.
# La règle elle-même vit dans `email_routing`, sans import Django, pour rester
# testable sans charger les réglages de prod ni leurs dépendances.
EMAIL_BACKEND, EMAIL_PRIMARY_BACKEND = resolve_email_backends(
    env("EMAIL_BACKEND", default="anymail.backends.brevo.EmailBackend"),
    fallback_backend=EMAIL_FALLBACK_BACKEND,
)

# Serve compressed, hashed static files via WhiteNoise.
MIDDLEWARE = [
    *MIDDLEWARE[:2],  # CorsMiddleware, SecurityMiddleware
    "whitenoise.middleware.WhiteNoiseMiddleware",
    *MIDDLEWARE[2:],
]
STORAGES = {
    **STORAGES,
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

# --- HTTPS / security hardening ---------------------------------------------

SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=31536000)
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"

# --- Cookies cross-subdomain (CRITIQUE pour le portail + admin) -------------
# Le backend API tourne sur `api.gathe-finance.horus-lab.com`, alors que les
# fronts Next.js vivent sur `portail.*`, `admin.*`, et `gathe-finance.*`.
# Sans `Domain=.gathe-finance.horus-lab.com`, le cookie de session est scope
# uniquement a `api.*` et le navigateur ne le partage PAS lorsque l'utilisateur
# clique sur un lien externe (retour au site / portail) puis revient.
# Resultat : la session est "perdue" au moindre changement de sous-domaine.
#
# Avec `.gathe-finance.horus-lab.com`, le cookie est partage entre tous les
# sous-domaines (api / portail / admin / site / cms) et la session persiste.
# eTLD+1 = `horus-lab.com` donc SameSite=Lax considere les 5 hotes comme
# same-site, ce qui permet aussi les requetes XHR cross-origin avec
# credentials.
_COOKIE_DOMAIN = env("COOKIE_DOMAIN", default=".gathe-finance.horus-lab.com")
SESSION_COOKIE_DOMAIN = _COOKIE_DOMAIN
CSRF_COOKIE_DOMAIN = _COOKIE_DOMAIN

# --- Media on Backblaze B2 (S3-compatible) ----------------------------------
# Set AWS_* env vars to enable; otherwise falls back to local filesystem (base.py).

if env("AWS_STORAGE_BUCKET_NAME", default=""):
    STORAGES = {
        "default": {
            # url() renvoie le proxy backend /media/<clé> (protected_media),
            # jamais l'URL MinIO interne — cf. config/storage.py.
            "BACKEND": "config.storage.ProxiedMediaS3Storage",
            "OPTIONS": {
                "bucket_name": env("AWS_STORAGE_BUCKET_NAME"),
                "access_key": env("AWS_ACCESS_KEY_ID"),
                "secret_key": env("AWS_SECRET_ACCESS_KEY"),
                "endpoint_url": env("AWS_S3_ENDPOINT_URL"),  # e.g. https://s3.eu-central-003.backblazeb2.com
                "region_name": env("AWS_S3_REGION_NAME", default=""),
                "file_overwrite": False,
                "querystring_auth": False,  # public-read media; private docs handled separately
                "default_acl": None,
                # "virtual" (<bucket>.<host>) convient à Backblaze B2 (DNS wildcard).
                # MinIO auto-hébergé (DMZ cliente) EXIGE "path" (<host>/<bucket>) :
                # sinon botocore forge un hôte `<bucket>.<endpoint>` non résolvable
                # → gaierror à l'écriture des fichiers. Piloté par env, défaut inchangé.
                "addressing_style": env(
                    "AWS_S3_ADDRESSING_STYLE", default="virtual"
                ),
            },
        },
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
        },
    }
    # Optionally serve media through Cloudflare in front of B2.
    if env("MEDIA_DOMAIN", default=""):
        MEDIA_URL = f"https://{env('MEDIA_DOMAIN')}/"

# --- Error tracking ----------------------------------------------------------

if env("SENTRY_DSN", default=""):
    try:
        import sentry_sdk

        sentry_sdk.init(
            dsn=env("SENTRY_DSN"),
            environment=env("SENTRY_ENVIRONMENT", default="production"),
            traces_sample_rate=env.float("SENTRY_TRACES_SAMPLE_RATE", default=0.1),
            send_default_pii=False,
        )
    except ImportError:  # pragma: no cover
        pass

# Stricter API throttle in production.
REST_FRAMEWORK = {
    **REST_FRAMEWORK,
    # Tous les scopes utilisés par DEFAULT_THROTTLE_CLASSES doivent avoir un
    # taux, sinon DRF lève ImproperlyConfigured ("No default throttle rate set
    # for 'user' scope"). On garde `user` et `auth-login` de base.
    "DEFAULT_THROTTLE_RATES": {
        # Généreux : l'écrêtage fin est délégué au middleware de blacklist IP.
        # TOUS les scopes utilisés doivent figurer ici (sinon ImproperlyConfigured
        # dès qu'un throttle est invoqué) — d'où auth-password-reset ci-dessous.
        "anon": "1000/hour",
        "user": "5000/hour",
        "form-submit": "10/hour",
        "auth-login": "20/hour",
        "auth-password-reset": "5/hour",
    },
}
