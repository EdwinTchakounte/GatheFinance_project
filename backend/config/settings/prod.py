"""Production settings (VPS Contabo)."""
from .base import *  # noqa: F401,F403
from .base import MIDDLEWARE, REST_FRAMEWORK, STORAGES, env

DEBUG = False
SECRET_KEY = env("DJANGO_SECRET_KEY")  # required in production

# --- Email : envoi RÉEL via l'API HTTP Brevo (django-anymail) en production --
# base.py défaut = console (dev). En prod on bascule sur le backend Anymail-Brevo
# qui appelle l'API transactionnelle Brevo avec ANYMAIL["BREVO_API_KEY"].
# (Mettre EMAIL_BACKEND=...console.EmailBackend dans l'env pour un test à blanc.)
EMAIL_BACKEND = env(
    "EMAIL_BACKEND", default="anymail.backends.brevo.EmailBackend"
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

# --- Media on Backblaze B2 (S3-compatible) ----------------------------------
# Set AWS_* env vars to enable; otherwise falls back to local filesystem (base.py).

if env("AWS_STORAGE_BUCKET_NAME", default=""):
    STORAGES = {
        "default": {
            "BACKEND": "storages.backends.s3.S3Storage",
            "OPTIONS": {
                "bucket_name": env("AWS_STORAGE_BUCKET_NAME"),
                "access_key": env("AWS_ACCESS_KEY_ID"),
                "secret_key": env("AWS_SECRET_ACCESS_KEY"),
                "endpoint_url": env("AWS_S3_ENDPOINT_URL"),  # e.g. https://s3.eu-central-003.backblazeb2.com
                "region_name": env("AWS_S3_REGION_NAME", default=""),
                "file_overwrite": False,
                "querystring_auth": False,  # public-read media; private docs handled separately
                "default_acl": None,
                "addressing_style": "virtual",
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
    "DEFAULT_THROTTLE_RATES": {"anon": "120/hour", "form-submit": "10/hour"},
}
